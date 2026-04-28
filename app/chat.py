"""
chat.py - معالج WebSocket مع Streaming من Mistral API
"""
import json
import uuid
from typing import AsyncGenerator

import httpx
from fastapi import WebSocket, WebSocketDisconnect

from .auth import get_current_user_ws
from .config import settings
from .memory import session_memory
from .models import AsyncSessionLocal, Conversation, Message
from .rag import rag_engine

# ─── System Prompt ─────────────────────────────────────────────────
SYSTEM_PROMPT = """أنت مساعد ذكي لدعم العملاء. مهمتك مساعدة المستخدمين في حل مشاكلهم بكفاءة.

قواعد التعامل:
- أجب بنفس لغة المستخدم (عربي أو إنجليزي أو غيرها).
- كن مختصراً ودقيقاً ولطيفاً.
- إذا لم تعرف الإجابة، قل ذلك بصراحة واقترح تصعيد الطلب.
- استخدم المعلومات من قاعدة المعرفة عند توفرها.
- لا تختلق معلومات غير موجودة في السياق."""


def build_messages_with_context(
    history: list,
    rag_context: str = "",
) -> list:
    """بناء قائمة الرسائل مع السياق من RAG"""
    system_content = SYSTEM_PROMPT
    if rag_context:
        system_content += f"\n\n## معلومات من قاعدة المعرفة:\n{rag_context}"

    return [{"role": "system", "content": system_content}] + history


async def stream_mistral(
    messages: list,
    rag_context: str = "",
) -> AsyncGenerator[str, None]:
    """
    Async generator يرسل الاستجابة chunk بـ chunk من Mistral API.
    """
    full_messages = build_messages_with_context(messages, rag_context)

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        async with client.stream(
            "POST",
            f"{settings.MISTRAL_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.CHAT_MODEL,
                "messages": full_messages,
                "stream": True,
                "max_tokens": 1024,
                "temperature": 0.7,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    return
                try:
                    chunk_data = json.loads(raw)
                    delta = chunk_data["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


# ─── WebSocket Handler ─────────────────────────────────────────────

async def handle_websocket(websocket: WebSocket):
    """
    معالج الاتصال الكامل:
    1. قبول الاتصال
    2. التحقق من الهوية (JWT)
    3. إنشاء جلسة + محادثة
    4. حلقة الرسائل مع RAG + Streaming
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())

    # ── Step 1: Authentication ──────────────────────────────────────
    try:
        auth_msg = await websocket.receive_json()
    except Exception:
        await websocket.close(code=1003, reason="Invalid initial message")
        return

    if auth_msg.get("type") != "auth":
        await websocket.send_json(
            {"type": "error", "message": "الرسالة الأولى يجب أن تكون auth"}
        )
        await websocket.close(code=4001)
        return

    token = auth_msg.get("token", "")
    async with AsyncSessionLocal() as db:
        user = await get_current_user_ws(token, db)

    if not user:
        await websocket.send_json(
            {"type": "error", "message": "رمز المصادقة غير صالح أو منتهي"}
        )
        await websocket.close(code=4003)
        return

    # ── Step 2: Create Session & Conversation ───────────────────────
    session_memory.create_session(session_id, user.id, user.username)

    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=user.id, title="محادثة دعم")
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conversation_id = conv.id

    session_memory.set_conversation_id(session_id, conversation_id)

    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "username": user.username,
        "conversation_id": conversation_id,
        "message": f"مرحباً {user.username}! كيف يمكنني مساعدتك؟",
    })

    print(f"🔌 WS: مستخدم [{user.username}] متصل — جلسة [{session_id[:8]}...]")

    # ── Step 3: Message Loop ────────────────────────────────────────
    try:
        while True:
            try:
                data = await websocket.receive_json()
            except Exception:
                break

            msg_type = data.get("type")

            # ── Ping/Pong ───────────────────────────────────────────
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # ── Chat Message ────────────────────────────────────────
            if msg_type != "message":
                continue

            user_text = (data.get("content") or "").strip()
            if not user_text:
                continue

            # حفظ رسالة المستخدم في DB
            async with AsyncSessionLocal() as db:
                db.add(Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_text,
                ))
                await db.commit()

            # إضافة إلى ذاكرة السياق
            session_memory.add_message_to_context(session_id, "user", user_text)
            context = session_memory.get_context(session_id, max_messages=10)

            # RAG Search
            rag_context = ""
            try:
                results = await rag_engine.search(user_text)
                if results:
                    parts = []
                    for text, source, dist in results:
                        parts.append(f"[المصدر: {source}]\n{text}")
                    rag_context = "\n\n---\n\n".join(parts)
            except Exception as rag_err:
                print(f"⚠️  RAG error: {rag_err}")

            # Streaming Response
            await websocket.send_json({"type": "start_stream", "rag_used": bool(rag_context)})

            full_response = ""
            error_occurred = False

            try:
                async for chunk in stream_mistral(context, rag_context):
                    full_response += chunk
                    await websocket.send_json({"type": "stream_chunk", "content": chunk})
            except httpx.HTTPStatusError as e:
                error_occurred = True
                err_detail = f"Mistral API error: {e.response.status_code}"
                try:
                    err_detail += f" — {e.response.json().get('message', '')}"
                except Exception:
                    pass
                await websocket.send_json({"type": "error", "message": err_detail})
            except Exception as e:
                error_occurred = True
                await websocket.send_json({"type": "error", "message": f"خطأ: {str(e)}"})

            await websocket.send_json({"type": "end_stream"})

            if not error_occurred and full_response:
                # حفظ رد المساعد في DB
                async with AsyncSessionLocal() as db:
                    db.add(Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_response,
                    ))
                    await db.commit()

                session_memory.add_message_to_context(session_id, "assistant", full_response)

    except WebSocketDisconnect:
        print(f"🔌 WS: مستخدم [{user.username}] قطع الاتصال")
    except Exception as e:
        print(f"❌ WS error [{session_id[:8]}]: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        session_memory.delete_session(session_id)
        print(f"🧹 Session [{session_id[:8]}] cleaned up")