"""
main.py - التطبيق الرئيسي FastAPI
يتضمن: المصادقة، WebSocket، رفع المستندات، سجل المحادثات
"""
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from .chat import handle_websocket
from .config import settings
from .document_ingestion import process_upload
from .memory import session_memory
from .models import (
    AsyncSessionLocal,
    Conversation,
    Document,
    Message,
    User,
    get_db,
    init_db,
)
from .rag import rag_engine

# ─── إنشاء المجلدات ─────────────────────────────────────────────
for _dir in ["./data", "./data/uploads", "./data/faiss_index"]:
    os.makedirs(os.path.dirname(_dir) if not _dir.endswith("/") else _dir, exist_ok=True)
os.makedirs("./data", exist_ok=True)
os.makedirs("./data/uploads", exist_ok=True)


# ─── Lifespan ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """تهيئة DB وإنشاء المستخدم التجريبي عند بدء التشغيل"""
    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == settings.DEMO_USERNAME)
        )
        if not result.scalar_one_or_none():
            demo = User(
                username=settings.DEMO_USERNAME,
                hashed_password=get_password_hash(settings.DEMO_PASSWORD),
            )
            db.add(demo)
            await db.commit()
            print(
                f"✅ المستخدم التجريبي: "
                f"{settings.DEMO_USERNAME} / {settings.DEMO_PASSWORD}"
            )
        else:
            print(f"✅ المستخدم التجريبي [{settings.DEMO_USERNAME}] موجود مسبقاً")

    print("🚀 AI Support MVP جاهز على http://localhost:8000")
    yield
    print("👋 إيقاف الخادم")


# ─── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Support Platform MVP",
    description="منصة دعم العملاء بالذكاء الاصطناعي — بدون Docker",
    version="1.0.0-mvp",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Models ────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class RegisterRequest(BaseModel):
    username: str
    password: str


# ─── Auth Routes ────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """تسجيل الدخول والحصول على JWT"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=token, username=user.username)


@app.post("/api/auth/register", response_model=TokenResponse, tags=["Auth"])
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """تسجيل مستخدم جديد"""
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="اسم المستخدم مأخوذ بالفعل")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")

    user = User(username=req.username, hashed_password=get_password_hash(req.password))
    db.add(user)
    await db.commit()

    token = create_access_token(data={"sub": req.username})
    return TokenResponse(access_token=token, username=req.username)


@app.get("/api/auth/me", tags=["Auth"])
async def me(current_user: User = Depends(get_current_user)):
    """بيانات المستخدم الحالي"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "created_at": current_user.created_at.isoformat(),
    }


# ─── WebSocket ──────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """نقطة نهاية WebSocket للدردشة"""
    await handle_websocket(websocket)


# ─── Documents ──────────────────────────────────────────────────

@app.post("/api/documents/upload", tags=["Documents"])
async def upload_doc(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """رفع مستند PDF أو TXT وفهرسته في RAG"""
    return await process_upload(file, db)


@app.get("/api/documents", tags=["Documents"])
async def list_docs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """قائمة المستندات المرفوعة"""
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size_kb": round(d.file_size / 1024, 2) if d.file_size else 0,
            "chunks": d.chunk_count,
            "is_indexed": d.is_indexed,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


@app.delete("/api/documents/{doc_id}", tags=["Documents"])
async def delete_doc(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """حذف مستند من DB (لا يحذف من FAISS في MVP)"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")

    # حذف الملف الفعلي
    file_path = os.path.join(settings.UPLOADS_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": "تم حذف المستند", "note": "FAISS index لم يتحدث (يتطلب إعادة الفهرسة)"}


# ─── RAG ────────────────────────────────────────────────────────

@app.get("/api/rag/stats", tags=["RAG"])
async def rag_stats(current_user: User = Depends(get_current_user)):
    """إحصائيات فهرس RAG"""
    return rag_engine.get_stats()


@app.post("/api/rag/search", tags=["RAG"])
async def rag_search(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """بحث يدوي في RAG (للاختبار)"""
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="يجب إرسال query")
    results = await rag_engine.search(query)
    return [
        {"text": t, "source": s, "distance": d}
        for t, s, d in results
    ]


# ─── Conversations ───────────────────────────────────────────────

@app.get("/api/conversations", tags=["Conversations"])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """سجل محادثات المستخدم"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
        }
        for c in convs
    ]


@app.get("/api/conversations/{conv_id}/messages", tags=["Conversations"])
async def get_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """رسائل محادثة معينة"""
    # التحقق من الملكية
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="المحادثة غير موجودة")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in msgs
    ]


# ─── Health ──────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health():
    """فحص حالة النظام"""
    return {
        "status": "ok",
        "mistral_key_set": bool(settings.MISTRAL_API_KEY),
        "rag": rag_engine.get_stats(),
        "active_sessions": session_memory.get_active_count(),
    }


# ─── Frontend Serving ─────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("./frontend/index.html")


@app.get("/chat.js", include_in_schema=False)
async def serve_js():
    return FileResponse("./frontend/chat.js", media_type="application/javascript")