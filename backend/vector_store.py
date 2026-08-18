"""
FAISS Vector Store Manager for Incremental Indexing and Cosine Similarity Search.
"""
import os
import threading
import logging
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
import faiss

from backend.config import FAISS_INDEX_PATH, EMBEDDING_DIM

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Manages the in-memory FAISS vector index with thread-safe incremental additions
    and disk persistence.
    """
    _instance: Optional["VectorStore"] = None
    _lock = threading.Lock()

    def __init__(self, index_path: Path = FAISS_INDEX_PATH, dimension: int = EMBEDDING_DIM):
        self.index_path = Path(index_path)
        self.dimension = dimension
        self.index = None
        self._load_or_create_index()

    @classmethod
    def get_instance(cls) -> "VectorStore":
        """Get or initialize singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_or_create_index(self):
        """Load existing FAISS index from disk or create a new IndexFlatIP."""
        if self.index_path.exists():
            try:
                logger.info(f"Loading FAISS index from {self.index_path}")
                self.index = faiss.read_index(str(self.index_path))
                self.dimension = self.index.d
                logger.info(f"Loaded FAISS index containing {self.index.ntotal} vectors (dim={self.dimension}).")
                return
            except Exception as e:
                logger.error(f"Failed to read FAISS index from {self.index_path}: {e}. Creating new index.")

        logger.info(f"Creating new FAISS IndexFlatIP with dimension {self.dimension}")
        # IndexFlatIP computes exact inner product (Cosine Similarity on L2 normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.save()

    @property
    def total_vectors(self) -> int:
        """Total vectors stored in the index."""
        return self.index.ntotal if self.index is not None else 0

    def add_vector(self, embedding: np.ndarray) -> int:
        """
        Incrementally add a single normalized vector to the FAISS index.
        
        Args:
            embedding: 1D or 2D float32 numpy array.
            
        Returns:
            int: The assigned 0-indexed FAISS ID.
        """
        return self.add_vectors(np.expand_dims(embedding, axis=0) if embedding.ndim == 1 else embedding)[0]

    def add_vectors(self, embeddings: np.ndarray) -> List[int]:
        """
        Incrementally add multiple normalized vectors to the FAISS index.
        
        Args:
            embeddings: 2D float32 numpy array of shape (N, dimension).
            
        Returns:
            List[int]: List of assigned FAISS IDs.
        """
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)

        # Ensure L2 normalization
        faiss.normalize_L2(embeddings)

        with self._lock:
            start_id = self.index.ntotal
            num_vectors = embeddings.shape[0]
            self.index.add(embeddings)
            assigned_ids = list(range(start_id, start_id + num_vectors))
            
            # Persist to disk
            self.save()
            logger.info(f"Incrementally added {num_vectors} vectors to FAISS index. Total: {self.index.ntotal}")
            return assigned_ids

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        Execute cosine similarity search for a query vector.
        
        Args:
            query_vector: 1D or 2D float32 numpy array.
            top_k: Number of nearest neighbors to retrieve.
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (scores, faiss_ids) arrays of shape (1, K)
        """
        if self.index.ntotal == 0:
            return np.array([[]], dtype=np.float32), np.array([[]], dtype=np.int64)

        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)

        faiss.normalize_L2(query_vector)
        k = min(top_k, self.index.ntotal)
        
        with self._lock:
            scores, indices = self.index.search(query_vector, k)
            
        return scores, indices

    def save(self):
        """Save the in-memory FAISS index to disk atomically."""
        if self.index is not None:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = str(self.index_path) + ".tmp"
            faiss.write_index(self.index, temp_path)
            if os.path.exists(str(self.index_path)):
                os.replace(temp_path, str(self.index_path))
            else:
                os.rename(temp_path, str(self.index_path))
            logger.debug(f"Saved FAISS index ({self.index.ntotal} vectors) to {self.index_path}")

    def reset(self):
        """Clear all vectors from the index."""
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.save()
            logger.info("FAISS index has been reset.")
