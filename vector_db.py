"""
Qdrant vector database integration
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PayloadSchemaType
from config import settings
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class QdrantVectorDB:
    """Qdrant vector database client"""
    
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self.collection_name = settings.qdrant_collection_name
        self.vector_size = settings.embedding_dimension
        self._init_collection()
    
    def _recreate_client(self):
        """Re-initialize QdrantClient if closed"""
        logger.info("Re-initializing Qdrant client connection...")
        try:
            self.client.close()
        except Exception:
            pass
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    
    def _init_collection(self):
        """Initialize the collection if it doesn't exist"""
        collection_exists = False
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists")
            collection_exists = True
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                self._recreate_client()
                try:
                    self.client.get_collection(self.collection_name)
                    logger.info(f"Collection '{self.collection_name}' already exists after client recreation")
                    collection_exists = True
                except Exception:
                    pass
            
            if not collection_exists:
                logger.info(f"Creating collection '{self.collection_name}'")
                try:
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                        hnsw_config={
                            "m": 16,
                            "ef_construct": 100,
                        },
                    )
                except Exception as ex:
                    logger.error(f"Failed to create collection: {ex}")
                    return

        # Ensure index on faq_id exists
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="faq_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            logger.info("Payload index on 'faq_id' created/verified.")
        except Exception as idx_ex:
            logger.debug(f"Payload index creation details: {idx_ex}")
    
    def store_embedding(
        self, 
        faq_id: str, 
        embedding: List[float], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a single embedding with metadata
        
        Args:
            faq_id: FAQ unique identifier
            embedding: Embedding vector
            metadata: Optional metadata payload
        
        Returns:
            Point ID in Qdrant
        """
        point_id = str(uuid.uuid4().int)  # Convert to int for Qdrant
        
        payload = {
            "faq_id": faq_id,
            **(metadata or {})
        }
        
        point = PointStruct(
            id=int(point_id[:15]),  # Use first 15 digits as ID
            vector=embedding,
            payload=payload
        )
        
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                self._recreate_client()
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[point],
                )
            else:
                raise
        
        logger.debug(f"Stored embedding for FAQ {faq_id}")
        return point_id
    
    def search_similar(
        self, 
        embedding: List[float], 
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for similar embeddings
        
        Args:
            embedding: Query embedding vector
            limit: Number of results
            score_threshold: Minimum similarity score
            filters: Optional Qdrant filters
        
        Returns:
            List of (faq_id, similarity_score) tuples
        """
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filters,
            )
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                self._recreate_client()
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=embedding,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=filters,
                )
            else:
                raise
        
        return [(result.payload.get("faq_id"), result.score) for result in response.points]
    
    def delete_embedding(self, faq_id: str):
        """Delete embedding for a FAQ"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="faq_id",
                            match=MatchValue(value=faq_id)
                        )
                    ]
                )
            )
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                self._recreate_client()
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="faq_id",
                                match=MatchValue(value=faq_id)
                            )
                        ]
                    )
                )
            else:
                raise
        logger.debug(f"Deleted embedding for FAQ {faq_id}")
    
    def update_payload(
        self, 
        faq_id: str, 
        metadata: Dict[str, Any]
    ):
        """Update metadata payload for a FAQ without changing its vector"""
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=metadata,
                points=Filter(
                    must=[
                        FieldCondition(
                            key="faq_id",
                            match=MatchValue(value=faq_id)
                        )
                    ]
                )
            )
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                self._recreate_client()
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload=metadata,
                    points=Filter(
                        must=[
                            FieldCondition(
                                key="faq_id",
                                match=MatchValue(value=faq_id)
                            )
                        ]
                    )
                )
            else:
                raise
        logger.debug(f"Updated Qdrant payload for FAQ {faq_id}")

    def update_embedding(
        self, 
        faq_id: str, 
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update embedding for a FAQ"""
        self.delete_embedding(faq_id)
        self.store_embedding(faq_id, embedding, metadata)
    
    def health_check(self) -> bool:
        """Check if Qdrant is accessible"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            if "client has been closed" in str(e) or "closed" in str(e).lower():
                try:
                    self._recreate_client()
                    self.client.get_collections()
                    return True
                except Exception:
                    pass
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Global instance
_vector_db = None


def get_vector_db() -> QdrantVectorDB:
    """Get or create global Qdrant client"""
    global _vector_db
    if _vector_db is None:
        _vector_db = QdrantVectorDB()
    return _vector_db
