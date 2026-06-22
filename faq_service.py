"""
FAQ service - business logic for FAQ operations
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from models import FAQ, FAQMetadata, FAQVersion, ImplementationChecklist, SearchLog, faq_related_association
from schemas import (
    FAQCreate, FAQUpdate, FAQResponse, MetadataCreate, 
    ImplementationChecklistCreate, RelatedFAQsRequest
)
from embeddings import get_embedding_service
from vector_db import get_vector_db
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class FAQService:
    """Service for FAQ operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.vector_db = get_vector_db()
    
    def create_faq(self, faq_data: FAQCreate) -> FAQ:
        """Create new FAQ with embedding (performs smart upsert and tracks change history)"""
        try:
            # Check if an active FAQ with the same question and same category already exists
            existing_faq = self.db.query(FAQ).filter(
                and_(
                    func.lower(FAQ.question) == func.lower(faq_data.question),
                    func.coalesce(func.lower(FAQ.category), '') == func.coalesce(func.lower(faq_data.category), ''),
                    FAQ.is_active == True
                )
            ).first()
            
            if existing_faq:
                # If answer has changed, store history and update existing record
                if existing_faq.answer.strip() != faq_data.answer.strip():
                    logger.info(f"Detected answer change for FAQ question: '{faq_data.question[:40]}...'. Versioning and updating.")
                    
                    # Get current max version number
                    max_version = self.db.query(func.max(FAQVersion.version_number)).filter(
                        FAQVersion.faq_id == existing_faq.id
                    ).scalar() or 0
                    
                    # Store previous Q&A in FAQVersion as a historical record
                    old_version = FAQVersion(
                        faq_id=existing_faq.id,
                        version_number=max_version + 1,
                        question=existing_faq.question,
                        answer=existing_faq.answer,
                        source_url=existing_faq.source_url,
                        category=existing_faq.category,
                        topic=existing_faq.topic,
                        subtopic=existing_faq.subtopic,
                        document_publish_date=existing_faq.document_publish_date,
                        change_type="updated",
                        change_reason="Automatically updated during scraper ingestion due to answer content change",
                        changed_by=faq_data.extracted_by or "sebi_scraper",
                        created_at=datetime.utcnow()
                    )
                    self.db.add(old_version)
                    
                    # Update active record to new answer and properties
                    existing_faq.answer = faq_data.answer
                    existing_faq.full_text_searchable = f"{existing_faq.question} {faq_data.answer}"
                    existing_faq.source_url = faq_data.source_url or existing_faq.source_url
                    existing_faq.category = faq_data.category or existing_faq.category
                    existing_faq.topic = faq_data.topic or existing_faq.topic
                    existing_faq.subtopic = faq_data.subtopic or existing_faq.subtopic
                    existing_faq.document_publish_date = faq_data.document_publish_date or existing_faq.document_publish_date
                    existing_faq.extracted_by = faq_data.extracted_by or existing_faq.extracted_by
                    existing_faq.updated_at = datetime.utcnow()
                    
                    # Update metadata entry
                    if faq_data.metadata:
                        self.db.query(FAQMetadata).filter(FAQMetadata.faq_id == existing_faq.id).delete()
                        metadata = FAQMetadata(
                            faq_id=existing_faq.id,
                            department=faq_data.metadata.department,
                            topic=faq_data.metadata.topic,
                            category=faq_data.metadata.category,
                            subcategory=faq_data.metadata.subcategory,
                            risk_level=faq_data.metadata.risk_level,
                            compliance_status=faq_data.metadata.compliance_status,
                            authority=faq_data.metadata.authority,
                            compliance_framework=faq_data.metadata.compliance_framework,
                            publication_date=faq_data.metadata.publication_date,
                            custom_attributes=faq_data.metadata.custom_attributes,
                        )
                        self.db.add(metadata)
                        
                    # Regenerate vector embedding
                    embedding = self.embedding_service.encode_faq(
                        existing_faq.question, 
                        existing_faq.answer
                    )
                    self.vector_db.update_embedding(
                        faq_id=existing_faq.id,
                        embedding=embedding,
                        metadata={
                            "category": existing_faq.category,
                            "topic": existing_faq.topic,
                            "subtopic": existing_faq.subtopic,
                            "source_url": existing_faq.source_url,
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    )
                    
                    self.db.commit()
                    self.db.refresh(existing_faq)
                    logger.info(f"Updated existing FAQ {existing_faq.id} and stored version {max_version + 1}.")
                    return existing_faq
                else:
                    # Answer is identical, skip update
                    logger.info(f"Skipping duplicate FAQ question with identical answer: '{faq_data.question[:40]}...'.")
                    return existing_faq

            # Create FAQ record
            faq = FAQ(
                question=faq_data.question,
                answer=faq_data.answer,
                source_url=faq_data.source_url,
                category=faq_data.category,
                topic=faq_data.topic,
                subtopic=faq_data.subtopic,
                document_publish_date=faq_data.document_publish_date,
                extracted_by=faq_data.extracted_by,
                full_text_searchable=f"{faq_data.question} {faq_data.answer}",
            )
            
            self.db.add(faq)
            self.db.flush()  # Get the ID
            
            # Generate and store embedding
            embedding = self.embedding_service.encode_faq(
                faq_data.question, 
                faq_data.answer
            )
            faq.embedding_vector = str(faq.id)
            
            # Store in Qdrant with full attributes
            qdrant_meta = {
                "category": faq.category,
                "topic": faq.topic,
                "subtopic": faq.subtopic,
                "document_publish_date": faq.document_publish_date.isoformat() if faq.document_publish_date else None,
                "source_url": faq.source_url
            }

            self.vector_db.store_embedding(
                faq_id=faq.id,
                embedding=embedding,
                metadata=qdrant_meta
            )
            
            # Add metadata if provided
            if faq_data.metadata:
                metadata = FAQMetadata(
                    faq_id=faq.id,
                    department=faq_data.metadata.department,
                    topic=faq_data.metadata.topic,
                    category=faq_data.metadata.category,
                    subcategory=faq_data.metadata.subcategory,
                    risk_level=faq_data.metadata.risk_level,
                    compliance_status=faq_data.metadata.compliance_status,
                    authority=faq_data.metadata.authority,
                    compliance_framework=faq_data.metadata.compliance_framework,
                    publication_date=faq_data.metadata.publication_date,
                    custom_attributes=faq_data.metadata.custom_attributes,
                )
                self.db.add(metadata)
            
            # Create initial version
            version = FAQVersion(
                faq_id=faq.id,
                version_number=1,
                question=faq_data.question,
                answer=faq_data.answer,
                source_url=faq_data.source_url,
                category=faq_data.category,
                topic=faq_data.topic,
                subtopic=faq_data.subtopic,
                document_publish_date=faq_data.document_publish_date,
                change_type="created",
                changed_by=faq_data.extracted_by or "system",
            )
            self.db.add(version)
            
            self.db.commit()
            self.db.refresh(faq)
            
            logger.info(f"Created FAQ {faq.id}")
            return faq
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create FAQ: {e}")
            raise
    
    def get_faq(self, faq_id: str) -> Optional[FAQ]:
        """Get FAQ by ID"""
        return self.db.query(FAQ).filter(FAQ.id == faq_id).first()
    
    def get_faqs(self, skip: int = 0, limit: int = 100, is_active: bool = True) -> List[FAQ]:
        """Get list of FAQs with pagination"""
        query = self.db.query(FAQ)
        if is_active:
            query = query.filter(FAQ.is_active == True)
        return query.offset(skip).limit(limit).all()
    
    def update_faq(self, faq_id: str, update_data: FAQUpdate) -> Optional[FAQ]:
        """Update FAQ and create version record"""
        try:
            faq = self.get_faq(faq_id)
            if not faq:
                return None
            
            # Track changes
            has_changes = False
            
            if update_data.question and update_data.question != faq.question:
                faq.question = update_data.question
                has_changes = True
            
            if update_data.answer and update_data.answer != faq.answer:
                faq.answer = update_data.answer
                has_changes = True
            
            if update_data.source_url is not None:
                faq.source_url = update_data.source_url
            
            if update_data.is_verified is not None:
                faq.is_verified = update_data.is_verified
            
            # Update full text searchable
            faq.full_text_searchable = f"{faq.question} {faq.answer}"
            
            # Create version if there are changes
            if has_changes:
                # Get max version number
                max_version = self.db.query(func.max(FAQVersion.version_number)).filter(
                    FAQVersion.faq_id == faq_id
                ).scalar() or 0
                
                version = FAQVersion(
                    faq_id=faq_id,
                    version_number=max_version + 1,
                    question=faq.question,
                    answer=faq.answer,
                    source_url=faq.source_url,
                    category=faq.category,
                    topic=faq.topic,
                    subtopic=faq.subtopic,
                    document_publish_date=faq.document_publish_date,
                    change_type="updated",
                    change_reason=update_data.change_reason,
                    changed_by="system",
                )
                self.db.add(version)
                
                # Re-generate and update embedding
                embedding = self.embedding_service.encode_faq(faq.question, faq.answer)
                self.vector_db.update_embedding(
                    faq_id=faq_id,
                    embedding=embedding,
                    metadata={"updated_at": datetime.utcnow().isoformat()}
                )
            
            # Update metadata if provided
            if update_data.metadata:
                # Delete old metadata
                self.db.query(FAQMetadata).filter(FAQMetadata.faq_id == faq_id).delete()
                
                # Add new metadata
                metadata = FAQMetadata(
                    faq_id=faq_id,
                    department=update_data.metadata.department,
                    topic=update_data.metadata.topic,
                    category=update_data.metadata.category,
                    subcategory=update_data.metadata.subcategory,
                    risk_level=update_data.metadata.risk_level,
                    compliance_status=update_data.metadata.compliance_status,
                    authority=update_data.metadata.authority,
                    compliance_framework=update_data.metadata.compliance_framework,
                    custom_attributes=update_data.metadata.custom_attributes,
                )
                self.db.add(metadata)
            
            faq.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(faq)
            
            logger.info(f"Updated FAQ {faq_id}")
            return faq
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update FAQ {faq_id}: {e}")
            raise
    
    def delete_faq(self, faq_id: str) -> bool:
        """Soft delete FAQ"""
        try:
            faq = self.get_faq(faq_id)
            if not faq:
                return False
            
            faq.is_active = False
            faq.updated_at = datetime.utcnow()
            
            # Delete from vector DB
            self.vector_db.delete_embedding(faq_id)
            
            self.db.commit()
            logger.info(f"Deleted FAQ {faq_id}")
            return True
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete FAQ {faq_id}: {e}")
            raise
    
    def add_related_faq(self, faq_id: str, related_faq_ids: List[str]) -> bool:
        """Link related FAQs"""
        try:
            faq = self.get_faq(faq_id)
            if not faq:
                return False
            
            for related_id in related_faq_ids:
                related_faq = self.get_faq(related_id)
                if related_faq and related_faq not in faq.related_faqs:
                    faq.related_faqs.append(related_faq)
            
            self.db.commit()
            logger.info(f"Added related FAQs for {faq_id}")
            return True
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add related FAQs: {e}")
            raise
    
    def add_checklist(
        self, 
        faq_id: str, 
        checklist_data: ImplementationChecklistCreate
    ) -> Optional[ImplementationChecklist]:
        """Add implementation checklist to FAQ"""
        try:
            checklist = ImplementationChecklist(
                faq_id=faq_id,
                title=checklist_data.title,
                description=checklist_data.description,
                items=checklist_data.items,
                priority=checklist_data.priority,
                estimated_effort=checklist_data.estimated_effort,
                applicable_departments=checklist_data.applicable_departments,
            )
            self.db.add(checklist)
            self.db.commit()
            self.db.refresh(checklist)
            
            logger.info(f"Added checklist to FAQ {faq_id}")
            return checklist
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add checklist: {e}")
            raise
    
    def get_faq_stats(self) -> Dict[str, Any]:
        """Get FAQ statistics"""
        total = self.db.query(func.count(FAQ.id)).filter(FAQ.is_active == True).scalar()
        verified = self.db.query(func.count(FAQ.id)).filter(
            and_(FAQ.is_active == True, FAQ.is_verified == True)
        ).scalar()
        
        # Count by department
        dept_counts = self.db.query(
            FAQMetadata.department, 
            func.count(FAQ.id)
        ).join(FAQ).filter(FAQ.is_active == True).group_by(
            FAQMetadata.department
        ).all()

        # Count by risk level
        risk_counts = self.db.query(
            FAQMetadata.risk_level, 
            func.count(FAQ.id)
        ).join(FAQ).filter(FAQ.is_active == True).group_by(
            FAQMetadata.risk_level
        ).all()

        # Count by compliance status
        compliance_counts = self.db.query(
            FAQMetadata.compliance_status, 
            func.count(FAQ.id)
        ).join(FAQ).filter(FAQ.is_active == True).group_by(
            FAQMetadata.compliance_status
        ).all()
        
        return {
            "total_faqs": total or 0,
            "verified_faqs": verified or 0,
            "faqs_by_department": {d or "Unassigned": c for d, c in dept_counts},
            "faqs_by_risk_level": {r or "Unassigned": c for r, c in risk_counts},
            "faqs_by_compliance_status": {s or "Unassigned": c for s, c in compliance_counts},
            "last_updated": datetime.utcnow(),
        }
