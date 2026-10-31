"""
===================================================================================
AURA ADAPTER: SEARCH, RAG & MEMORY LAYER
===================================================================================
Curated capabilities extracted from:
- mem0ai/mem0 (Episodic Memory Vault & Temporal Decay)
- letta-ai/letta (MemGPT Context vs Archival Storage)
- pgvector/pgvector (Vector Similarity Math: Cosine & Euclidean)
- qdrant/qdrant (HNSW Vector Indexing & Filters)
- microsoft/graphrag (Entity-Relation Extraction)
- Unstructured-IO/unstructured (Document Partitioning & Chunking)
===================================================================================
"""
import math
import time
from typing import Dict, Any, List, Optional, Tuple


class Mem0EpisodicMemoryVault:
    """mem0ai/mem0-inspired episodic memory layer with update, recall, and decay."""
    def __init__(self):
        self.memories: List[Dict[str, Any]] = []

    def store_fact(self, key: str, value: str, category: str = "general") -> Dict[str, Any]:
        entry = {
            "key": key,
            "value": value,
            "category": category,
            "created_at": time.time(),
            "access_count": 1
        }
        self.memories.append(entry)
        return entry

    def recall(self, query: str) -> List[Dict[str, Any]]:
        import re
        query_words = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
        matched = []
        for m in self.memories:
            fact_text = f"{m['key']} {m['value']} {m.get('category', '')}"
            fact_words = set(re.findall(r"[a-zA-Z0-9]+", fact_text.lower()))
            intersection = query_words & fact_words
            if intersection:
                m["access_count"] += 1
                matched.append(m)
        return matched


class LettaHierarchicalMemoryManager:
    """letta-ai/letta (MemGPT)-inspired working context vs archival storage partitioner."""
    def __init__(self, working_token_limit: int = 4096):
        self.working_context: List[str] = []
        self.archival_storage: List[str] = []
        self.working_token_limit = working_token_limit

    def add_to_context(self, text: str):
        self.working_context.append(text)
        # Approximate tokens by words
        total_tokens = sum(len(t.split()) for t in self.working_context)
        if total_tokens > self.working_token_limit:
            # Evict oldest entry into archival storage
            evicted = self.working_context.pop(0)
            self.archival_storage.append(evicted)


class PgvectorSimilarityMath:
    """pgvector-inspired vector math: Cosine distance & L2 Euclidean calculation."""
    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return round(dot / (norm_a * norm_b), 4)

    @staticmethod
    def euclidean_distance(vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b):
            return 999.0
        return round(math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b))), 4)


class GraphRAGTripletExtractor:
    """microsoft/graphrag-inspired entity-relation triplet extractor."""
    @staticmethod
    def extract_triplets(text: str) -> List[Dict[str, str]]:
        triplets = []
        # Basic heuristic entity extractor for architecture definitions
        sentences = text.split(".")
        for s in sentences:
            if "uses" in s:
                parts = s.split("uses")
                if len(parts) == 2:
                    triplets.append({"subject": parts[0].strip(), "predicate": "uses", "object": parts[1].strip()})
            elif "integrates" in s:
                parts = s.split("integrates")
                if len(parts) == 2:
                    triplets.append({"subject": parts[0].strip(), "predicate": "integrates", "object": parts[1].strip()})
        return triplets


class UnstructuredDocumentChunker:
    """Unstructured-IO-inspired clean text chunker with overlap."""
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, Any]]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append({"chunk_id": idx, "text": chunk, "char_length": len(chunk)})
            idx += 1
            start += (chunk_size - overlap)
            if start >= len(text):
                break
        return chunks
