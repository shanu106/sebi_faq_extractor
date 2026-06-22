"""
SEBI FAQ Extraction & Database Ingestion - Complete Workflow
Extracts from SEBI website and stores in PostgreSQL + Qdrant
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def run_extraction():
    """Run SEBI FAQ extraction"""
    print_header("STEP 1: EXTRACTING SEBI FAQs FROM WEBSITE")
    
    try:
        from extract_sebi_faqs import extract_sebi_faqs
        
        print("Starting extraction from SEBI website...")
        print("This may take 2-5 minutes depending on SEBI server response...\n")
        
        faqs = extract_sebi_faqs()
        
        if not faqs:
            logger.error("❌ No FAQs extracted. Please check:")
            logger.error("   - Internet connection")
            logger.error("   - SEBI website availability")
            logger.error("   - Proxy/Firewall settings")
            return None
        
        logger.info(f"✅ Successfully extracted {len(faqs)} FAQs")
        return faqs
    
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.error("Install: pip install beautifulsoup4 requests PyPDF2")
        return None
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        return None


def validate_faqs(faqs: List[Dict[str, Any]]) -> Tuple[List[Dict], List[str]]:
    """Validate extracted FAQs"""
    print_header("STEP 2: VALIDATING EXTRACTED FAQs")
    
    valid_faqs = []
    errors = []
    
    for idx, faq in enumerate(faqs, 1):
        try:
            # Required fields
            if not faq.get('question'):
                errors.append(f"FAQ #{idx}: Missing question")
                continue
            if not faq.get('answer'):
                errors.append(f"FAQ #{idx}: Missing answer")
                continue
            
            # Validate lengths
            if len(faq['question']) < 10:
                errors.append(f"FAQ #{idx}: Question too short")
                continue
            if len(faq['answer']) < 20:
                errors.append(f"FAQ #{idx}: Answer too short")
                continue
            
            valid_faqs.append(faq)
        
        except Exception as e:
            errors.append(f"FAQ #{idx}: {str(e)}")
    
    logger.info(f"✅ Valid FAQs: {len(valid_faqs)}/{len(faqs)}")
    if errors:
        logger.warning(f"⚠️  Validation errors: {len(errors)}")
        for error in errors[:5]:
            logger.warning(f"   - {error}")
    
    return valid_faqs, errors


def save_extraction(faqs: List[Dict[str, Any]], filename: str = "sebi_faqs_extracted.json"):
    """Save extraction to JSON"""
    print_header("STEP 3: SAVING EXTRACTED DATA")
    
    try:
        output_path = Path(filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(faqs, f, indent=2, ensure_ascii=False)
        
        file_size_kb = output_path.stat().st_size / 1024
        logger.info(f"✅ Saved {len(faqs)} FAQs to {filename}")
        logger.info(f"   File size: {file_size_kb:.2f} KB")
        return filename
    
    except Exception as e:
        logger.error(f"❌ Failed to save: {e}")
        return None


def ingest_to_database(faqs: List[Dict[str, Any]]):
    """Ingest FAQs to database"""
    print_header("STEP 4: INGESTING FAQs TO DATABASE")
    
    try:
        from sqlalchemy.orm import Session
        from database import SessionLocal
        from faq_service import FAQService
        from schemas import FAQCreate, MetadataCreate
        
        db = SessionLocal()
        service = FAQService(db)
        
        successful = 0
        failed = 0
        failed_items = []
        
        logger.info(f"Starting ingestion of {len(faqs)} FAQs...\n")
        
        for idx, faq_data in enumerate(faqs, 1):
            try:
                # Extract metadata
                metadata_dict = faq_data.pop('metadata', {})
                metadata = MetadataCreate(**metadata_dict) if metadata_dict else None
                
                # Create FAQ
                faq_create = FAQCreate(
                    question=faq_data['question'],
                    answer=faq_data['answer'],
                    source_url=faq_data.get('source_url'),
                    extracted_by=faq_data.get('extracted_by', 'sebi_scraper'),
                    metadata=metadata
                )
                
                service.create_faq(faq_create)
                successful += 1
                
                # Progress indicator
                if idx % 10 == 0:
                    logger.info(f"  Progress: {idx}/{len(faqs)} ✓")
                if idx % 50 == 0:
                    logger.info(f"  ✅ {successful} ingested, ⏱️  working...\n")
            
            except Exception as e:
                failed += 1
                failed_items.append({
                    'index': idx,
                    'question': faq_data.get('question', '')[:50],
                    'error': str(e)
                })
                logger.debug(f"Failed FAQ #{idx}: {e}")
        
        db.close()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"INGESTION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"✅ Successfully ingested: {successful}/{len(faqs)}")
        if failed > 0:
            logger.warning(f"❌ Failed: {failed}")
            logger.warning(f"\nFirst 5 failures:")
            for item in failed_items[:5]:
                logger.warning(f"  - #{item['index']}: {item['error']}")
        
        return successful, failed
    
    except ImportError as e:
        logger.error(f"❌ Cannot import database modules: {e}")
        logger.error("Ensure FastAPI app is in same directory")
        return 0, len(faqs)
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        logger.error("Check database connection and ensure PostgreSQL is running")
        return 0, len(faqs)


def verify_ingestion():
    """Verify FAQs were ingested"""
    print_header("STEP 5: VERIFYING INGESTION")
    
    try:
        from database import SessionLocal
        from models import FAQ
        
        db = SessionLocal()
        
        # Count FAQs
        total_faqs = db.query(FAQ).filter(FAQ.is_active == True).count()
        verified = db.query(FAQ).filter(FAQ.is_verified == False, FAQ.is_active == True).count()
        
        logger.info(f"✅ Total FAQs in database: {total_faqs}")
        logger.info(f"   Unverified FAQs: {verified} (ready for manual verification)")
        
        # Show sample FAQs
        sample_faqs = db.query(FAQ).filter(FAQ.is_active == True).limit(3).all()
        if sample_faqs:
            logger.info(f"\nSample FAQs in database:")
            for faq in sample_faqs:
                logger.info(f"\n  Q: {faq.question[:60]}...")
                logger.info(f"  A: {faq.answer[:80]}...")
                logger.info(f"  Source: {faq.source_url}")
        
        db.close()
        return total_faqs
    
    except Exception as e:
        logger.error(f"⚠️  Could not verify (database may not be running): {e}")
        return 0


def main():
    """Main workflow"""
    print_header("SEBI FAQ EXTRACTION & INGESTION SYSTEM")
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    # Step 1: Extract
    faqs = run_extraction()
    if not faqs:
        logger.error("\n❌ Extraction failed. Exiting.")
        sys.exit(1)
    
    # Step 2: Validate
    valid_faqs, errors = validate_faqs(faqs)
    if not valid_faqs:
        logger.error("\n❌ No valid FAQs found. Exiting.")
        sys.exit(1)
    
    # Step 3: Save
    json_file = save_extraction(valid_faqs)
    if not json_file:
        logger.error("\n❌ Failed to save. Exiting.")
        sys.exit(1)
    
    # Step 4: Ask for confirmation
    print_header("STEP 4: READY FOR DATABASE INGESTION")
    print(f"Summary:")
    print(f"  📊 Total FAQs extracted: {len(valid_faqs)}")
    print(f"  ✅ Valid FAQs: {len(valid_faqs)}")
    if errors:
        print(f"  ⚠️  Validation errors: {len(errors)}")
    print(f"  📁 JSON file: {json_file}\n")
    
    response = input("Proceed with database ingestion? (yes/no): ").strip().lower()
    if response != 'yes':
        logger.info("Ingestion cancelled. FAQs saved to " + json_file)
        sys.exit(0)
    
    # Step 5: Ingest
    successful, failed = ingest_to_database(valid_faqs)
    if successful == 0:
        logger.error("\n❌ Ingestion failed. Please check:")
        logger.error("   - PostgreSQL is running: docker-compose up -d postgres")
        logger.error("   - Database connection: psql -U shahnawaj -d postgres")
        sys.exit(1)
    
    # Step 6: Verify
    total = verify_ingestion()
    
    # Final summary
    print_header("✅ EXTRACTION & INGESTION COMPLETE")
    print(f"Successfully extracted and ingested: {successful} FAQs")
    print(f"Total in database: {total}")
    print(f"\nNext steps:")
    print(f"  1. Manual verification of FAQs")
    print(f"  2. Test semantic search: http://localhost:8000/docs")
    print(f"  3. View statistics: GET /api/v1/stats/faqs")
    print(f"  4. Customize metadata schema as needed")
    print(f"\nStarted: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
