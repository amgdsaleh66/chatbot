"""
utils.py - دوال مساعدة مشتركة
"""
import re
from datetime import datetime
from typing import Any, Dict, List


def clean_text(text: str) -> str:
    """تنظيف النص من المسافات الزائدة"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate(text: str, max_chars: int = 300, suffix: str = "...") -> str:
    """اقتطاع النص مع إضافة ... إذا كان طويلاً"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(' ', 1)[0] + suffix


def format_rag_results(results: List[tuple]) -> str:
    """تنسيق نتائج RAG كنص واضح"""
    if not results:
        return ""
    parts = []
    for i, (text, source, score) in enumerate(results, 1):
        parts.append(f"[{i}] المصدر: {source}\n{text}")
    return "\n\n".join(parts)


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def paginate(items: List, page: int = 1, per_page: int = 20) -> Dict:
    """تقسيم القوائم الكبيرة إلى صفحات"""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }