"""
memory.py - إدارة الجلسات في الذاكرة
⚠️  تنبيه: تُفقد جميع الجلسات عند إعادة تشغيل الخادم.
للإنتاج: استبدل بـ Redis أو قاعدة بيانات.
"""
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class SessionMemory:
    """
    مخزن الجلسات في الذاكرة.
    آمن للاستخدام مع FastAPI/asyncio (يستخدم threading.Lock للتزامن).
    """

    SESSION_TTL_HOURS = 24  # صلاحية الجلسة

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── CRUD ──────────────────────────────────────────────────────

    def create_session(self, session_id: str, user_id: int, username: str) -> None:
        with self._lock:
            self._sessions[session_id] = {
                "user_id": user_id,
                "username": username,
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
                "expires_at": (
                    datetime.utcnow() + timedelta(hours=self.SESSION_TTL_HOURS)
                ).isoformat(),
                "conversation_id": None,
                "context": [],       # آخر N رسالة للسياق
                "metadata": {},      # بيانات إضافية مخصصة
            }

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            # التحقق من انتهاء الصلاحية
            expires = datetime.fromisoformat(session["expires_at"])
            if datetime.utcnow() > expires:
                del self._sessions[session_id]
                return None
            return session.copy()

    def update_session(self, session_id: str, **kwargs) -> bool:
        with self._lock:
            if session_id not in self._sessions:
                return False
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["last_active"] = datetime.utcnow().isoformat()
            return True

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    # ── Context Management ────────────────────────────────────────

    def get_context(self, session_id: str, max_messages: int = 10) -> List[dict]:
        with self._lock:
            session = self._sessions.get(session_id, {})
            return session.get("context", [])[-max_messages:]

    def add_message_to_context(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                return
            ctx = self._sessions[session_id]["context"]
            ctx.append({"role": role, "content": content})
            # احتفظ بآخر 20 رسالة فقط
            self._sessions[session_id]["context"] = ctx[-20:]
            self._sessions[session_id]["last_active"] = datetime.utcnow().isoformat()

    def set_conversation_id(self, session_id: str, conversation_id: int) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["conversation_id"] = conversation_id

    # ── Stats ─────────────────────────────────────────────────────

    def get_active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def cleanup_expired(self) -> int:
        """تنظيف الجلسات المنتهية (يمكن استدعاؤها دورياً)"""
        removed = 0
        with self._lock:
            now = datetime.utcnow()
            expired = [
                sid for sid, s in self._sessions.items()
                if datetime.fromisoformat(s["expires_at"]) < now
            ]
            for sid in expired:
                del self._sessions[sid]
                removed += 1
        return removed


# Singleton
session_memory = SessionMemory()