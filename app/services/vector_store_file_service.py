# app\services\vector_store_file_service.py
import os
import time
import chromadb
from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.embedding_service import embed_texts
from app.services.Extractors.pdf_extractor import extract_from_pdf
from app.services.Extractors.text_extractor import extract_from_txt
chroma_client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./storage/chroma")
)

# --- Main Service ---

async def attach_file_to_vector_store(
    redis,
    vector_store_id: str,
    file_id: str,
    chunk_size: int,
    chunk_overlap: int
):
    vs_file_id = f"vsfile_{vector_store_id}_{file_id}"
    
    # 1) check vector store exists
    vs_meta = await redis.hgetall(f"vector_store:{vector_store_id}")
    if not vs_meta:
        raise HTTPException(status_code=404, detail="Vector store not found.")

    # 2) check file exists
    file_meta = await redis.hgetall(f"file:{file_id}")
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found.")
    
    # 3) duplicate check -- فقط با همین کلید استاندارد
    already_attached = await redis.sismember(
        f"vector_store_files:{vector_store_id}",
        vs_file_id
    )
    if already_attached:
        raise HTTPException(
            status_code=409,
            detail="This file is already attached to this vector store."
        )


    file_path = file_meta["path"]
    file_name = file_meta.get("filename") or os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    full_path = os.path.join(os.getcwd(), file_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"File not found at: {full_path}")
    
    # 2. استخراج متن بر اساس فرمت (Switch Case / IF)
    if ext == ".txt":
        raw_documents = extract_from_txt(full_path)
    elif ext == ".pdf":
        raw_documents = extract_from_pdf(full_path)
    else:
        raise ValueError(f"Extension {ext} is not supported yet")

    # 3. تکه تکه کردن (Chunking)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    final_chunks = []
    final_metadatas = []
    global_chunk_index = 0
    for doc in raw_documents:
        # برای هر بخش (مثلاً هر صفحه PDF)، چانک می‌سازیم
        chunks = splitter.split_text(doc["text"])
        for i, chunk_text in enumerate(chunks):
            final_chunks.append(chunk_text)
            
            # ترکیب متادیتای پایه با متادیتای اختصاصی (مثل شماره صفحه)
            meta = {
                "file_id": file_id,
                "file_name": file_name,
                "chunk_index": global_chunk_index
            }
            meta.update(doc["metadata"]) # اضافه کردن page_number اگر وجود داشته باشد
            final_metadatas.append(meta)

            global_chunk_index += 1
    
    if not final_chunks:
        raise HTTPException(
            status_code=400,
            detail="No extractable text found in the file."
        )
    # 4. تولید Embedding
    embeddings = await embed_texts(final_chunks)

    # 5. ذخیره در Chroma
    collection = chroma_client.get_or_create_collection(
        name=vector_store_id,
        embedding_function=None
    )

    # پاک‌سازی قبلی برای جلوگیری از duplicate / re-index inconsistency
    collection.delete(where={"file_id": file_id})

    ids = [f"{file_id}_{i}" for i in range(len(final_chunks))]

    collection.add(
        ids=ids,
        documents=final_chunks,
        embeddings=embeddings,
        metadatas=final_metadatas
    )

    # 6. آپدیت وضعیت در Redis
    

    data = {
        "id": vs_file_id,
        "object": "vector_store.file",
        "vector_store_id": vector_store_id,
        "file_id": file_id,
        "created_at": int(time.time()),
        "status": "completed",
        "last_error": ""
    }

    await redis.hset(f"vector_store_file:{vs_file_id}", mapping=data)
    await redis.sadd(f"vector_store_files:{vector_store_id}", vs_file_id)

    return data
