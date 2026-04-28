"""
rag.py - محرك RAG باستخدام FAISS (محلي) و Mistral Embeddings API
"""
import json
import os
from typing import List, Optional, Tuple

import httpx
import numpy as np

from .config import settings

# ─── FAISS Import ──────────────────────────────────────────────────
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️  faiss-cpu غير مثبّت — ميزات RAG معطّلة.")
    print("   لتثبيته: pip install faiss-cpu")

EMBEDDING_DIMENSION = 1024  # أبعاد نموذج mistral-embed


class RAGEngine:
    """
    محرك الاسترجاع المعزّز بالتوليد (RAG).
    - يخزّن المتجهات في FAISS على القرص.
    - يستخدم Mistral API للـ embeddings.
    - يسترجع أقرب N قطعة نص عند البحث.
    """

    def __init__(self):
        self.index_path = settings.FAISS_INDEX_PATH
        self.metadata_path = f"{self.index_path}_meta.json"
        self.index: Optional["faiss.Index"] = None
        self.metadata: List[dict] = []   # [{text, source, chunk_id}]
        self._http_client: Optional[httpx.AsyncClient] = None
        self._load_or_create_index()

    # ── Index Lifecycle ───────────────────────────────────────────

    def _load_or_create_index(self):
        if not FAISS_AVAILABLE:
            return
        os.makedirs("./data", exist_ok=True)

        faiss_file = f"{self.index_path}.faiss"
        if os.path.exists(faiss_file) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(faiss_file)
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                print(f"✅ FAISS: تحميل {self.index.ntotal} متجه من القرص")
                return
            except Exception as e:
                print(f"⚠️  خطأ في تحميل FAISS: {e} — إنشاء فهرس جديد")

        self._create_new_index()

    def _create_new_index(self):
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            self.metadata = []
            print("✅ FAISS: فهرس جديد فارغ")

    def _save_index(self):
        if not FAISS_AVAILABLE or self.index is None:
            return
        faiss.write_index(self.index, f"{self.index_path}.faiss")
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    # ── Mistral Embeddings API ────────────────────────────────────

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """استدعاء Mistral Embeddings API"""
        if not texts:
            return []

        # تقسيم إلى دُفعات (max 32 نصاً في الطلب الواحد)
        all_embeddings = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.MISTRAL_BASE_URL}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"model": settings.EMBEDDING_MODEL, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()
                all_embeddings.extend([item["embedding"] for item in data["data"]])

        return all_embeddings

    # ── Public API ────────────────────────────────────────────────

    async def add_chunks(self, chunks: List[str], source: str) -> int:
        """
        تضمين قطع النص وإضافتها إلى FAISS.
        يُعاد عدد القطع المُضافة.
        """
        if not FAISS_AVAILABLE or not chunks:
            return 0

        print(f"  📥 تضمين {len(chunks)} قطعة من [{source}] ...")
        embeddings = await self._get_embeddings(chunks)
        vectors = np.array(embeddings, dtype=np.float32)

        start_id = len(self.metadata)
        self.index.add(vectors)

        for i, chunk in enumerate(chunks):
            self.metadata.append({
                "chunk_id": start_id + i,
                "source": source,
                "text": chunk,
            })

        self._save_index()
        print(f"  ✅ تم حفظ {len(chunks)} قطعة — الإجمالي: {self.index.ntotal}")
        return len(chunks)

    async def search(
        self,
        query: str,
        k: int = None,
    ) -> List[Tuple[str, str, float]]:
        """
        البحث عن أقرب K قطعة للسؤال.
        يُعيد قائمة من (text, source, distance).
        """
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []

        k = k or settings.TOP_K_RESULTS
        k = min(k, self.index.ntotal)

        embeddings = await self._get_embeddings([query])
        query_vec = np.array(embeddings, dtype=np.float32)

        distances, indices = self.index.search(query_vec, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            if dist > settings.RAG_DISTANCE_THRESHOLD:
                continue  # بعيد جداً — غير ذي صلة
            meta = self.metadata[idx]
            results.append((meta["text"], meta["source"], float(dist)))

        return results

    def get_stats(self) -> dict:
        return {
            "faiss_available": FAISS_AVAILABLE,
            "total_vectors": self.index.ntotal if (FAISS_AVAILABLE and self.index) else 0,
            "total_chunks": len(self.metadata),
            "index_path": self.index_path,
        }

    def clear_index(self):
        """حذف الفهرس وإعادة البناء"""
        self._create_new_index()
        self._save_index()
        print("🗑️  تم مسح فهرس FAISS")


# Singleton
rag_engine = RAGEngine()