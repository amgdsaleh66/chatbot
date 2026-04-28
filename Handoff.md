# Project Handoff Context (MVP Termux)

---

## ✅ Completed Features

| الميزة | الحالة | الملف |
|--------|--------|-------|
| FastAPI + Uvicorn | ✅ مكتمل | `app/main.py`, `run.py` |
| WebSocket Streaming | ✅ مكتمل | `app/chat.py` |
| مصادقة JWT | ✅ مكتمل | `app/auth.py` |
| SQLite + SQLAlchemy Async | ✅ مكتمل | `app/models.py` |
| RAG مع FAISS + Mistral Embed | ✅ مكتمل | `app/rag.py` |
| رفع PDF/TXT + فهرسة | ✅ مكتمل | `app/document_ingestion.py` |
| جلسات في الذاكرة | ✅ مكتمل | `app/memory.py` |
| Mistral Chat Streaming | ✅ مكتمل | `app/chat.py` |
| واجهة دردشة HTML/JS | ✅ مكتمل | `frontend/` |
| مستخدم تجريبي تلقائي | ✅ مكتمل | `app/main.py` (lifespan) |
| سجل المحادثات | ✅ مكتمل | `app/models.py`, `/api/conversations` |
| Swagger UI | ✅ مكتمل | `/api/docs` |
| CORS | ✅ مكتمل | `app/main.py` |

---

## 🗂 هيكل المشروع النهائي

```
ai-support-mvp-termux/
├── run.py                    ← نقطة الدخول
├── requirements.txt          ← المكتبات
├── .env.example              ← قالب البيئة
├── README.md                 ← التوثيق الكامل
├── app/
│   ├── __init__.py
│   ├── config.py             ← Settings من .env
│   ├── models.py             ← User, Conversation, Message, Document
│   ├── auth.py               ← bcrypt + JWT + Bearer
│   ├── memory.py             ← SessionMemory (in-memory)
│   ├── rag.py                ← RAGEngine (FAISS + Mistral Embed API)
│   ├── document_ingestion.py ← PDF/TXT → chunks → FAISS
│   ├── chat.py               ← WebSocket handler + Mistral streaming
│   ├── main.py               ← FastAPI app + all routes
│   └── utils.py              ← دوال مساعدة
├── frontend/
│   ├── index.html            ← SPA (login + chat UI)
│   └── chat.js               ← WebSocket client + streaming renderer
├── data/                     ← يُنشأ تلقائياً
│   ├── support.db
│   ├── faiss_index.faiss
│   ├── faiss_index_meta.json
│   └── uploads/
└── migrations/
    └── __init__.py
```

---

## 🔑 متغيرات البيئة المطلوبة

```env
# مطلوب - مفتاح Mistral
MISTRAL_API_KEY=sk-...

# أمان
SECRET_KEY=random-long-secret-string

# اختياري (مع قيم افتراضية)
DEMO_USERNAME=demo
DEMO_PASSWORD=demo123
CHAT_MODEL=mistral-small-latest
HOST=0.0.0.0
PORT=8000
RELOAD=false
```

---

## 🚀 كيفية التشغيل خطوة بخطوة (Termux)

```bash
# 1. في Ubuntu proot:
apt update && apt install -y python3 python3-pip python3-venv \
  build-essential libssl-dev libffi-dev

# 2. استنساخ أو نسخ المشروع
cd ai-support-mvp-termux

# 3. البيئة الافتراضية
python3 -m venv venv
source venv/bin/activate

# 4. المكتبات
pip install --upgrade pip
pip install -r requirements.txt

# 5. البيئة
cp .env.example .env
# عدّل MISTRAL_API_KEY في .env

# 6. التشغيل
python run.py

# 7. افتح في المتصفح (من Android):
#    http://localhost:8000
```

---

## ⚠️ القيود الحالية

### 1. قاعدة البيانات: SQLite
- **السبب:** تعمل بدون خادم في Termux
- **التأثير:** لا تدعم concurrent writes جيداً عند التحميل العالي
- **الحل:** استبدل بـ PostgreSQL في الإنتاج

