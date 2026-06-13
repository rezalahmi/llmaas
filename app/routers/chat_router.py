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
from app.services.quota_service import consume_api_key_quota_service
from app.redis_client import get_redis
from app.token_counter import count_tokens
from app.auth import get_api_key
from app.postgres_client import get_pg

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Response"]
)


async def stream_response(r, conn, key_id, request_id, citations=None):

    pubsub = r.pubsub()
    
    print(f"[STREAM] Opening stream for request_id={request_id}")
    try:

        await pubsub.subscribe(f"stream:{request_id}")
        print(f"[STREAM] Subscribed to channel stream:{request_id}")

        async for msg in pubsub.listen():

            print(f"[STREAM] RAW REDIS MSG: {msg}")

            if msg["type"] != "message":
                continue

            data = msg["data"]

            if isinstance(data, bytes):
                data = data.decode()

            print(f"[STREAM] DATA RECEIVED: {data[:300]}")


            if data == "[DONE]":
                
                print("[STREAM] Received DONE from worker")
                
                if citations:
                
                    print("[STREAM] Sending citations after usage")
                
                    yield (
                        "event: response.citations\n"
                        f"data: {json.dumps({'citations': citations}, ensure_ascii=False)}\n\n"
                    )
                
                yield "data: [DONE]\n\n"
                
                break

            yield data

            if data.startswith("event: response.usage"):
                
                print("[STREAM] Usage event received")
                try:
                    # فرمت معمول: event: response.usage\ndata: {"total_tokens": 150, ...}
                    json_str = data.split("data: ")[1]
                    usage_data = json.loads(json_str)
                    total_tokens = usage_data.get("total_tokens", 0)

                    if total_tokens > 0:
                        await consume_api_key_quota_service(
                            conn,
                            key_id=key_id,
                            amount=total_tokens,
                            reason="chat_stream",
                            reference_id=f"stream_{request_id}"
                        )
                except Exception as e:
                    logging.error(f"Failed to consume quota in stream: {e}")
                
                if citations:
                    
                    print("[STREAM] Sending citations event")
                    
                    yield (
                        "event: response.citations\n"
                        f"data: {json.dumps({'citations': citations}, ensure_ascii=False)}\n\n"
                    )

                print("[STREAM] Stream finished after usage")
                
                yield "data: [DONE]\n\n"
                
                break
    except Exception as e:
        logger.error(f"Stream Error for request {request_id}: {str(e)}")
        yield f"data: {json.dumps({'error': 'Stream interrupted'})}\n\n"
    finally:
        logger.info(f"[STREAM] Closing stream for request_id={request_id}")

        await pubsub.unsubscribe(f"stream:{request_id}")

        await pubsub.close()


