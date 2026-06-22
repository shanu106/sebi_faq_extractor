"""
Embedding generation service
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"

from sentence_transformers import SentenceTransformer
from config import settings
import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings"""
    
    def __init__(self, model_name: str = settings.embedding_model):
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
    
    def encode(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text
        
        Returns:
            Embedding vector
        """
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
        
        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, batch_size=batch_size, convert_to_tensor=False)
        return [emb.tolist() for emb in embeddings]
    
    def encode_faq(self, question: str, answer: str) -> List[float]:
        """
        Generate embedding for FAQ (question + answer)
        
        Args:
            question: FAQ question
            answer: FAQ answer
        
        Returns:
            Embedding vector
        """
        # Combine question and answer with a separator
        combined_text = f"{question} [SEP] {answer}"
        return self.encode(combined_text)
    
    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
        
        Returns:
            Similarity score 0-1
        """
        import numpy as np
        v1 = np.array(embedding1)
        v2 = np.array(embedding2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


# Global instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