### 2. الجلسات: في الذاكرة
- **السبب:** Redis معقد التثبيت في Termux
- **التأثير:** تضيع الجلسات عند إعادة تشغيل الخادم
- **الحل:** Redis + aioredis

### 3. FAISS: محلي على القرص
- **السبب:** لا حاجة لإنترنت أو اشتراك
- **التأثير:** لا يدعم horizontal scaling
- **الحل:** Pinecone / Qdrant / Weaviate

### 4. المصادقة: بسيطة
- **السبب:** MVP للاختبار
- **التأثير:** مستخدم تجريبي واحد، لا نظام أدوار
- **الحل:** نظام مستخدمين كامل + أدوار + OAuth

### 5. لا Rate Limiting
- **السبب:** MVP
- **الحل:** `slowapi` أو Nginx rate limiting

### 6. حذف FAISS غير مدعوم
- عند حذف مستند، يُحذف من DB لكن تبقى قطعه في FAISS
- **الحل:** إعادة بناء الفهرس بعد الحذف (endpoint مخطط للمرحلة 2)

---

## 🗺 نقاط الانطلاق للمرحلة الثانية

### أولوية عالية
1. **Tool Calling** — Mistral Function Calling لإجراء عمليات (فتح تذاكر، استعلام DB)
2. **نظام التصعيد** — تحليل المشاعر → تصعيد لوكيل بشري
3. **تعدد المستأجرين** — Multi-tenancy مع عزل البيانات
4. **لوحة إدارة** — Dashboard للمشرفين

### أولوية متوسطة
5. **زحف الويب** — إضافة محتوى الموقع لقاعدة المعرفة تلقائياً
6. **ذاكرة طويلة المدى** — تلخيص المحادثات القديمة
7. **تقييم الإجابات** — 👍/👎 لتحسين الأداء
8. **Redis للجلسات** — استمرارية عبر إعادة التشغيل

### أولوية منخفضة
9. **WebPush / Email إشعارات**
10. **تحليلات المحادثات**
11. **A/B testing للنماذج**

---

## 🔧 التغييرات المطلوبة للإنتاج

### 1. استبدال SQLite بـ PostgreSQL
```python
# .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_support

# requirements.txt — أضف:
asyncpg>=0.29.0
```

### 2. إضافة Redis للجلسات
```python
# app/memory.py — استبدل SessionMemory بـ:
import aioredis
redis = aioredis.from_url("redis://localhost")

# .env
REDIS_URL=redis://localhost:6379
```

### 3. استبدال FAISS بـ Pinecone
```python
# app/rag.py — استبدل RAGEngine بـ Pinecone client
import pinecone
pinecone.init(api_key="...", environment="us-west1-gcp")
index = pinecone.Index("ai-support")
```

### 4. نشر بـ Gunicorn
```bash
pip install gunicorn
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### 5. Nginx كـ Reverse Proxy
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";  # مهم لـ WebSocket
        proxy_set_header Host $host;
    }
}
```

### 6. SSL مع Certbot
```bash
certbot --nginx -d yourdomain.com
```

### 7. متغيرات الأمان للإنتاج
```env
SECRET_KEY=<64-character-random-hex>
DEMO_PASSWORD=<strong-password>
RELOAD=false
```

---

## 📊 تدفق النظام

```
المستخدم (Browser)
    │
    │ HTTP GET /
    ▼
FastAPI → frontend/index.html
    │
    │ POST /api/auth/login → JWT Token
    │
    │ WS /ws/chat
    ▼
WebSocket Handler (chat.py)
    ├── auth: verify JWT
    ├── إنشاء Conversation في SQLite
    ├── إنشاء Session في الذاكرة
    │
    │ على كل رسالة:
    ├── RAG Search (FAISS + Mistral Embed)
    ├── بناء Context (آخر 10 رسائل + RAG)
    ├── Mistral Chat API (streaming)
    └── حفظ في SQLite
```

---

*آخر تحديث: MVP — جاهز للاختبار في Termux/Ubuntu*