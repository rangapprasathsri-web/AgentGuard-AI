import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from guard.policy_version import compute_corpus_hash


class PolicyChunk:
    def __init__(self, doc_name: str, heading: str, content: str):
        self.doc_name = doc_name
        self.heading = heading
        self.content = content
        self.citation = f"{doc_name}#{heading}"


class PolicyRAGEngine:
    def __init__(self, policy_dir: str = "policy-data"):
        self.policy_dir = policy_dir
        self.chunks: List[PolicyChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.corpus_hash: str = ""
        self.load_and_index()

    def load_and_index(self) -> None:
        """
        Chunks policy documents by headings, builds in-memory TF-IDF index,
        and computes corpus hash. No external vector DB.
        """
        self.chunks = []
        if not os.path.exists(self.policy_dir):
            return

        for fname in sorted(os.listdir(self.policy_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(self.policy_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    text = f.read()

                # Chunk by markdown headings
                sections = re.split(r"\n(?=#{1,3}\s+)", text)
                for sec in sections:
                    sec = sec.strip()
                    if not sec:
                        continue
                    lines = sec.splitlines()
                    heading = lines[0].lstrip("#").strip() if lines else fname
                    self.chunks.append(
                        PolicyChunk(doc_name=fname, heading=heading, content=sec)
                    )

        if self.chunks:
            corpus_texts = [f"{c.heading}\n{c.content}" for c in self.chunks]
            self.vectorizer = TfidfVectorizer(stop_words="english")
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)

        self.corpus_hash = compute_corpus_hash(self.policy_dir)

    def retrieve(
        self, action: str, target: str, department: str = "", top_k: int = 3
    ) -> Tuple[List[str], List[str], str]:
        """
        Retrieves top k chunks for (action, target, department).
        Returns: (chunks_text_list, citations_list, rag_status)
        Advisory only: RAG NEVER affects decisions or scores.
        """
        try:
            if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
                return [], [], "skipped"

            query = f"{action} {target} {department} policy rules security constraints"
            query_vec = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

            top_indices = similarities.argsort()[::-1][:top_k]
            matched_chunks = []
            citations = []
            for idx in top_indices:
                if similarities[idx] > 0.0:
                    c = self.chunks[idx]
                    matched_chunks.append(c.content)
                    citations.append(c.citation)

            return matched_chunks, citations, "success"
        except Exception:
            # Advisory failure -> continue with no chunks and rag_status="failed"
            return [], [], "failed"
