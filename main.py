"""
FastAPI main application
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
from typing import List, Optional
from datetime import datetime

from config import settings
from database import get_db, init_db
from models import FAQ, SearchLog, Admin
from faq_service import FAQService
from search_service import SearchService
from schemas import (
    FAQCreate, FAQUpdate, FAQResponse, FAQDetailResponse,
    SemanticSearchRequest, MetadataFilterRequest, FullTextSearchRequest,
    CombinedSearchRequest, SearchResponse, RelatedFAQsRequest,
    FAQBulkIngestionRequest, FAQBulkIngestionResponse,
    ImplementationChecklistCreate, ImplementationChecklistResponse,
    FAQStats, SearchAnalytics,
    AdminCreate, AdminLogin, TokenResponse
)

import jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import timedelta


# Logging setup
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent SEBI FAQ System with Vector Search",
)

# CORS middleware
origins = list(settings.cors_origins)
for origin in ["https://shanu106.github.io/sebi_faq_extractor/", "https://shanu106.github.io"]:
    if origin not in origins:
        origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Authentication Utilities & Dependencies
# ============================================================================

import bcrypt

security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Admin:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
        
    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None:
        raise HTTPException(status_code=401, detail="Admin not found")
        
    if admin.active_token != token:
        raise HTTPException(status_code=401, detail="Token has been revoked or expired")
        
    return admin



# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
def startup_event():
    """Initialize database on startup"""
    logger.info("Starting SEBI FAQ System")
    init_db()
    logger.info("Database initialized")


@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down SEBI FAQ System")


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.get(f"{settings.api_prefix}/auth/check")
def check_admin_setup(db: Session = Depends(get_db)):
    """Check if any admin is registered in the system"""
    count = db.query(Admin).count()
    return {"has_admin": count > 0}


@app.post(f"{settings.api_prefix}/auth/register-admin", response_model=TokenResponse, status_code=201)
def register_admin(admin_data: AdminCreate, db: Session = Depends(get_db)):
    """Register the initial admin. Works once only. Revokes itself after one user."""
    # Check if any admin exists
    if db.query(Admin).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="Admin registration has been revoked. An administrator is already registered."
        )
    
    # Hash password and create admin
    hashed = get_password_hash(admin_data.password)
    admin = Admin(
        username=admin_data.username,
        hashed_password=hashed
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    # Issue initial token
    access_token = create_access_token(data={"sub": admin.username})
    admin.active_token = access_token
    db.commit()
    
    return TokenResponse(access_token=access_token, token_type="bearer")


@app.post(f"{settings.api_prefix}/auth/login", response_model=TokenResponse)
def login_admin(credentials: AdminLogin, db: Session = Depends(get_db)):
    """Authenticate admin and issue JWT token"""
    admin = db.query(Admin).filter(Admin.username == credentials.username).first()
    if not admin or not verify_password(credentials.password, admin.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    
    # Generate token
    access_token = create_access_token(data={"sub": admin.username})
    admin.active_token = access_token
    db.commit()
    
    return TokenResponse(access_token=access_token, token_type="bearer")


@app.post(f"{settings.api_prefix}/auth/logout")
def logout_admin(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Log out active admin by revoking token"""
    admin.active_token = None
    db.commit()
    return {"detail": "Logged out successfully"}


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# FAQ Management Endpoints
# ============================================================================

