"""
document_ingestion.py - معالجة المستندات (PDF / TXT) وفهرستها في RAG
"""
import os
import re
from typing import List, Optional

from fastapi import HTTPException, UploadFile

from .config import settings
from .rag import rag_engine

os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
MAX_FILE_SIZE_MB = 20


# ─── Text Extraction ───────────────────────────────────────────────

async def extract_text_pdf(file_path: str) -> str:
    """استخراج النص من PDF — يجرّب pdfplumber أولاً ثم PyPDF2"""
    text = ""

    # المحاولة الأولى: pdfplumber (أدق)
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️  pdfplumber error: {e}")

    # المحاولة الثانية: PyPDF2
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="لم يُعثر على مكتبة PDF. ثبّت: pip install pdfplumber",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في قراءة PDF: {e}")


async def extract_text_txt(file_path: str) -> str:
    """قراءة ملف نصي"""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    # آخر محاولة مع ignore
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ─── Text Chunking ─────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """تنظيف النص المستخرج"""
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\x00', '', text)   # null bytes
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> List[str]:
    """
    تقسيم النص إلى قطع متداخلة.
    يحاول الكسر عند حدود الجمل.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    text = clean_text(text)
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:]
        else:
            # حاول الكسر عند نهاية جملة
            for sep in [". ", ".\n", "! ", "? ", "\n\n", "\n", " "]:
                pos = text.rfind(sep, start + chunk_size // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
            chunk = text[start:end]

        chunk = chunk.strip()
        if chunk and len(chunk) > 20:  # تجاهل القطع القصيرة جداً
            chunks.append(chunk)

        if end >= len(text):
            break
        start = end - overlap

    return chunks


# ─── Main Ingestion Function ───────────────────────────────────────

async def process_upload(file: UploadFile, db=None) -> dict:
    """
    المعالج الرئيسي: يحفظ الملف، يستخرج النص، يقسّمه، ويفهرسه في FAISS.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="اسم الملف مفقود")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"امتداد غير مدعوم [{ext}]. المسموح: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # قراءة المحتوى
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"الملف أكبر من {MAX_FILE_SIZE_MB}MB",
        )
    if file_size == 0:
        raise HTTPException(status_code=400, detail="الملف فارغ")

    # حفظ الملف
    save_path = os.path.join(settings.UPLOADS_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(content)

    # استخراج النص
    if ext == ".pdf":
        text = await extract_text_pdf(save_path)
    else:
        text = await extract_text_txt(save_path)

    text = clean_text(text)
    if not text:
        raise HTTPException(
            status_code=400,
            detail="لم يتمكن من استخراج أي نص من الملف",
        )

    # التقسيم والفهرسة
    chunks = chunk_text(text)
    print(f"📄 {file.filename}: {len(text)} حرف → {len(chunks)} قطعة")

    chunk_count = await rag_engine.add_chunks(chunks, source=file.filename)

    # تحديث قاعدة البيانات
    if db is not None:
        from sqlalchemy import select
        from .models import Document

        result = await db.execute(
            select(Document).where(Document.filename == file.filename)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.chunk_count = chunk_count
            existing.text_length = len(text)
            existing.file_size = file_size
            existing.is_indexed = True
        else:
            doc = Document(
                filename=file.filename,
                file_type=ext.lstrip("."),
                file_size=file_size,
                chunk_count=chunk_count,
                text_length=len(text),
                is_indexed=True,
            )
            db.add(doc)

        await db.commit()

    return {
        "filename": file.filename,
        "file_size_kb": round(file_size / 1024, 2),
        "text_length": len(text),
        "chunks_indexed": chunk_count,
        "status": "success",
        "message": f"تم فهرسة {chunk_count} قطعة بنجاح",
    }