@router.post("/v1/responses")
async def create_response(
        req: ResponseRequest,
        user=Depends(get_api_key),
        r=Depends(get_redis),
        conn=Depends(get_pg)
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
            
            # 1) Build messages
            messages = build_messages(req)
            
            serializable_messages = fully_serialize(messages)
            logger.debug(f"DEBUG: STAGE 2-------\n{serializable_messages}")
            # 2) Count input tokens (برای پیام‌ها)
            input_tokens = count_tokens(json.dumps(serializable_messages, ensure_ascii=False))
            # 3) Call LLM (non-stream always)
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
            # 4) Extract output text
            output_text = ""
            try:
                msg = result.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list) and len(content) > 0:
                    output_text = content[0].get("text", "") or ""
                elif isinstance(content, str):
                    output_text = content
            except Exception:
                output_text = ""
            # 5) Count output tokens
            output_tokens = count_tokens(output_text)

            # 6) Total tokens
            total_tokens = input_tokens + output_tokens
             # 7) Consume quota  (اصلی‌ترین بخش)
            try:
                await consume_api_key_quota_service(
                    conn,
                    key_id=user["key_id"],
                    amount=total_tokens,
                    reason="tool_call_final",
                    reference_id=f"tc_final_{uuid.uuid4().hex}"
                )
            except HTTPException as e:
                # اگر quota کافی نبود، بهتر است پیام مدل را هم ندهیم
                if e.status_code == 402:
                    raise HTTPException(status_code=402, detail="Insufficient quota for tool completion")
                raise
             # 8) Build OpenAI-compatible response
            formatted = convert_to_openai_format(result)

            # 9) اضافه کردن usage واقعی
            formatted["usage"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            }

            return formatted


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
                # استخراج query
                if isinstance(req.input, list):
                    user_query = req.input[-1].text
                else:
                    user_query = req.input
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
                            "sheet": meta.get("sheet"),
                            "row": meta.get("row"),
                            "slide_number":meta.get("slide_number")
                        })
                except Exception as e:
                    logger.error(f"Vector store search failed: {str(e)}")
                    raise HTTPException(
                        status_code=502,
                        detail="Vector store search failed"
                    )
                # تبدیل چانک‌ها به context
                rag_prompt = build_rag_prompt_from_file_search(user_query, fs_response)
                # صدا زدن مدل با RAG prompt
                input_tokens = count_tokens(rag_prompt)
                if not req.stream:
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
                    output = result.get("response", "") if isinstance(result, dict) else str(result)
                    output_tokens = count_tokens(output)
                    total_tokens = input_tokens + output_tokens

                    # ✅ debit quota
                    await consume_api_key_quota_service(
                        conn,
                        key_id=user["key_id"],
                        amount=total_tokens,
                        reason="rag_completion",
                        reference_id=f"rag_{uuid.uuid4().hex}"
                    )
                    # خروجی نهایی استاندارد OpenAI
                    return JSONResponse({
                        "id": f"resp_{uuid.uuid4().hex}",
                        "object": "response",
                        "created": int(time.time()),
                        "model": req.model,
                        "usage": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
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
                if req.stream:
                    # همون منطق استریم معمولی، فقط prompt همون rag_prompt است
                    request_id = uuid.uuid4().hex

                    payload = {
                        "model": req.model,
                        "prompt": rag_prompt,
                        "stream": True,
                        "options": {
                            "temperature": req.temperature,
                            "top_p": req.top_p,
                            "num_predict": req.max_output_tokens,
                        },
                    }
                    print(f"[RAG STREAM] request_id={request_id}")
                    print(f"[RAG STREAM] model={req.model}")
                    print(f"[RAG STREAM] input_tokens={input_tokens}")
                    print(f"[RAG STREAM] citations_count={len(sources)}")
                    # فقط preview از prompt
                    print(f"[RAG STREAM] prompt_preview={rag_prompt[:500]}")
                    # چک Redis
                    try:
                        await r.ping()
                        print("[RAG STREAM] Redis connection OK")
                    except Exception as e:
                        logger.error(f"[RAG STREAM] Redis unavailable: {str(e)}")
                        raise HTTPException(status_code=503, detail="Messaging queue (Redis) is unavailable")

                    # enqueue برای worker مدل
                    await llm.enqueue_stream(
                        request_id,
                        payload,
                        user["user_id"],
                        input_tokens
                    )
                    print("[RAG STREAM] enqueue_stream DONE")
                    # StreamingResponse که هم متن و هم citation را برمی‌گرداند
                    return StreamingResponse(
                        stream_response(r, conn, user["key_id"], request_id, sources),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive"
                        }
                    )
                     

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
                            "arguments": json.dumps(fn.get("arguments", {}), ensure_ascii=False),
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
            total_tokens = input_tokens + output_tokens
             # ✅ debit quota اضافه شد
            await consume_api_key_quota_service(
                conn,
                key_id=user["key_id"],
                amount=total_tokens,
                reason="chat_completion",
                reference_id=f"resp_{uuid.uuid4().hex}"
            )
            return JSONResponse({
                "id": f"resp_{uuid.uuid4().hex}",
                "object": "response",
                "created": int(time.time()),
                "model": req.model,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens
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
        print(f"DEBUG CHAT ROUTER prompt: {prompt}")
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
            stream_response(r=r, conn=conn, key_id=user["key_id"],request_id= request_id),
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
