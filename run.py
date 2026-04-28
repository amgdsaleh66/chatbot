#!/usr/bin/env python3
"""
run.py - نقطة تشغيل الخادم
الاستخدام: python run.py
"""
import os
import sys

# التأكد من وجود ملف .env
if not os.path.exists(".env"):
    if os.path.exists(".env.example"):
        print("⚠️  ملف .env غير موجود!")
        print("   انسخ .env.example إلى .env وعيّن MISTRAL_API_KEY:")
        print("   cp .env.example .env")
        print("   nano .env")
        print()
        # إنشاء .env تلقائياً من المثال للتجربة الأولى
        import shutil
        shutil.copy(".env.example", ".env")
        print("✅ تم إنشاء .env من المثال — يرجى تعديل MISTRAL_API_KEY")
    else:
        print("❌ ملف .env و .env.example غير موجودَين!")
        sys.exit(1)

# إنشاء المجلدات المطلوبة
for d in ["data", "data/uploads", "frontend"]:
    os.makedirs(d, exist_ok=True)

# ─── تشغيل uvicorn ───────────────────────────────────────────────────
import uvicorn
from app.config import settings

print("=" * 55)
print("  🤖 AI Support Platform MVP — Termux Edition")
print("=" * 55)
print(f"  🌐 URL      : http://localhost:{settings.PORT}")
print(f"  📖 API Docs : http://localhost:{settings.PORT}/api/docs")
print(f"  🔑 Demo     : {settings.DEMO_USERNAME} / {settings.DEMO_PASSWORD}")
print(f"  🤖 Model    : {settings.CHAT_MODEL}")
print(f"  🔍 FAISS    : {settings.FAISS_INDEX_PATH}")
mistral_ok = "✅ مُعيَّن" if settings.MISTRAL_API_KEY else "❌ مفقود — أضفه في .env"
print(f"  🗝️  API Key  : {mistral_ok}")
print("=" * 55)
print()

if not settings.MISTRAL_API_KEY:
    print("⚠️  تحذير: MISTRAL_API_KEY غير معيّن.")
    print("   الدردشة لن تعمل. أضف مفتاحك في ملف .env")
    print()

uvicorn.run(
    "app.main:app",
    host=settings.HOST,
    port=settings.PORT,
    reload=settings.RELOAD,
    log_level="info",
    ws_ping_interval=20,
    ws_ping_timeout=30,
)