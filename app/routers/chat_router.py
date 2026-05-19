# app\routers\chat_router.py
import uuid
import time
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas.responses_schema import ResponseRequest
from app.schemas.file_search import FileSearchQuery
from app.services.file_search import search_in_vector_store
from app.utility.build_prompt import build_rag_prompt_from_file_search
from app.utils import build_prompt, build_messages, convert_to_openai_format, fully_serialize
from app.services.llm_service import LLMService
from app.redis_client import get_redis
from app.token_counter import count_tokens
from app.auth import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


async def stream_response(r, request_id):

    pubsub = r.pubsub()
    

    try:

        await pubsub.subscribe(f"stream:{request_id}")

        async for msg in pubsub.listen():

            if msg["type"] != "message":
                continue

            data = msg["data"]

            if isinstance(data, bytes):
                data = data.decode()

            if data == "[DONE]":
                yield "data: [DONE]\n\n"
                break

            yield data

            if data.startswith("event: response.usage"):
                break
    except Exception as e:
        logger.error(f"Stream Error for request {request_id}: {str(e)}")
        yield f"data: {json.dumps({'error': 'Stream interrupted'})}\n\n"
    finally:
        await pubsub.unsubscribe(f"stream:{request_id}")
        await pubsub.close()


@router.post("/v1/responses")
async def create_response(
        req: ResponseRequest,
        user=Depends(get_api_key),
        r=Depends(get_redis)
):
    try:

        llm = LLMService(r)

        if not req.model:
            raise HTTPException(status_code=400, detail="Model field is required")

        input_is_list = isinstance(req.input, list)

        tool_messages_present = (
            input_is_list and
            any(getattr(msg, "role", None) == "tool" for msg in req.input)
        )

        tools_present = req.tools is not None and len(req.tools) > 0

        logger.debug(f"DEBUG: tool_messages_present={tool_messages_present} tools_present={tools_present}")

        # =========================================================
        # ✅ STAGE 2 — tool results received
        # =========================================================
        if tool_messages_present:

            messages = build_messages(req)
            
            serializable_messages = fully_serialize(messages)
            logger.debug(f"DEBUG: STAGE 2-------\n{serializable_messages}")
            payload = {
                "model": req.model,
                "messages": serializable_messages,
                "tool_choice": "none",   # مهم
                "stream": False,
                "options": {
                    "temperature": req.temperature,
                    "top_p": req.top_p,
                    "num_predict": req.max_output_tokens,
                },
            }
            result = await llm.tools_calling(payload)
            logger.debug(f"DEBUG RESULT:\n{result}")
            # چک کردن اینکه آیا سرویس LLM خطا برگردانده یا نه
            if not result or "error" in result:
                    error_msg = result.get("error", "Unknown LLM Error") if result else "LLM Service Unreachable"
                    logger.error(f"LLM Provider Error: {error_msg}")
                    raise HTTPException(status_code=502, detail=f"LLM Provider Error: {error_msg}")
            return convert_to_openai_format(result)


        # =========================================================
        # ✅ STAGE 1 — model should call tools
        # =========================================================
        if tools_present:
            # ===========================================
            # 1) Detect direct file_search usage
            # ===========================================
            file_search_tool = None
            for tool in req.tools:
                if tool.get("type") == "file_search":
                    vector_ids = tool.get("vector_store_ids")
                    # یعنی کاربر داده: "برو از این وکتور استورها جستجو کن"
                    if vector_ids and isinstance(vector_ids, list) and len(vector_ids) > 0:
                        file_search_tool = tool
                        break
            # ===========================================
            # 2) If direct file_search → RAG pipeline
            # ===========================================
            if file_search_tool is not None:
                print("START DEBUG DIRECT FILE SEARCH")
                # استخراج query
                if isinstance(req.input, list):
                    user_query = req.input[-1].text
                else:
                    user_query = req.input
                print(f"USER QUERY: {user_query}")
                # ساختن FileSearchQuery
                fs_query = FileSearchQuery(
                    vector_store_ids=file_search_tool["vector_store_ids"],
                    query=user_query,
                    max_results=file_search_tool.get("max_results", 5),
                    filters=file_search_tool.get("filters", None)
                )

                # اجرای retrieve
                try:
                    
                    fs_response = await search_in_vector_store(fs_query)

                    sources = []
                    for i, ch in enumerate(fs_response.results, start=1):
                        meta = ch.metadata or {}
                        sources.append({
                            "index": i,  # این با [منبع i] / [i] هم‌تراز است
                            "file_id": meta.get("file_id"),
                            "file_name": meta.get("file_name"),
                            "page_number": meta.get("page_number"),
                            "chunk_index": meta.get("chunk_index"),
                            "score": getattr(ch, "score", None),
                        })
                except Exception as e:
                    logger.error(f"Vector store search failed: {str(e)}")
                    raise HTTPException(
                        status_code=502,
                        detail="Vector store search failed"
                    )

                # تبدیل چانک‌ها به context
                rag_prompt = build_rag_prompt_from_file_search(user_query, fs_response)
                print(f"Len RAG Prompt: {len(rag_prompt)}")
                # صدا زدن مدل با RAG prompt
                input_tokens = count_tokens(rag_prompt)
                print(f"input token: {input_tokens}")
                payload = {
                    "model": req.model,
                    "prompt": rag_prompt,
                    "stream": False,
                    "options": {
                        "temperature": req.temperature,
                        "top_p": req.top_p,
                        "num_predict": req.max_output_tokens,
                    },
                }

                result = await llm.generate(payload)
                if not result or "error" in result:
                    logger.error("LLM Generation failed after RAG retrieval")
                    raise HTTPException(
                        status_code=502,
                        detail="LLM Generation failed"
                    )
                print(f"RAW RESPONSE {result}")
                output = result.get("response", "") if isinstance(result, dict) else str(result)
                output_tokens = count_tokens(output)
                print("END DEBUG DIRECT FILE SEARCH")
                # خروجی نهایی استاندارد OpenAI
                return JSONResponse({
                    "id": f"resp_{uuid.uuid4().hex}",
                    "object": "response",
                    "created": int(time.time()),
                    "model": req.model,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    "output": [{
                        "id": f"msg_{uuid.uuid4().hex}",
                        "type": "message",
                        "role": "assistant",
                        "content": [{
                            "type": "output_text",
                            "text": output
                        }],
                        "citations": sources
                    }]
                })

            # ===========================================
            # 3) Other tools → normal model-driven tool calling
            # ===========================================
            else:
                messages = build_messages(req)
                
                serializable_messages = fully_serialize(messages)
                logger.debug(f"DEBUG: STAGE 1-------\n{serializable_messages}")
                payload = {
                    "model": req.model,
                    "messages": serializable_messages,
                    "stream": False,
                    "tools": req.tools,
                    "tool_choice": req.tool_choice,
                    "options": {
                        "temperature": req.temperature,
                        "top_p": req.top_p,
                        "num_predict": req.max_output_tokens,
                    },
                }

                result = await llm.tools_calling(payload)

                if not result or "error" in result:
                        logger.error("LLM failed to process tool calls")
                        raise HTTPException(status_code=502, detail="LLM failed to process tool calls")
                
                msg = result.get("message", {}) if isinstance(result, dict) else {}
                tool_calls = msg.get("tool_calls") or []

                openai_tool_calls = []
                for tc in tool_calls:
                    try:
                        fn = tc.get("function", {})
                        openai_tool_calls.append({
                            "type": "function_call",
                            "id": tc.get("id"),
                            "call_id": tc.get("id"),
                            "name": fn.get("name"),
                            "arguments": json.dumps(fn.get("arguments", {})),
                        })
                    except Exception as e:
                            logger.warning(f"Skipping malformed tool call: {str(e)}")
                            continue

                return JSONResponse({
                    "id": f"resp_{uuid.uuid4().hex}",
                    "object": "response",
                    "created": int(time.time()),
                    "model": req.model,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                    "output": openai_tool_calls,
                })


        # =========================================================
        # ✅ NORMAL TEXT GENERATION (non-stream)
        # =========================================================
        if not req.stream:

            prompt = build_prompt(req)
            input_tokens = count_tokens(prompt)

            payload = {
                "model": req.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": req.temperature,
                    "top_p": req.top_p,
                    "num_predict": req.max_output_tokens
                }
            }

            result = await llm.generate(payload)
            if not result or "error" in result:
                    logger.error("LLM Generation failed")
                    raise HTTPException(status_code=502, detail="LLM Generation failed")
            
            output = result.get("response", "") if isinstance(result, dict) else str(result)
            output_tokens = count_tokens(output)

            return JSONResponse({
                "id": f"resp_{uuid.uuid4().hex}",
                "object": "response",
                "created": int(time.time()),
                "model": req.model,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                },
                "output": [{
                    "id": f"msg_{uuid.uuid4().hex}",
                    "type": "message",
                    "role": "assistant",
                    "content": [{
                        "type": "output_text",
                        "text": output
                    }]
                }]
            })


        # =========================================================
        # ✅ STREAM MODE (only normal text)
        # =========================================================
        request_id = uuid.uuid4().hex

        prompt = build_prompt(req)
        input_tokens = count_tokens(prompt)

        payload = {
            "model": req.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": req.temperature,
                "top_p": req.top_p,
                "num_predict": req.max_output_tokens
            }
        }

        try:
            await r.ping()
        except Exception:
            logger.error("Messaging queue (Redis) is unavailable")
            raise HTTPException(status_code=503, detail="Messaging queue (Redis) is unavailable")
        
        await llm.enqueue_stream(
            request_id,
            payload,
            user["user_id"],
            input_tokens
        )

        return StreamingResponse(
            stream_response(r, request_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    except HTTPException as he:
            # خطاهای مدیریت شده (مثل ۴۰۰ یا ۴۰۱) مستقیماً پاس داده می‌شوند
            raise he
    except Exception as e:
        # خطاهای پیش‌بینی نشده لاگ می‌شوند و یک پاسخ تمیز ۵۰۰ برمی‌گردانند
        logger.error(f"UNHANDLED ERROR in Chat Router: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred", "message": str(e)}
        )
