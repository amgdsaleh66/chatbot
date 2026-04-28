# 🤖 AI Support Platform MVP — Termux Edition

منصة دعم العملاء بالذكاء الاصطناعي — مصممة للعمل في **Termux + Ubuntu proot** (أو أي Ubuntu عادي) **بدون Docker**.

---

## 🗂 هيكل المشروع

```
ai-support-mvp-termux/
├── run.py                    ← نقطة التشغيل الرئيسية
├── requirements.txt
├── .env.example              ← انسخه إلى .env وعدّل المفاتيح
├── app/
│   ├── main.py               ← FastAPI + جميع المسارات
│   ├── config.py             ← إعدادات البيئة
│   ├── models.py             ← SQLAlchemy + SQLite
│   ├── auth.py               ← JWT
│   ├── chat.py               ← WebSocket + Streaming Mistral
│   ├── rag.py                ← FAISS + Mistral Embeddings
│   ├── document_ingestion.py ← معالجة PDF/TXT
│   ├── memory.py             ← جلسات في الذاكرة
│   └── utils.py
├── frontend/
│   ├── index.html            ← واجهة الدردشة
│   └── chat.js               ← WebSocket Client
├── data/                     ← يُنشأ تلقائياً
│   ├── support.db            ← SQLite
│   ├── faiss_index.faiss     ← فهرس المتجهات
│   └── uploads/              ← الملفات المرفوعة
└── migrations/
```

---

## ⚡ التثبيت والتشغيل

### 1. المتطلبات الأساسية

**في Ubuntu proot (Termux):**
```bash
# تحديث الحزم
apt update && apt upgrade -y

# Python وأدوات البناء
apt install -y python3 python3-pip python3-venv git

# مكتبات C المطلوبة لبعض packages
apt install -y build-essential libssl-dev libffi-dev \
               libxml2-dev libxslt1-dev zlib1g-dev \
               libjpeg-dev libpng-dev
```

**في Termux مباشرةً (بدون proot):**
```bash
pkg update && pkg upgrade -y
pkg install python python-pip git build-essential
pkg install binutils libxml2 libxslt libjpeg-turbo
```

---

### 2. استنساخ المشروع

```bash
git clone <your-repo-url> ai-support-mvp-termux
cd ai-support-mvp-termux

# أو انسخ المجلد مباشرةً
```

---

### 3. إنشاء البيئة الافتراضية

```bash
python3 -m venv venv
source venv/bin/activate
# (في Windows: venv\Scripts\activate)
```

---

### 4. تثبيت المكتبات

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **ملاحظة Termux:** إذا فشل تثبيت `faiss-cpu`:
> ```bash
> pip install faiss-cpu --no-binary faiss-cpu
> # أو جرّب:
> FAISS_DISABLE_MKL=ON pip install faiss-cpu
> ```
> إذا استمر الفشل، يمكنك تشغيل المشروع بدون RAG (الدردشة ستعمل بدون قاعدة معرفة).

---

### 5. إعداد متغيرات البيئة

```bash
cp .env.example .env
nano .env   # أو: vi .env
```

**الحد الأدنى المطلوب:**
```env
MISTRAL_API_KEY=your_actual_api_key_here
SECRET_KEY=any-random-long-string-here
```

احصل على مفتاح Mistral من: https://console.mistral.ai/

---

### 6. تشغيل الخادم

```bash
python run.py
```

**المخرجات المتوقعة:**
```
=======================================================
  🤖 AI Support Platform MVP — Termux Edition
=======================================================
  🌐 URL      : http://localhost:8000
  📖 API Docs : http://localhost:8000/api/docs
  🔑 Demo     : demo / demo123
  🤖 Model    : mistral-small-latest
  🔍 FAISS    : ./data/faiss_index
  🗝️  API Key  : ✅ مُعيَّن
=======================================================
✅ المستخدم التجريبي: demo / demo123
✅ Database initialized
🚀 AI Support MVP جاهز على http://localhost:8000
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

### 7. فتح الواجهة

افتح المتصفح على:
```
http://localhost:8000
```

**بيانات الدخول التجريبية:**
- المستخدم: `demo`
- كلمة المرور: `demo123`

---

## 🗺 استخدام المنصة

### الدردشة
1. سجّل الدخول بالبيانات التجريبية
2. اكتب سؤالك في مربع النص
3. اضغط Enter أو زر الإرسال
4. ستظهر الإجابة تدريجياً (streaming)

### رفع المستندات (قاعدة المعرفة)
1. من الشريط الجانبي → "قاعدة المعرفة"
2. اضغط على منطقة الرفع
3. اختر ملف PDF أو TXT
4. انتظر رسالة "تم الفهرسة"
5. الأسئلة التالية ستستفيد من هذا المستند

### واجهة API التفاعلية
```
http://localhost:8000/api/docs
```

---

## 🔌 API Reference

### المصادقة

```bash
# تسجيل الدخول
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'
# → {"access_token":"...","token_type":"bearer","username":"demo"}

# تسجيل مستخدم جديد
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'
```

### رفع مستند

```bash
TOKEN="your_jwt_token"

curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/document.pdf"
```

### إحصائيات RAG

```bash
curl http://localhost:8000/api/rag/stats \
  -H "Authorization: Bearer $TOKEN"
```

### بحث في RAG (اختبار)

```bash
curl -X POST http://localhost:8000/api/rag/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"ما هي سياسة الاسترجاع؟"}'
```

### WebSocket (اختبار بـ wscat)

```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws/chat
# أرسل: {"type":"auth","token":"your_jwt"}
# أرسل: {"type":"message","content":"مرحباً!"}
```

---

## ⚙️ متغيرات البيئة

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|---------------------|
| `MISTRAL_API_KEY` | **مطلوب** — مفتاح Mistral API | — |
| `SECRET_KEY` | مفتاح تشفير JWT | (قيمة ضعيفة — غيّرها) |
| `DEMO_USERNAME` | اسم المستخدم التجريبي | `demo` |
| `DEMO_PASSWORD` | كلمة مرور المستخدم التجريبي | `demo123` |
| `CHAT_MODEL` | نموذج Mistral للدردشة | `mistral-small-latest` |
| `DATABASE_URL` | رابط قاعدة البيانات | `sqlite+aiosqlite:///./data/support.db` |
| `FAISS_INDEX_PATH` | مسار فهرس FAISS | `./data/faiss_index` |
| `UPLOADS_DIR` | مجلد الملفات المرفوعة | `./data/uploads` |
| `HOST` | عنوان الاستماع | `0.0.0.0` |
| `PORT` | المنفذ | `8000` |
| `RELOAD` | إعادة تحميل تلقائية (dev) | `false` |

---

## ⚠️ القيود الحالية (MVP)

| القيد | السبب | الحل في الإنتاج |
|-------|--------|------------------|
| **SQLite** بدلاً من PostgreSQL | سهولة Termux | استبدل `DATABASE_URL` بـ PostgreSQL |
| **جلسات في الذاكرة** بدلاً من Redis | Redis معقد في Termux | أضف Redis + `aioredis` |
| **FAISS محلي** بدلاً من Pinecone | لا حاجة لإنترنت | استبدل بـ Pinecone/Weaviate |
| **مستخدم واحد تجريبي** | MVP | نظام تسجيل كامل + أدوار |
| **لا يوجد rate limiting** | MVP | أضف `slowapi` |
| **الجلسات تضيع عند إعادة التشغيل** | طبيعي في الذاكرة | Redis يحل هذا |
| **لا يوجد نظام تصعيد** | مرحلة لاحقة | نظام تذاكر + إشعارات |

---

## 🚀 نقاط الانطلاق للمرحلة الثانية

### ميزات مقترحة
- [ ] **Tool Calling** — Mistral Function Calling للإجراءات (فتح تذكرة، البحث في DB...)
- [ ] **نظام التصعيد** — تحويل المحادثة لوكيل بشري تلقائياً
- [ ] **ذاكرة طويلة المدى** — تلخيص المحادثات وتخزينها
- [ ] **تعدد المستأجرين** (Multi-tenancy)
- [ ] **لوحة إدارة** — إحصائيات، رصد الجلسات، إدارة المستندات
- [ ] **زحف الويب** — جلب محتوى الموقع تلقائياً وفهرسته
- [ ] **إشعارات** — WebPush أو Email
- [ ] **تقييم الإجابات** — 👍/👎 لتحسين النموذج

### التحجيم للإنتاج
```bash
# 1. استبدل SQLite بـ PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/aidb

# 2. أضف Redis للجلسات
REDIS_URL=redis://localhost:6379

# 3. استخدم Gunicorn مع uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# 4. أضف Nginx كـ reverse proxy
# 5. SSL مع Certbot
# 6. Pinecone/Qdrant بدلاً من FAISS
```

---

## 🐛 استكشاف الأخطاء

### `faiss-cpu` لا يُثبَّت
```bash
# جرّب التثبيت من المصدر
pip install --no-binary :all: faiss-cpu

# أو استخدم نسخة مبسطة
pip install faiss-cpu==1.7.2
```

### خطأ `aiosqlite`
```bash
pip install aiosqlite --upgrade
```

### `pdfplumber` يفشل في Termux
```bash
pip install PyPDF2  # بديل أبسط
# pdfplumber يعتمد على pdfminer وقد يكون ثقيلاً
```

### الخادم لا يبدأ
```bash
# تحقق من تفعيل البيئة الافتراضية
source venv/bin/activate

# تحقق من المتغيرات
python -c "from app.config import settings; print(settings.MISTRAL_API_KEY[:5])"

# شغّل بوضع verbose
uvicorn app.main:app --reload --log-level debug
```

### WebSocket ينقطع
- تأكد أن المتصفح لا يوقف الاتصال بعد فترة خمول
- الـ ping كل 25 ثانية يحافظ على الاتصال

---

## 📄 الترخيص

MIT — للاستخدام التجريبي والتعليمي.

---

*أُنشئ تلقائياً — MVP جاهز للاختبار في Termux/Ubuntu*# chatbot
# chatbot