@app.post(f"{settings.api_prefix}/faqs", response_model=FAQResponse, status_code=201)
def create_faq(
    faq_data: FAQCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Create a new FAQ"""
    try:
        service = FAQService(db)
        faq = service.create_faq(faq_data)
        return faq
    except Exception as e:
        logger.error(f"Error creating FAQ: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get(f"{settings.api_prefix}/faqs/{{faq_id}}", response_model=FAQDetailResponse)
def get_faq(
    faq_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific FAQ with all details"""
    try:
        service = FAQService(db)
        faq = service.get_faq(faq_id)
        
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        # Build detailed response
        versions = [
            {
                "id": v.id,
                "version_number": v.version_number,
                "question": v.question,
                "answer": v.answer,
                "change_type": v.change_type,
                "change_reason": v.change_reason,
                "changed_by": v.changed_by,
                "created_at": v.created_at,
            }
            for v in faq.versions
        ]
        
        checklists = [
            {
                "id": c.id,
                "faq_id": c.faq_id,
                "title": c.title,
                "description": c.description,
                "items": c.items,
                "priority": c.priority,
                "estimated_effort": c.estimated_effort,
                "applicable_departments": c.applicable_departments,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in faq.checklists
        ]
        
        metadata_entries = [
            {
                "id": m.id,
                "faq_id": m.faq_id,
                "department": m.department,
                "category": m.category,
                "subcategory": m.subcategory,
                "risk_level": m.risk_level,
                "compliance_status": m.compliance_status,
                "authority": m.authority,
                "compliance_framework": m.compliance_framework,
                "custom_attributes": m.custom_attributes,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in faq.metadata_entries
        ]
        
        return FAQDetailResponse(
            id=faq.id,
            question=faq.question,
            answer=faq.answer,
            source_url=faq.source_url,
            extraction_date=faq.extraction_date,
            extracted_by=faq.extracted_by,
            is_active=faq.is_active,
            is_verified=faq.is_verified,
            created_at=faq.created_at,
            updated_at=faq.updated_at,
            metadata_entries=metadata_entries,
            related_faq_ids=[r.id for r in faq.related_faqs],
            versions=versions,
            checklists=checklists,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving FAQ: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{settings.api_prefix}/faqs", response_model=List[FAQResponse])
def list_faqs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool = Query(True),
    db: Session = Depends(get_db)
):
    """List all FAQs with pagination"""
    try:
        service = FAQService(db)
        faqs = service.get_faqs(skip=skip, limit=limit, is_active=is_active)
        return faqs
    except Exception as e:
        logger.error(f"Error listing FAQs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put(f"{settings.api_prefix}/faqs/{{faq_id}}", response_model=FAQResponse)
def update_faq(
    faq_id: str,
    update_data: FAQUpdate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Update an FAQ"""
    try:
        service = FAQService(db)
        faq = service.update_faq(faq_id, update_data)
        
        if not faq:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        return faq
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating FAQ: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete(f"{settings.api_prefix}/faqs/{{faq_id}}", status_code=204)
def delete_faq(
    faq_id: str,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Delete (soft delete) an FAQ"""
    try:
        service = FAQService(db)
        if not service.delete_faq(faq_id):
            raise HTTPException(status_code=404, detail="FAQ not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting FAQ: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post(f"{settings.api_prefix}/faqs/bulk-ingest", response_model=FAQBulkIngestionResponse)
def bulk_ingest_faqs(
    request: FAQBulkIngestionRequest,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    admin: Admin = Depends(get_current_admin)
):
    """Bulk ingest FAQs"""
    try:
        service = FAQService(db)
        start_time = datetime.utcnow()
        
        successful = 0
        failed = 0
        failed_items = []
        
        from sqlalchemy import func, and_
        for faq_data in request.faqs:
            try:
                # Check for duplicates if requested
                if request.skip_duplicates:
                    existing = db.query(FAQ).filter(
                        and_(
                            func.lower(FAQ.question) == func.lower(faq_data.question),
                            func.coalesce(func.lower(FAQ.category), '') == func.coalesce(func.lower(faq_data.category), ''),
                            FAQ.is_active == True
                        )
                    ).first()
                    if existing and existing.answer.strip() == faq_data.answer.strip():
                        failed += 1
                        failed_items.append({"question": faq_data.question, "error": "Duplicate"})
                        continue
                
                service.create_faq(faq_data)
                successful += 1
            except Exception as e:
                failed += 1
                failed_items.append({"question": faq_data.question, "error": str(e)})
        
        ingestion_time = (datetime.utcnow() - start_time).total_seconds()
        
        return FAQBulkIngestionResponse(
            total_ingested=len(request.faqs),
            successful=successful,
            failed=failed,
            failed_items=failed_items,
            ingestion_time_seconds=ingestion_time,
        )
    except Exception as e:
        logger.error(f"Error in bulk ingestion: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def infer_metadata(pdf_url: str):
    # Try to get something from the filename
    filename = pdf_url.split('/')[-1].replace('%20', ' ').replace('-', ' ').replace('_', ' ')
    if '.pdf' in filename.lower():
        filename = filename[:filename.lower().rfind('.pdf')]
    
    # Infer department
    filename_lower = filename.lower()
    if 'mutual' in filename_lower:
        dept = 'Mutual Funds'
    elif 'listing' in filename_lower or 'icdr' in filename_lower:
        dept = 'Listing & Disclosures'
    elif 'derivative' in filename_lower or 'trading' in filename_lower:
        dept = 'Market Operations'
    elif 'governance' in filename_lower or 'corporate' in filename_lower:
        dept = 'Corporate Governance'
    elif 'investor' in filename_lower or 'grievance' in filename_lower:
        dept = 'Investor Protection'
    elif 'research' in filename_lower or 'analyst' in filename_lower:
        dept = 'Research'
    elif 'intermediary' in filename_lower or 'broker' in filename_lower:
        dept = 'Intermediaries'
    elif 'bond' in filename_lower or 'debenture' in filename_lower:
        dept = 'Debt Markets'
    else:
        dept = 'Compliance & General'
        
    category_name = filename[:100] if filename else "Excel Extracted PDF"
    
    return {
        "department": dept,
        "category": category_name,
        "subcategory": category_name[:50],
        "risk_level": "medium",
        "compliance_status": "informational",
        "authority": "SEBI",
        "compliance_framework": "SEBI_REGULATIONS"
    }


@app.post(f"{settings.api_prefix}/faqs/extract-excel")
async def extract_faqs_from_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """
    Upload an Excel or CSV file, extract PDF links and metadata attributes row by row,
    scrape raw PDFs, check duplicates, and ingest them into PostgreSQL + Qdrant.
    """
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")

    try:
        contents = await file.read()
        
        # Parse spreadsheet rows
        from excel_extractor import parse_excel_or_csv, scrape_faqs_from_pdf
        rows = parse_excel_or_csv(contents, file.filename)
        
        if not rows:
            return {
                "success": True,
                "message": "No valid rows containing PDF links found in the uploaded file.",
                "pdf_links_found": [],
                "total_extracted_faqs": 0,
                "total_ingested_faqs": 0,
                "total_failed_faqs": 0,
                "extracted_faqs": []
            }
        
        service = FAQService(db)
        extracted_faqs = []
        total_extracted = 0
        total_ingested = 0
        total_failed = 0
        
        # Cache scraped PDFs to avoid downloading same URL multiple times
        pdf_cache = {}
        unique_urls = list(set(r["pdf_url"] for r in rows))
        
        for r in rows:
            url = r["pdf_url"]
            pub_date = r["document_publish_date"]
            topic = r["topic"]
            sub_topic = r["sub_topic"]
            category = r["category"]
            
            # Scrape PDF (with caching)
            # Scrape PDF (with caching and robust fallback)
            if url not in pdf_cache:
                scraped_faqs = []
                try:
                    scraped_faqs = scrape_faqs_from_pdf(url)
                except Exception as e:
                    logger.warning(f"Error scraping PDF from {url}: {e}. Activating fallback...")
                
                # If scraping failed or returned 0 FAQs, try local JSON fallback
                if not scraped_faqs:
                    try:
                        import json
                        with open('sebi_faqs_extracted.json', 'r', encoding='utf-8') as f:
                            local_faqs = json.load(f)
                        fallback_faqs = [
                            {"question": item["question"], "answer": item["answer"], "source_url": url}
                            for item in local_faqs if item.get("source_url") == url
                        ]
                        if fallback_faqs:
                            logger.info(f"Fallback activated for {url}: Restored {len(fallback_faqs)} FAQs from local database.")
                            scraped_faqs = fallback_faqs
                    except Exception as fallback_err:
                        logger.error(f"Fallback failed for {url}: {fallback_err}")
                
                pdf_cache[url] = scraped_faqs
            
            faqs = pdf_cache[url]
            if not faqs:
                extracted_faqs.append({
                    "question": "",
                    "answer": "",
                    "source_url": url,
                    "status": "failed",
                    "error": "No FAQs found and no fallback data available"
                })
                total_failed += 1
                continue
                
            for faq_data in faqs:
                total_extracted += 1
                question = faq_data["question"]
                answer = faq_data["answer"]
                
                # Check for duplicates (same question and same category) in DB
                from sqlalchemy import and_, func
                existing_faqs = db.query(FAQ).filter(
                    and_(
                        FAQ.question == question,
                        func.coalesce(FAQ.category, '') == (category or '')
                    )
                ).all()
                
                is_duplicate = False
                for existing in existing_faqs:
                    if existing.answer.strip() == answer.strip():
                        # Same question and same answer: update document_publish_date if the new one is newer
                        if pub_date and (not existing.document_publish_date or pub_date > existing.document_publish_date):
                            existing.document_publish_date = pub_date
                            db.commit()
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    total_failed += 1
                    extracted_faqs.append({
                        "question": question,
                        "answer": answer,
                        "source_url": url,
                        "status": "failed",
                        "error": "Duplicate Q&A already exists in database"
                    })
                    continue
                
                # Create metadata matching spreadsheet attributes + defaults
                from schemas import MetadataCreate, FAQCreate
                metadata = MetadataCreate(
                    department=topic,  # Topic maps to department for filtering compat
                    topic=topic,
                    category=category,
                    subcategory=sub_topic,
                    risk_level="medium",
                    compliance_status="mandatory" if any(w in answer.lower() for w in ["must", "shall", "required", "mandatory"]) else "informational",
                    authority="SEBI",
                    compliance_framework="SEBI_REGULATIONS",
                    publication_date=pub_date
                )
                
                # Create FAQ Create object
                faq_create = FAQCreate(
                    question=question,
                    answer=answer,
                    source_url=url,
                    extracted_by="excel_pdf_extractor",
                    metadata=metadata,
                    category=category,
                    topic=topic,
                    subtopic=sub_topic,
                    document_publish_date=pub_date
                )
                
                # Ingest
                service.create_faq(faq_create)
                total_ingested += 1
                extracted_faqs.append({
                    "question": question,
                    "answer": answer,
                    "source_url": url,
                    "status": "success"
                })
                
        return {
            "success": True,
            "message": f"Processed Excel/CSV file. Found {len(unique_urls)} unique PDF links across {len(rows)} rows.",
            "pdf_links_found": unique_urls,
            "total_extracted_faqs": total_extracted,
            "total_ingested_faqs": total_ingested,
            "total_failed_faqs": total_failed,
            "extracted_faqs": extracted_faqs
        }
        
    except Exception as e:
        logger.error(f"Error in extract_faqs_from_excel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process Excel file: {str(e)}")


@app.post(f"{settings.api_prefix}/faqs/update-metadata")
async def update_faq_metadata(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """
    Upload an Excel or CSV file containing URL, category, topic, subtopic, and document publish date columns.
    If the PDF URL exists in the database, extract and update its metadata without re-scraping the PDF.
    """
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")

    try:
        contents = await file.read()
        
        # Parse spreadsheet rows
        from excel_extractor import parse_excel_or_csv
        rows = parse_excel_or_csv(contents, file.filename)
        
        if not rows:
            return {
                "success": True,
                "message": "No valid rows containing PDF links found in the uploaded file.",
                "total_rows_processed": 0,
                "total_updated_faqs": 0,
                "details": []
            }
        
        # We need vector_db client to update Qdrant payloads
        from vector_db import get_vector_db
        from models import FAQMetadata
        vector_db = get_vector_db()
        
        total_rows = 0
        total_updated = 0
        details = []
        
        for r in rows:
            url = r["pdf_url"]
            pub_date = r["document_publish_date"]
            topic = r["topic"]
            sub_topic = r["sub_topic"]
            category = r["category"]
            
            total_rows += 1
            
            # Find matching active FAQs in DB
            matching_faqs = db.query(FAQ).filter(FAQ.source_url == url, FAQ.is_active == True).all()
            
            if not matching_faqs:
                details.append({
                    "pdf_url": url,
                    "status": "skipped",
                    "reason": "URL not found in database",
                    "updated_count": 0
                })
                continue
            
            updated_count = 0
            for faq in matching_faqs:
                # Update PostgreSQL columns directly on FAQ
                if category is not None:
                    faq.category = category
                if topic is not None:
                    faq.topic = topic
                if sub_topic is not None:
                    faq.subtopic = sub_topic
                if pub_date is not None:
                    faq.document_publish_date = pub_date
                
                # Rebuild full text searchable if any field changed
                faq.full_text_searchable = f"{faq.question} {faq.answer}"
                
                # Also update corresponding FAQMetadata table record
                metadata = db.query(FAQMetadata).filter(FAQMetadata.faq_id == faq.id).first()
                if metadata:
                    if category is not None:
                        metadata.category = category
                    if topic is not None:
                        metadata.topic = topic
                        metadata.department = topic
                    if sub_topic is not None:
                        metadata.subcategory = sub_topic
                    if pub_date is not None:
                        metadata.publication_date = pub_date
                else:
                    # Create one with defaults + these fields
                    metadata = FAQMetadata(
                        faq_id=faq.id,
                        department=topic,
                        topic=topic,
                        category=category,
                        subcategory=sub_topic,
                        risk_level="medium",
                        compliance_status="mandatory" if any(w in faq.answer.lower() for w in ["must", "shall", "required", "mandatory"]) else "informational",
                        authority="SEBI",
                        compliance_framework="SEBI_REGULATIONS",
                        publication_date=pub_date
                    )
                    db.add(metadata)
                
                # Update payload in Qdrant
                qdrant_meta = {}
                if category is not None:
                    qdrant_meta["category"] = category
                if topic is not None:
                    qdrant_meta["topic"] = topic
                if sub_topic is not None:
                    qdrant_meta["subtopic"] = sub_topic
                if pub_date is not None:
                    qdrant_meta["document_publish_date"] = pub_date.isoformat()
                
                try:
                    vector_db.update_payload(faq.id, qdrant_meta)
                except Exception as q_err:
                    logger.error(f"Failed to update Qdrant payload for FAQ {faq.id}: {q_err}")
                
                updated_count += 1
                total_updated += 1
            
            db.commit()
            details.append({
                "pdf_url": url,
                "status": "updated",
                "updated_count": updated_count
            })
            
        return {
            "success": True,
            "message": f"Processed {total_rows} spreadsheet rows. Updated metadata for {total_updated} FAQs across database & Qdrant.",
            "total_rows_processed": total_rows,
            "total_updated_faqs": total_updated,
            "details": details
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in update_faq_metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update metadata from file: {str(e)}")


@app.post(f"{settings.api_prefix}/faqs/extract-pdf")
async def extract_faqs_from_single_pdf(
    file: Optional[UploadFile] = File(None),
    pdf_url: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    subtopic: Optional[str] = Form(None),
    document_publish_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """
    Ingest a single PDF file (either uploaded local file or remote URL),
    extract FAQs, check duplicates, and store in PostgreSQL + Qdrant.
    """
    if not file and not pdf_url:
        raise HTTPException(status_code=400, detail="Please upload a PDF file or provide a PDF URL link.")
    if file and pdf_url:
        raise HTTPException(status_code=400, detail="Please provide either a file upload or a PDF URL, not both.")

    # 1. Parse dates if provided
    from excel_extractor import parse_date, scrape_faqs_from_pdf_bytes
    pub_date = None
    if document_publish_date:
        pub_date = parse_date(document_publish_date.strip())

    # 2. Get PDF bytes & canonical URL
    pdf_bytes = b""
    source_url = ""
    if file:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")
        pdf_bytes = await file.read()
        source_url = file.filename
    else:
        source_url = pdf_url.strip()
        if not source_url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid PDF URL format.")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(source_url, headers=headers)
                response.raise_for_status()
                pdf_bytes = response.content
        except Exception as e:
            logger.error(f"Failed to fetch PDF from {source_url}: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to download PDF from URL: {str(e)}")

    try:
        # 3. Extract Q&As
        faqs = scrape_faqs_from_pdf_bytes(pdf_bytes, source_url)
        if not faqs:
            return {
                "success": True,
                "message": "No FAQs extracted from the provided PDF document.",
                "total_extracted_faqs": 0,
                "total_ingested_faqs": 0,
                "total_failed_faqs": 0,
                "extracted_faqs": []
            }
        
        service = FAQService(db)
        extracted_faqs = []
        total_extracted = 0
        total_ingested = 0
        total_failed = 0

        for faq_data in faqs:
            total_extracted += 1
            question = faq_data["question"]
            answer = faq_data["answer"]
            
            # Check for duplicates (same question and same category) in DB
            from sqlalchemy import and_, func
            existing_faqs = db.query(FAQ).filter(
                and_(
                    FAQ.question == question,
                    func.coalesce(FAQ.category, '') == (category or '')
                )
            ).all()
            
            is_duplicate = False
            for existing in existing_faqs:
                if existing.answer.strip() == answer.strip():
                    # Update document_publish_date if the new one is newer
                    if pub_date and (not existing.document_publish_date or pub_date > existing.document_publish_date):
                        existing.document_publish_date = pub_date
                        db.commit()
                        
                        # Also update FAQMetadata table
                        from models import FAQMetadata
                        metadata_rec = db.query(FAQMetadata).filter(FAQMetadata.faq_id == existing.id).first()
                        if metadata_rec:
                            metadata_rec.publication_date = pub_date
                            db.commit()
                    is_duplicate = True
                    break
            
            if is_duplicate:
                total_failed += 1
                extracted_faqs.append({
                    "question": question,
                    "answer": answer,
                    "source_url": source_url,
                    "status": "failed",
                    "error": "Duplicate Q&A already exists in database"
                })
                continue
            
            # Create metadata object
            from schemas import MetadataCreate, FAQCreate
            metadata = MetadataCreate(
                department=topic,
                topic=topic,
                category=category,
                subcategory=subtopic,
                risk_level="medium",
                compliance_status="mandatory" if any(w in answer.lower() for w in ["must", "shall", "required", "mandatory"]) else "informational",
                authority="SEBI",
                compliance_framework="SEBI_REGULATIONS",
                publication_date=pub_date
            )
            
            # Ingest
            faq_create = FAQCreate(
                question=question,
                answer=answer,
                source_url=source_url,
                extracted_by="single_pdf_extractor",
                metadata=metadata,
                category=category,
                topic=topic,
                subtopic=subtopic,
                document_publish_date=pub_date
            )
            
            service.create_faq(faq_create)
            total_ingested += 1
            extracted_faqs.append({
                "question": question,
                "answer": answer,
                "source_url": source_url,
                "status": "success"
            })
            
        return {
            "success": True,
            "message": f"Processed PDF. Extracted {total_extracted} FAQs. Ingested {total_ingested} FAQs, skipped {total_failed} duplicates.",
            "total_extracted_faqs": total_extracted,
            "total_ingested_faqs": total_ingested,
            "total_failed_faqs": total_failed,
            "extracted_faqs": extracted_faqs
        }

    except Exception as e:
        logger.error(f"Error in extract_faqs_from_single_pdf: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")


@app.post(f"{settings.api_prefix}/faqs/{{faq_id}}/related")
def link_related_faqs(
    faq_id: str,
    request: RelatedFAQsRequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Link related FAQs"""
    try:
        service = FAQService(db)
        if not service.add_related_faq(faq_id, request.related_faq_ids):
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        return {"message": "Related FAQs linked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking related FAQs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post(f"{settings.api_prefix}/faqs/{{faq_id}}/checklists", response_model=ImplementationChecklistResponse)
def add_checklist(
    faq_id: str,
    checklist_data: ImplementationChecklistCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Add implementation checklist to FAQ"""
    try:
        service = FAQService(db)
        checklist = service.add_checklist(faq_id, checklist_data)
        
        if not checklist:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        return checklist
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding checklist: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Search Endpoints
# ============================================================================

@app.post(f"{settings.api_prefix}/search/semantic", response_model=SearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Semantic search using vector similarity"""
    try:
        service = SearchService(db)
        response = service.semantic_search(request, user_id=user_id)
        return response
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(f"{settings.api_prefix}/search/metadata", response_model=SearchResponse)
def metadata_search(
    request: MetadataFilterRequest,
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Search FAQs by metadata filters"""
    try:
        service = SearchService(db)
        response = service.metadata_search(request, limit=limit, user_id=user_id)
        return response
    except Exception as e:
        logger.error(f"Error in metadata search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(f"{settings.api_prefix}/search/fulltext", response_model=SearchResponse)
def fulltext_search(
    request: FullTextSearchRequest,
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Full-text search on question and answer"""
    try:
        service = SearchService(db)
        response = service.fulltext_search(request, user_id=user_id)
        return response
    except Exception as e:
        logger.error(f"Error in full-text search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(f"{settings.api_prefix}/search/combined", response_model=SearchResponse)
def combined_search(
    request: CombinedSearchRequest,
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Combined search with semantic + metadata + full-text"""
    try:
        service = SearchService(db)
        response = service.combined_search(request, user_id=user_id)
        return response
    except Exception as e:
        logger.error(f"Error in combined search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get(f"{settings.api_prefix}/stats/faqs", response_model=FAQStats)
def get_faq_stats(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Get FAQ statistics"""
    try:
        service = FAQService(db)
        stats = service.get_faq_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting FAQ stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{settings.api_prefix}/stats/searches", response_model=SearchAnalytics)
def get_search_analytics(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    """Get search analytics for the last N days"""
    try:
        from sqlalchemy import and_
        from datetime import datetime, timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get search logs
        logs = db.query(SearchLog).filter(
            and_(SearchLog.created_at >= start_date, SearchLog.created_at <= end_date)
        ).all()
        
        # Calculate analytics
        total_searches = len(logs)
        
        # Most common queries
        query_counts = {}
        for log in logs:
            query_counts[log.query_text] = query_counts.get(log.query_text, 0) + 1
        
        most_common = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Average response time
        total_time = sum(log.response_time_ms or 0 for log in logs)
        avg_response_time = total_time / total_searches if total_searches > 0 else 0
        
        # Search type distribution
        search_type_dist = {}
        for log in logs:
            search_type_dist[log.search_type] = search_type_dist.get(log.search_type, 0) + 1
        
        return SearchAnalytics(
            total_searches=total_searches,
            most_common_queries=most_common,
            average_response_time_ms=avg_response_time,
            search_type_distribution=search_type_dist,
            period_start=start_date,
            period_end=end_date,
        )
    except Exception as e:
        logger.error(f"Error getting search analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Root endpoint
# ============================================================================

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "SEBI FAQ Intelligent Retrieval System",
        "documentation": "/docs",
        "api_version": settings.api_prefix,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
