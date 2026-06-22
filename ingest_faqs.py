"""
Example: Ingest SEBI FAQs from JSON file
"""

import json
import logging
from pathlib import Path
from typing import List

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from faq_service import FAQService
from schemas import FAQCreate, MetadataCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_faqs_from_json(json_file: str, api_base_url: str = "http://localhost:8000/api/v1"):
    """
    Ingest FAQs from a JSON file via API
    
    Args:
        json_file: Path to JSON file with FAQs
        api_base_url: Base URL of the API
    """
    try:
        # Load FAQs
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        faqs = data if isinstance(data, list) else data.get('faqs', [])
        
        if not faqs:
            logger.error("No FAQs found in JSON file")
            return
        
        logger.info(f"Loaded {len(faqs)} FAQs from {json_file}")
        
        # Ingest via API
        response = requests.post(
            f"{api_base_url}/faqs/bulk-ingest",
            json={
                "faqs": faqs,
                "skip_duplicates": True
            },
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✓ Ingested: {result['successful']}/{result['total_ingested']}")
            
            if result['failed'] > 0:
                logger.warning(f"✗ Failed: {result['failed']}")
                for item in result['failed_items'][:5]:  # Show first 5 failures
                    logger.warning(f"  - {item}")
            
            logger.info(f"Ingestion took {result['ingestion_time_seconds']:.2f}s")
        else:
            logger.error(f"API Error: {response.status_code}")
            logger.error(response.text)
    
    except FileNotFoundError:
        logger.error(f"File not found: {json_file}")
    except Exception as e:
        logger.error(f"Error ingesting FAQs: {e}")


def ingest_faqs_from_db(json_file: str):
    """
    Ingest FAQs directly via database (for testing)
    
    Args:
        json_file: Path to JSON file with FAQs
    """
    from database import SessionLocal
    
    try:
        # Load FAQs
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        faqs_data = data if isinstance(data, list) else data.get('faqs', [])
        
        if not faqs_data:
            logger.error("No FAQs found in JSON file")
            return
        
        logger.info(f"Loaded {len(faqs_data)} FAQs")
        
        # Create session and service
        db = SessionLocal()
        service = FAQService(db)
        
        successful = 0
        failed = 0
        
        for idx, faq_data in enumerate(faqs_data, 1):
            try:
                # Convert to schema
                metadata_dict = faq_data.pop('metadata', {})
                metadata = MetadataCreate(**metadata_dict) if metadata_dict else None
                
                faq_create = FAQCreate(
                    **faq_data,
                    metadata=metadata
                )
                
                service.create_faq(faq_create)
                successful += 1
                
                if idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{len(faqs_data)}")
            
            except Exception as e:
                failed += 1
                logger.error(f"Failed to ingest FAQ {idx}: {e}")
        
        logger.info(f"✓ Successfully ingested: {successful}/{len(faqs_data)}")
        if failed > 0:
            logger.warning(f"✗ Failed: {failed}")
        
        db.close()
    
    except FileNotFoundError:
        logger.error(f"File not found: {json_file}")
    except Exception as e:
        logger.error(f"Error: {e}")


# Example: Create sample FAQ JSON file
def create_sample_faqs_json(output_file: str = "sample_faqs.json"):
    """Create a sample FAQ JSON file"""
    
    sample_faqs = [
        {
            "question": "What are the key compliance requirements for listed companies under SEBI regulations?",
            "answer": "Listed companies must comply with several key requirements:\n1. Periodic disclosures - quarterly results, annual reports\n2. Corporate governance norms - board composition, committee structure\n3. Listing Agreement compliance - stock exchange requirements\n4. Insider trading regulations - prevention of insider trading\n5. Related party transactions - disclosure and approval\n6. Material events reporting - timely disclosure of material developments",
            "source_url": "https://www.sebi.gov.in/faq/",
            "extracted_by": "system",
            "metadata": {
                "department": "Listing & Disclosures",
                "category": "Corporate Governance",
                "subcategory": "Compliance Requirements",
                "risk_level": "high",
                "compliance_status": "mandatory",
                "authority": "SEBI",
                "compliance_framework": "DORA"
            }
        },
        {
            "question": "What is the process for applying for mutual fund registration?",
            "answer": "The mutual fund registration process involves:\n1. Sponsor registration with SEBI\n2. Appointment of trustees and custodian\n3. Submission of fund scheme documents\n4. SEBI approval before launch\n5. Appointment of authorized dealers\n6. Compliance with ongoing reporting requirements",
            "source_url": "https://www.sebi.gov.in/faq/",
            "extracted_by": "system",
            "metadata": {
                "department": "Mutual Funds",
                "category": "Registration & Authorization",
                "risk_level": "medium",
                "compliance_status": "mandatory",
                "authority": "SEBI",
                "compliance_framework": "MF_REGULATIONS"
            }
        },
        {
            "question": "What are the audit committee requirements for listed companies?",
            "answer": "Audit committee requirements include:\n1. Composition - At least 3 members, minimum 2 independent\n2. Expertise - At least one member with accounting/audit expertise\n3. Functions - Review financial statements, internal audit, risk management\n4. Meetings - Quarterly meetings with external and internal auditors\n5. Reporting - Annual report disclosure of audit committee details",
            "source_url": "https://www.sebi.gov.in/faq/",
            "extracted_by": "system",
            "metadata": {
                "department": "Investor Protection",
                "category": "Corporate Governance",
                "risk_level": "high",
                "compliance_status": "mandatory",
                "authority": "SEBI",
                "compliance_framework": "CG_CODE"
            }
        },
        {
            "question": "What information should be disclosed for related party transactions?",
            "answer": "Related party transaction disclosures must include:\n1. Nature of transaction\n2. Amount and percentage of sales/purchases\n3. Terms and conditions\n4. Justification for exemption (if any)\n5. Board approval status\n6. Shareholder approval status\n7. Transfer pricing policy details",
            "source_url": "https://www.sebi.gov.in/faq/",
            "extracted_by": "system",
            "metadata": {
                "department": "Compliance & Disclosures",
                "category": "Related Party Transactions",
                "risk_level": "high",
                "compliance_status": "mandatory",
                "authority": "SEBI",
                "compliance_framework": "IND-AS"
            }
        },
        {
            "question": "How should insider trading regulations be implemented?",
            "answer": "Insider trading prevention requires:\n1. Trading window restrictions - close before results announcement\n2. Pre-clearance mechanism - for designated persons\n3. Restricted list management - persons with unpublished price-sensitive info\n4. Trading policy adoption - clearly documented\n5. Reporting - disclosure to stock exchange\n6. Blackout periods - prevent trading during sensitive periods",
            "source_url": "https://www.sebi.gov.in/faq/",
            "extracted_by": "system",
            "metadata": {
                "department": "Investor Protection",
                "category": "Insider Trading Prevention",
                "risk_level": "high",
                "compliance_status": "mandatory",
                "authority": "SEBI",
                "compliance_framework": "PROHIBITION_OF_INSIDER_TRADING"
            }
        }
    ]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sample_faqs, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Created sample FAQ file: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        logger.info(f"Ingesting FAQs from {json_file}")
        ingest_faqs_from_json(json_file)
    else:
        # Create sample file and ingest
        sample_file = "sample_faqs.json"
        create_sample_faqs_json(sample_file)
        
        logger.info("\nIngesting sample FAQs...")
        logger.info("Option 1: Via API (ensure app is running on http://localhost:8000)")
        ingest_faqs_from_json(sample_file)
        
        logger.info("\nOption 2: Via direct database connection")
        # ingest_faqs_from_db(sample_file)
