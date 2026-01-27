"""
Enhanced Embedding service with BGE-M3 and hybrid search support.
Optimized for Chinese and multilingual text.
"""
from typing import List, Union, Optional, Tuple, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from app.config import settings
import logging
import jieba
from collections import Counter
import math
import re

logger = logging.getLogger(__name__)

# Global model instances
_embedding_model: Optional[SentenceTransformer] = None
_rerank_model: Optional[CrossEncoder] = None
_bm25_index: Optional['BM25Index'] = None


class BM25Index:
    """BM25 index for keyword-based retrieval."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict[str, Any]] = []
        self.doc_freqs: Dict[str, int] = Counter()
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.tokenized_docs: List[List[str]] = []
        
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text using jieba for Chinese + basic tokenization for English."""
        text = text.lower()
        tokens = list(jieba.cut(text))
        english_tokens = re.findall(r'[a-zA-Z]+', text)
        tokens.extend(english_tokens)
        tokens = [t.strip() for t in tokens if t.strip() and (len(t) > 1 or '\u4e00' <= t <= '\u9fff')]
        return tokens
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add documents to the BM25 index."""
        for doc in documents:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            tokens = self._tokenize(text)
            
            self.documents.append(doc)
            self.tokenized_docs.append(tokens)
            self.doc_lengths.append(len(tokens))
            
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1
        
        if self.doc_lengths:
            self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)
    
    def clear(self):
        """Clear the index."""
        self.documents = []
        self.doc_freqs = Counter()
        self.doc_lengths = []
        self.avg_doc_length = 0.0
        self.tokenized_docs = []
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """Search for documents matching the query."""
        if not self.documents:
            return []
        
        query_tokens = self._tokenize(query)
        scores = []
        n_docs = len(self.documents)
        
        for idx, doc_tokens in enumerate(self.tokenized_docs):
            score = 0.0
            doc_len = self.doc_lengths[idx]
            doc_tf = Counter(doc_tokens)
            
            for token in query_tokens:
                if token not in self.doc_freqs:
                    continue
                
                df = self.doc_freqs[token]
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                
                tf = doc_tf.get(token, 0)
                tf_normalized = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
                )
                
                score += idf * tf_normalized
            
            scores.append((self.documents[idx], score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def get_embedding_model() -> SentenceTransformer:
    """Get or create embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        try:
            _embedding_model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                
            )
            logger.info(f"Embedding model loaded. Dimension: {_embedding_model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.warning(f"Failed to load {settings.EMBEDDING_MODEL}, using fallback: {e}")
            _embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    return _embedding_model


def get_rerank_model() -> Optional[CrossEncoder]:
    """Get or create re-ranking model instance."""
    global _rerank_model
    if _rerank_model is None and settings.RAG_USE_RERANKING:
        logger.info(f"Loading rerank model: {settings.RAG_RERANK_MODEL}")
        try:
            _rerank_model = CrossEncoder(settings.RAG_RERANK_MODEL)
            logger.info("Rerank model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load rerank model: {e}")
            return None
    return _rerank_model


def get_bm25_index() -> BM25Index:
    """Get or create BM25 index instance."""
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return embedding.tolist()


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.tolist()


def compute_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Compute cosine similarity between two embeddings."""
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    return float(np.dot(vec1, vec2))


def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    content_key: str = 'content',
    top_k: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Re-rank results using cross-encoder for better accuracy."""
    if not results:
        return results
    
    reranker = get_rerank_model()
    if reranker is None:
        return results[:top_k] if top_k else results
    
    pairs = []
    for result in results:
        content = result.get(content_key, '') or result.get('title', '')
        if isinstance(content, str):
            content = content[:2000]
        pairs.append([query, content])
    
    try:
        scores = reranker.predict(pairs)
        
        scored_results = []
        for result, score in zip(results, scores):
            result_copy = result.copy()
            result_copy['rerank_score'] = float(score)
            scored_results.append(result_copy)
        
        scored_results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        
        return scored_results[:top_k] if top_k else scored_results
    except Exception as e:
        logger.error(f"Re-ranking failed: {e}")
        return results[:top_k] if top_k else results


def hybrid_search(
    query: str,
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Tuple[Dict[str, Any], float]],
    vector_weight: float = 0.5,
    bm25_weight: float = 0.5,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Combine vector search and BM25 results using Reciprocal Rank Fusion."""
    k = 60  # RRF constant
    
    fusion_scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}
    
    for rank, result in enumerate(vector_results, 1):
        doc_id = str(result.get('id', id(result)))
        rrf_score = vector_weight / (k + rank)
        fusion_scores[doc_id] = fusion_scores.get(doc_id, 0) + rrf_score
        doc_map[doc_id] = result
    
    for rank, (doc, bm25_score) in enumerate(bm25_results, 1):
        doc_id = str(doc.get('id', id(doc)))
        rrf_score = bm25_weight / (k + rank)
        fusion_scores[doc_id] = fusion_scores.get(doc_id, 0) + rrf_score
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
    
    sorted_ids = sorted(fusion_scores.keys(), key=lambda x: fusion_scores[x], reverse=True)
    
    final_results = []
    for doc_id in sorted_ids[:top_k]:
        result = doc_map[doc_id].copy()
        result['fusion_score'] = fusion_scores[doc_id]
        final_results.append(result)
    
    return final_results


def extract_keywords(text: str, top_k: int = 10) -> List[str]:
    """Extract important keywords from text using TF-IDF-like scoring."""
    tokens = list(jieba.cut(text))
    freq = Counter(tokens)
    
    chinese_stopwords = set([
        '\u7684', '\u662f', '\u5728', '\u4e86', '\u548c', '\u8207', '\u6216', 
        '\u4f46', '\u800c', '\u9019', '\u90a3', '\u6709', '\u70ba', '\u5230', 
        '\u5f9e', '\u4e2d', '\u4e0a', '\u4e0b'
    ])
    
    keywords = [
        (token, count) 
        for token, count in freq.most_common(top_k * 3)
        if token not in chinese_stopwords and len(token.strip()) > 1
    ]
    
    return [kw[0] for kw in keywords[:top_k]]


def init_jieba():
    """Initialize jieba with custom dictionary if available."""
    try:
        jieba.initialize()
        logger.info("Jieba initialized for Chinese tokenization")
    except Exception as e:
        logger.warning(f"Jieba initialization warning: {e}")


init_jieba()
