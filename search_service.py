"""
Search service - handles semantic, metadata, and full-text search
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from models import FAQ, FAQMetadata, SearchLog, FAQVersion
from schemas import (
    SemanticSearchRequest, MetadataFilterRequest, FullTextSearchRequest,
    CombinedSearchRequest, SearchResult, SearchResponse, FAQResponse, MetadataResponse
)
from embeddings import get_embedding_service
from vector_db import get_vector_db

logger = logging.getLogger(__name__)


class SearchService:
    """Service for searching FAQs"""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.vector_db = get_vector_db()

    def _process_search_results(self, faqs: List[FAQ]) -> List[FAQ]:
        """
        Groups matching FAQs by (question text, category), finds the latest version,
        attaches historical versions, and sorts the list by document_publish_date descending.
        """
        if not faqs:
            return []
            
        unique_faqs = {}
        for faq in faqs:
            q_norm = faq.question.strip().lower()
            cat_norm = (faq.category or "").strip().lower()
            key = (q_norm, cat_norm)
            
            if key not in unique_faqs:
                # Find the active FAQ for this question and category combination
                active_faq = self.db.query(FAQ).filter(
                    and_(
                        func.lower(FAQ.question) == q_norm,
                        func.coalesce(func.lower(FAQ.category), '') == cat_norm,
                        FAQ.is_active == True
                    )
                ).order_by(FAQ.document_publish_date.desc().nullslast()).first()
                
                if active_faq:
                    # Query all versions for this active_faq.id from FAQVersion table
                    versions = self.db.query(FAQVersion).filter(
                        FAQVersion.faq_id == active_faq.id
                    ).order_by(FAQVersion.version_number.desc()).all()
                    
                    if versions:
                        max_version_num = max(v.version_number for v in versions)
                        # Historical answers are the ones with version_number < max_version_num
                        active_faq.historical_answers = [
                            v for v in versions if v.version_number < max_version_num
                        ]
                    else:
                        active_faq.historical_answers = []
                        
                    unique_faqs[key] = active_faq
                    
        processed = list(unique_faqs.values())
        processed.sort(key=lambda x: x.document_publish_date or datetime.min, reverse=True)
        return processed
    
    def semantic_search(
        self, 
        request: SemanticSearchRequest,
        user_id: Optional[str] = None
    ) -> SearchResponse:
        """
        Semantic search using vector similarity
        
        Args:
            request: Search request with query and parameters
            user_id: Optional user identifier for logging
        
        Returns:
            Search response with results
        """
        start_time = datetime.utcnow()
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.encode(request.query)
            
            # Search in Qdrant
            similar_results = self.vector_db.search_similar(
                embedding=query_embedding,
                limit=request.limit,
                score_threshold=request.min_similarity
            )
            
            # Fetch FAQ details from database
            faq_ids = [faq_id for faq_id, _ in similar_results]
            if not faq_ids:
                return SearchResponse(
                    query=request.query,
                    total_results=0,
                    results=[],
                    response_time_ms=self._get_elapsed_ms(start_time),
                )
            
            faqs = self.db.query(FAQ).filter(
                and_(FAQ.id.in_(faq_ids), FAQ.is_active == True)
            ).all()
            
            # Build result map with scores
            score_map = {faq_id: score for faq_id, score in similar_results}
            
            # Group, find latest versions and historical versions
            processed_faqs = self._process_search_results(faqs)
            
            # Create search results
            results = []
            for faq in processed_faqs:
                max_score = score_map.get(faq.id, 0.5)
                for hist in faq.historical_answers:
                    if hist.id in score_map:
                        max_score = max(max_score, score_map[hist.id])
                
                results.append(
                    SearchResult(
                        faq=self._faq_to_response(faq),
                        score=max_score,
                        match_type="semantic",
                        matched_fields=["question", "answer"]
                    )
                )
            
            # Sort by publication date
            results.sort(key=lambda x: (x.faq.document_publish_date or datetime.min, x.score), reverse=True)
            
            response_time_ms = self._get_elapsed_ms(start_time)
            
            # Log search
            self._log_search(
                query=request.query,
                search_type="semantic",
                results_count=len(results),
                top_result_id=results[0].faq.id if results else None,
                response_time_ms=response_time_ms,
                user_id=user_id
            )
            
            return SearchResponse(
                query=request.query,
                total_results=len(results),
                results=results,
                response_time_ms=response_time_ms,
            )
        
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def metadata_search(
        self,
        request: MetadataFilterRequest,
        limit: int = 100,
        user_id: Optional[str] = None
    ) -> SearchResponse:
        """
        Search by metadata filters
        
        Args:
            request: Filter request with metadata criteria
            limit: Result limit
            user_id: Optional user identifier
        
        Returns:
            Search response with filtered results
        """
        start_time = datetime.utcnow()
        
        try:
            # Build query
            query = self.db.query(FAQ).join(FAQMetadata)
            
            # Apply filters
            filters = []
            filter_summary = {}
            
            if request.department:
                filters.append(FAQMetadata.department == request.department)
                filter_summary["department"] = request.department
            
            if request.category:
                filters.append(FAQMetadata.category == request.category)
                filter_summary["category"] = request.category
            
            if request.risk_level:
                filters.append(FAQMetadata.risk_level == request.risk_level)
                filter_summary["risk_level"] = request.risk_level
            
            if request.compliance_status:
                filters.append(FAQMetadata.compliance_status == request.compliance_status)
                filter_summary["compliance_status"] = request.compliance_status
            
            if request.authority:
                filters.append(FAQMetadata.authority == request.authority)
                filter_summary["authority"] = request.authority
            
            if request.compliance_framework:
                filters.append(FAQMetadata.compliance_framework == request.compliance_framework)
                filter_summary["compliance_framework"] = request.compliance_framework
            
            if request.is_verified is not None:
                filters.append(FAQ.is_verified == request.is_verified)
            
            # Apply all filters
            if filters:
                query = query.filter(and_(*filters))
            
            query = query.filter(FAQ.is_active == True)
            faqs = query.all()
            
            # Group, find latest versions and historical versions
            processed_faqs = self._process_search_results(faqs)
            
            # Create results
            results = [
                SearchResult(
                    faq=self._faq_to_response(faq),
                    score=1.0,  # Full match
                    match_type="metadata",
                    matched_fields=list(filter_summary.keys())
                )
                for faq in processed_faqs
            ]
            
            # Sort by publication date
            results.sort(key=lambda x: (x.faq.document_publish_date or datetime.min), reverse=True)
            
            response_time_ms = self._get_elapsed_ms(start_time)
            
            # Log search
            self._log_search(
                query="metadata_filter",
                search_type="filter",
                results_count=len(results),
                top_result_id=results[0].faq.id if results else None,
                response_time_ms=response_time_ms,
                applied_filters=filter_summary,
                user_id=user_id
            )
            
            return SearchResponse(
                query="metadata_filter",
                total_results=len(results),
                results=results,
                response_time_ms=response_time_ms,
                filters_applied=filter_summary
            )
        
        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            raise
    
    def fulltext_search(
        self,
        request: FullTextSearchRequest,
        user_id: Optional[str] = None
    ) -> SearchResponse:
        """
        Full-text search on question and answer
        
        Args:
            request: Full-text search request
            user_id: Optional user identifier
        
        Returns:
            Search response with results
        """
        start_time = datetime.utcnow()
        
        try:
            query_terms = request.query.lower().split()
            
            # Build search conditions
            conditions = []
            for term in query_terms:
                term_pattern = f"%{term}%"
                conditions.append(
                    or_(
                        FAQ.question.ilike(term_pattern),
                        FAQ.answer.ilike(term_pattern)
                    )
                )
            
            # Find matching FAQs
            query = self.db.query(FAQ).filter(
                and_(and_(*conditions), FAQ.is_active == True)
            ).limit(request.limit)
            
            faqs = query.all()
            
            # Group, find latest versions and historical versions
            processed_faqs = self._process_search_results(faqs)
            
            # Create results with relevance scoring
            results = []
            for faq in processed_faqs:
                # Simple relevance: count term occurrences
                score = self._calculate_text_relevance(
                    faq.question, 
                    faq.answer, 
                    query_terms
                )
                for hist in faq.historical_answers:
                    hist_score = self._calculate_text_relevance(
                        hist.question,
                        hist.answer,
                        query_terms
                    )
                    score = max(score, hist_score)
                    
                results.append(
                    SearchResult(
                        faq=self._faq_to_response(faq),
                        score=score,
                        match_type="fulltext",
                        matched_fields=["question", "answer"]
                    )
                )
            
            # Sort by publication date
            results.sort(key=lambda x: (x.faq.document_publish_date or datetime.min, x.score), reverse=True)
            
            response_time_ms = self._get_elapsed_ms(start_time)
            
            # Log search
            self._log_search(
                query=request.query,
                search_type="fulltext",
                results_count=len(results),
                top_result_id=results[0].faq.id if results else None,
                response_time_ms=response_time_ms,
                user_id=user_id
            )
            
            return SearchResponse(
                query=request.query,
                total_results=len(results),
                results=results,
                response_time_ms=response_time_ms,
            )
        
        except Exception as e:
            logger.error(f"Full-text search failed: {e}")
            raise
    
    def combined_search(
        self,
        request: CombinedSearchRequest,
        user_id: Optional[str] = None
    ) -> SearchResponse:
        """
        Combined search using semantic + metadata + full-text with weighted scoring
        
        Args:
            request: Combined search request
            user_id: Optional user identifier
        
        Returns:
            Search response with combined results
        """
        start_time = datetime.utcnow()
        
        try:
            # Run all search types in parallel conceptually
            semantic_request = SemanticSearchRequest(
                query=request.query,
                limit=request.limit + request.offset,
                min_similarity=request.min_similarity
            )
            
            fulltext_request = FullTextSearchRequest(
                query=request.query,
                limit=request.limit + request.offset
            )
            
            # Get results from each search type
            semantic_response = self.semantic_search(semantic_request)
            fulltext_response = self.fulltext_search(fulltext_request)
            
            # Merge and score results
            score_map: Dict[str, float] = {}
            faq_map: Dict[str, SearchResult] = {}
            
            # Add semantic results
            for result in semantic_response.results:
                score_map[result.faq.id] = result.score * request.semantic_weight
                faq_map[result.faq.id] = result
            
            # Add full-text results
            for result in fulltext_response.results:
                faq_id = result.faq.id
                if faq_id in score_map:
                    score_map[faq_id] += result.score * request.fulltext_weight
                else:
                    score_map[faq_id] = result.score * request.fulltext_weight
                    faq_map[faq_id] = result
            
            # Apply metadata filters if provided
            if request.metadata_filters:
                metadata_response = self.metadata_search(request.metadata_filters)
                metadata_ids = {r.faq.id for r in metadata_response.results}
                
                # Keep only FAQs that match metadata filters
                score_map = {k: v for k, v in score_map.items() if k in metadata_ids}
                faq_map = {k: v for k, v in faq_map.items() if k in metadata_ids}
            
            # Sort by publication date descending, and then by combined score
            sorted_results = sorted(
                score_map.items(),
                key=lambda x: (
                    faq_map[x[0]].faq.document_publish_date or datetime.min,
                    x[1]
                ),
                reverse=True
            )
            
            # Apply pagination
            paginated_results = sorted_results[request.offset:request.offset + request.limit]
            
            # Rebuild result objects with combined scores
            results = [
                SearchResult(
                    faq=faq_map[faq_id].faq,
                    score=score / (request.semantic_weight + request.fulltext_weight),
                    match_type="combined",
                    matched_fields=["question", "answer"]
                )
                for faq_id, score in paginated_results
            ]
            
            response_time_ms = self._get_elapsed_ms(start_time)
            
            # Log search
            self._log_search(
                query=request.query,
                search_type="combined",
                results_count=len(results),
                top_result_id=results[0].faq.id if results else None,
                response_time_ms=response_time_ms,
                applied_filters=vars(request.metadata_filters) if request.metadata_filters else None,
                user_id=user_id
            )
            
            return SearchResponse(
                query=request.query,
                total_results=len(score_map),
                results=results,
                response_time_ms=response_time_ms,
                filters_applied=vars(request.metadata_filters) if request.metadata_filters else None
            )
        
        except Exception as e:
            logger.error(f"Combined search failed: {e}")
            raise
    
    # Helper methods
    
    def _faq_to_response(self, faq: FAQ) -> FAQResponse:
        """Convert FAQ model to response dict"""
        
        metadata_entries = [
            MetadataResponse(
                id=m.id,
                faq_id=m.faq_id,
                department=m.department,
                topic=m.topic,
                category=m.category,
                subcategory=m.subcategory,
                risk_level=m.risk_level,
                compliance_status=m.compliance_status,
                authority=m.authority,
                compliance_framework=m.compliance_framework,
                publication_date=m.publication_date,
                custom_attributes=m.custom_attributes or {},
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in faq.metadata_entries
        ]
        
        # Fetch historical answers
        historical = []
        if hasattr(faq, 'historical_answers'):
            historical = [
                {
                    "id": h.id,
                    "answer": h.answer,
                    "source_url": h.source_url,
                    "category": h.category,
                    "subtopic": h.subtopic,
                    "topic": h.topic,
                    "document_publish_date": h.document_publish_date,
                    "is_historic": True,
                    "isHistoric": True,
                }
                for h in faq.historical_answers
            ]
        
        return FAQResponse(
            id=faq.id,
            question=faq.question,
            answer=faq.answer,
            source_url=faq.source_url,
            category=faq.category,
            topic=faq.topic,
            subtopic=faq.subtopic,
            document_publish_date=faq.document_publish_date,
            historical_answers=historical,
            extraction_date=faq.extraction_date,
            extracted_by=faq.extracted_by,
            is_active=faq.is_active,
            is_verified=faq.is_verified,
            created_at=faq.created_at,
            updated_at=faq.updated_at,
            metadata_entries=metadata_entries,
            related_faq_ids=[r.id for r in faq.related_faqs]
        )
    
    def _calculate_text_relevance(self, question: str, answer: str, terms: List[str]) -> float:
        """Calculate text relevance score"""
        combined_text = (question + " " + answer).lower()
        score = 0.0
        
        for term in terms:
            # Question matches worth more
            question_matches = question.lower().count(term)
            answer_matches = answer.lower().count(term)
            
            score += (question_matches * 2) + answer_matches
        
        # Normalize
        max_possible = len(terms) * 2
        return min(score / max_possible, 1.0) if max_possible > 0 else 0.0
    
    def _get_elapsed_ms(self, start_time: datetime) -> float:
        """Get elapsed time in milliseconds"""
        return (datetime.utcnow() - start_time).total_seconds() * 1000
    
    def _log_search(
        self,
        query: str,
        search_type: str,
        results_count: int,
        top_result_id: Optional[str] = None,
        response_time_ms: float = 0.0,
        applied_filters: Optional[Dict] = None,
        user_id: Optional[str] = None
    ):
        """Log search query for analytics"""
        try:
            log_entry = SearchLog(
                query_text=query,
                search_type=search_type,
                results_count=results_count,
                top_result_id=top_result_id,
                applied_filters=applied_filters or {},
                response_time_ms=response_time_ms,
                user_id=user_id,
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to log search: {e}")
