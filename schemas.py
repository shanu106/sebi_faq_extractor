"""
Pydantic schemas for SEBI FAQ System API
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# ============================================================================
# FAQ Schemas
# ============================================================================

class MetadataCreate(BaseModel):
    """Metadata creation schema - flexible for user customization"""
    department: Optional[str] = None
    topic: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    risk_level: Optional[str] = None
    compliance_status: Optional[str] = None
    authority: Optional[str] = None
    compliance_framework: Optional[str] = None
    publication_date: Optional[datetime] = None
    custom_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MetadataResponse(MetadataCreate):
    """Metadata response schema"""
    id: str
    faq_id: str
    created_at: datetime
    updated_at: datetime


class FAQCreate(BaseModel):
    """FAQ creation schema"""
    question: str = Field(..., min_length=10, max_length=1000)
    answer: str = Field(..., min_length=20)
    source_url: Optional[str] = None
    extracted_by: Optional[str] = None
    metadata: Optional[MetadataCreate] = None
    category: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    document_publish_date: Optional[datetime] = None


class FAQUpdate(BaseModel):
    """FAQ update schema"""
    question: Optional[str] = None
    answer: Optional[str] = None
    source_url: Optional[str] = None
    is_verified: Optional[bool] = None
    metadata: Optional[MetadataCreate] = None
    change_reason: Optional[str] = None  # For version tracking


class HistoricalAnswer(BaseModel):
    """Historical version of an FAQ answer"""
    id: str
    answer: str
    source_url: Optional[str] = None
    category: Optional[str] = None
    subtopic: Optional[str] = None
    topic: Optional[str] = None
    document_publish_date: Optional[datetime] = None
    is_historic: bool = True
    isHistoric: bool = True


class FAQResponse(BaseModel):
    """FAQ response schema"""
    id: str
    question: str
    answer: str
    source_url: Optional[str]
    category: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    document_publish_date: Optional[datetime] = None
    historical_answers: List[HistoricalAnswer] = []
    extraction_date: datetime
    extracted_by: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    metadata_entries: List[MetadataResponse] = []
    related_faq_ids: List[str] = []
    is_historic: bool = False
    isHistoric: bool = False



class FAQDetailResponse(FAQResponse):
    """Detailed FAQ response with versions and checklists"""
    versions: List['FAQVersionResponse'] = []
    checklists: List['ImplementationChecklistResponse'] = []


class ChecklistItemSchema(BaseModel):
    """Individual checklist item"""
    id: str
    title: str
    completed: bool = False
    notes: Optional[str] = None


class ImplementationChecklistCreate(BaseModel):
    """Implementation checklist creation"""
    title: str
    description: Optional[str] = None
    items: List[ChecklistItemSchema] = []
    priority: Optional[str] = None
    estimated_effort: Optional[str] = None
    applicable_departments: Optional[List[str]] = None


class ImplementationChecklistResponse(ImplementationChecklistCreate):
    """Implementation checklist response"""
    id: str
    faq_id: str
    created_at: datetime
    updated_at: datetime


class FAQVersionResponse(BaseModel):
    """FAQ version history response"""
    id: str
    version_number: int
    question: str
    answer: str
    change_type: str
    change_reason: Optional[str]
    changed_by: Optional[str]
    created_at: datetime


# ============================================================================
# Search Schemas
# ============================================================================

class SemanticSearchRequest(BaseModel):
    """Semantic search request"""
    query: str = Field(..., min_length=3, max_length=1000)
    limit: int = Field(10, ge=1, le=100)
    min_similarity: float = Field(0.5, ge=0.0, le=1.0)


class MetadataFilterRequest(BaseModel):
    """Metadata filtering request"""
    department: Optional[str] = None
    category: Optional[str] = None
    risk_level: Optional[str] = None
    compliance_status: Optional[str] = None
    authority: Optional[str] = None
    compliance_framework: Optional[str] = None
    is_verified: Optional[bool] = None
    custom_filters: Optional[Dict[str, Any]] = None


class FullTextSearchRequest(BaseModel):
    """Full-text search request"""
    query: str = Field(..., min_length=3)
    limit: int = Field(10, ge=1, le=100)
    search_fields: Optional[List[str]] = None  # "question", "answer"


class CombinedSearchRequest(BaseModel):
    """Combined search with semantic + metadata + full-text"""
    query: str = Field(..., min_length=3, max_length=1000)
    
    # Semantic search params
    semantic_weight: float = Field(0.5, ge=0.0, le=1.0)
    min_similarity: float = Field(0.5, ge=0.0, le=1.0)
    
    # Metadata filters
    metadata_filters: Optional[MetadataFilterRequest] = None
    
    # Full-text params
    fulltext_weight: float = Field(0.3, ge=0.0, le=1.0)
    
    # Result params
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchResult(BaseModel):
    """Individual search result"""
    faq: FAQResponse
    score: float = Field(..., description="Relevance score 0-1")
    match_type: Literal["semantic", "fulltext", "metadata", "combined"]
    matched_fields: Optional[List[str]] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata"""
    query: str
    total_results: int
    results: List[SearchResult]
    response_time_ms: float
    filters_applied: Optional[Dict[str, Any]] = None


# ============================================================================
# Ingestion Schemas
# ============================================================================

class FAQBulkIngestionRequest(BaseModel):
    """Bulk FAQ ingestion"""
    faqs: List[FAQCreate] = Field(..., min_items=1, max_items=1000)
    skip_duplicates: bool = True


class FAQBulkIngestionResponse(BaseModel):
    """Bulk ingestion response"""
    total_ingested: int
    successful: int
    failed: int
    failed_items: List[Dict[str, Any]] = []
    ingestion_time_seconds: float


class RelatedFAQsRequest(BaseModel):
    """Link related FAQs"""
    faq_id: str
    related_faq_ids: List[str]


# ============================================================================
# Schema Configuration Schemas
# ============================================================================

class SchemaFieldDefinition(BaseModel):
    """Definition for a metadata field"""
    name: str
    field_type: Literal["string", "integer", "boolean", "json", "enum"]
    required: bool = False
    description: Optional[str] = None
    enum_values: Optional[List[str]] = None  # For enum type
    default_value: Optional[Any] = None


class SchemaConfigRequest(BaseModel):
    """Customize the metadata schema"""
    custom_fields: List[SchemaFieldDefinition]
    remove_fields: Optional[List[str]] = None


class SchemaConfigResponse(BaseModel):
    """Current schema configuration"""
    standard_fields: List[str]
    custom_fields: List[SchemaFieldDefinition]
    last_updated: datetime


# ============================================================================
# Analytics Schemas
# ============================================================================

class SearchAnalytics(BaseModel):
    """Search analytics summary"""
    total_searches: int
    most_common_queries: List[tuple[str, int]]
    average_response_time_ms: float
    search_type_distribution: Dict[str, int]
    period_start: datetime
    period_end: datetime


class FAQStats(BaseModel):
    """FAQ statistics"""
    total_faqs: int
    verified_faqs: int
    faqs_by_department: Dict[str, int]
    faqs_by_risk_level: Dict[str, int]
    faqs_by_compliance_status: Dict[str, int]
    last_updated: datetime


class AdminCreate(BaseModel):
    username: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# Update forward references
FAQDetailResponse.model_rebuild()

