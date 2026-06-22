"""
SQLAlchemy ORM Models for SEBI FAQ System
"""

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, Boolean, 
    ForeignKey, Table, Index, JSON, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()


# Association table for many-to-many relationships
faq_related_association = Table(
    'faq_related_association',
    Base.metadata,
    Column('faq_id', String(36), ForeignKey('faqs.id'), primary_key=True),
    Column('related_faq_id', String(36), ForeignKey('faqs.id'), primary_key=True),
)


class FAQ(Base):
    """
    Core FAQ entity with question, answer, and content metadata
    """
    __tablename__ = 'faqs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question = Column(String(1000), nullable=False, index=True)
    answer = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=True, index=True)
    
    # Content metadata
    extraction_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = Column(String(255), nullable=True, index=True)
    topic = Column(String(255), nullable=True, index=True)
    subtopic = Column(String(255), nullable=True, index=True)
    document_publish_date = Column(DateTime, nullable=True, index=True)
    extracted_by = Column(String(255), nullable=True)  # who/what extracted it
    
    # Search & retrieval
    full_text_searchable = Column(Text, nullable=True)  # denormalized for FTS
    embedding_vector = Column(String(36), nullable=True)  # Reference to vector ID in Qdrant
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    metadata_entries = relationship("FAQMetadata", back_populates="faq", cascade="all, delete-orphan")
    versions = relationship("FAQVersion", back_populates="faq", cascade="all, delete-orphan")
    checklists = relationship("ImplementationChecklist", back_populates="faq", cascade="all, delete-orphan")
    related_faqs = relationship(
        "FAQ",
        secondary=faq_related_association,
        primaryjoin=id == faq_related_association.c.faq_id,
        secondaryjoin=id == faq_related_association.c.related_faq_id,
        foreign_keys=[faq_related_association.c.faq_id, faq_related_association.c.related_faq_id]
    )
    
    __table_args__ = (
        Index('idx_faq_created_active', 'created_at', 'is_active'),
        Index('idx_faq_verified_active', 'is_verified', 'is_active'),
    )


class FAQMetadata(Base):
    """
    Flexible metadata for FAQs - stores the quadrant classification and attributes
    Schema is JSON-configurable by user
    """
    __tablename__ = 'faq_metadata'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    faq_id = Column(String(36), ForeignKey('faqs.id'), nullable=False, index=True)
    
    # Standard metadata fields (expandable)
    department = Column(String(255), nullable=True, index=True)  # e.g., "Investor Protection", "Listing"
    topic = Column(String(255), nullable=True, index=True)
    category = Column(String(255), nullable=True, index=True)  # e.g., "Mutual Funds", "Research Analysts"
    subcategory = Column(String(255), nullable=True)
    publication_date = Column(DateTime, nullable=True)
    
    # Risk & Compliance Quadrant
    risk_level = Column(String(50), nullable=True, index=True)  # "high", "medium", "low"
    compliance_status = Column(String(50), nullable=True)  # "mandatory", "advisory", "informational"
    
    # Authority & Framework
    authority = Column(String(255), nullable=True)  # "SEBI", "Stock Exchange", etc.
    compliance_framework = Column(String(255), nullable=True)  # "DORA", "GDPR", "SOC2", etc.
    
    # Custom attributes (JSON for flexibility)
    custom_attributes = Column(JSON, nullable=True, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    faq = relationship("FAQ", back_populates="metadata_entries")
    
    __table_args__ = (
        Index('idx_metadata_dept_cat', 'department', 'category'),
        Index('idx_metadata_risk_compliance', 'risk_level', 'compliance_status'),
    )


class FAQVersion(Base):
    """
    Version history for change tracking and audit trail
    """
    __tablename__ = 'faq_versions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    faq_id = Column(String(36), ForeignKey('faqs.id'), nullable=False, index=True)
    
    version_number = Column(Integer, nullable=False)
    question = Column(String(1000), nullable=False)
    answer = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=True)
    category = Column(String(255), nullable=True)
    topic = Column(String(255), nullable=True)
    subtopic = Column(String(255), nullable=True)
    document_publish_date = Column(DateTime, nullable=True)
    
    # Change tracking
    change_type = Column(String(50), nullable=False)  # "created", "updated", "clarified"
    change_reason = Column(Text, nullable=True)
    changed_by = Column(String(255), nullable=True)  # User/system that made the change
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationship
    faq = relationship("FAQ", back_populates="versions")
    
    __table_args__ = (
        Index('idx_version_faq_number', 'faq_id', 'version_number'),
    )



class ImplementationChecklist(Base):
    """
    Implementation checklists derived from FAQs - action items for compliance
    """
    __tablename__ = 'implementation_checklists'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    faq_id = Column(String(36), ForeignKey('faqs.id'), nullable=False, index=True)
    
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # Checklist items (JSON format)
    items = Column(JSON, nullable=False, default=[])  # [{"id": "1", "title": "...", "completed": false}, ...]
    
    # Metadata
    priority = Column(String(50), nullable=True)  # "high", "medium", "low"
    estimated_effort = Column(String(255), nullable=True)  # "2 hours", "1 day", etc.
    applicable_departments = Column(JSON, nullable=True, default=[])  # Which depts need this
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    faq = relationship("FAQ", back_populates="checklists")


class SearchLog(Base):
    """
    Audit log for search queries - helps understand user behavior
    """
    __tablename__ = 'search_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Query details
    query_text = Column(String(1000), nullable=False)
    search_type = Column(String(50), nullable=False)  # "semantic", "filter", "combined"
    
    # Results
    results_count = Column(Integer, nullable=False)
    top_result_id = Column(String(36), nullable=True)
    
    # Filters applied
    applied_filters = Column(JSON, nullable=True, default={})
    
    # Response time
    response_time_ms = Column(Float, nullable=True)
    
    # User info (optional)
    user_id = Column(String(255), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Admin(Base):
    """
    Admin credentials for protected actions (stats, ingestion, extraction)
    """
    __tablename__ = 'admins'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    active_token = Column(Text, nullable=True)  # jwt token storage
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

