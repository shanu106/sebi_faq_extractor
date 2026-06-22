"""
SEBI FAQ Extraction & Ingestion System
Hybrid approach: HTML scraping + PDF extraction + Database storage
"""

import requests
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import PyPDF2
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SEBIFAQExtractor:
    """Extract FAQs from SEBI website"""
    
    def __init__(self):
        self.base_url = "https://www.sebi.gov.in"
        self.faq_url = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doFaq=yes"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.faqs = []
        
    def extract_all(self) -> List[Dict[str, Any]]:
        """Main extraction process"""
        logger.info("Starting SEBI FAQ extraction...")
        
        try:
            # Step 1: Get all FAQ categories
            categories = self._extract_faq_categories()
            logger.info(f"Found {len(categories)} FAQ categories")
            
            # Step 2: Extract from each category
            for idx, category in enumerate(categories, 1):
                logger.info(f"[{idx}/{len(categories)}] Processing: {category['name']}")
                
                before_count = len(self.faqs)
                
                if category['url'].endswith('.pdf'):
                    # PDF file
                    self._extract_from_pdf(category)
                else:
                    # HTML page
                    self._extract_from_html_page(category)
                
                after_count = len(self.faqs)
                extracted_count = after_count - before_count
                
                if extracted_count == 0:
                    logger.warning(f"  ⚠️ No FAQs extracted from url: {category['url']}. Activating offline fallback dataset...")
                    fallback_faqs = self._get_fallback_faqs(category['url'], category['name'])
                    if fallback_faqs:
                        self.faqs.extend(fallback_faqs)
                        logger.info(f"  ✅ Restored {len(fallback_faqs)} FAQs from fallback dataset")
            
            logger.info(f"✓ Total FAQs extracted: {len(self.faqs)}")
            return self.faqs
        
        except Exception as e:
            logger.error(f"Error during extraction: {e}")
            return []
    
    def _extract_faq_categories(self) -> List[Dict[str, Any]]:
        """Extract FAQ category links from main FAQ page"""
        categories = []
        
        try:
            response = self.session.get(self.faq_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for links with "View Details" or FAQ-related links
            # SEBI structure: links are typically in divs with class containing 'faq' or similar
            
            # Pattern 1: FAQ category divs with "View Details" links
            faq_sections = soup.find_all('div', class_=re.compile(r'faq|category', re.I))
            
            # Pattern 2: Direct links containing 'faq'
            links = soup.find_all('a', href=re.compile(r'faq|faqfile', re.I))
            
            seen_urls = set()
            
            for link in links:
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                
                if not href or href in seen_urls:
                    continue
                
                # Filter for FAQ-related links
                if 'faq' in href.lower() or 'FAQ' in text:
                    full_url = urljoin(self.base_url, href)
                    
                    category = {
                        'name': text[:100] if text else 'FAQ',
                        'url': full_url,
                        'extracted_date': datetime.utcnow().isoformat(),
                    }
                    
                    categories.append(category)
                    seen_urls.add(href)
            
            # If few categories found, try alternative parsing
            if len(categories) < 5:
                logger.warning("Few categories found with standard parsing, trying alternative...")
                categories.extend(self._extract_categories_alternative(soup))
            
            return categories
        
        except Exception as e:
            logger.error(f"Error extracting categories: {e}")
            return []
    
    def _extract_categories_alternative(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Alternative category extraction method"""
        categories = []
        seen = set()
        
        # Look for text "View Details" and extract surrounding context
        for a_tag in soup.find_all('a'):
            text = a_tag.get_text(strip=True)
            href = a_tag.get('href', '').strip()
            
            # Look for common FAQ category patterns
            if 'view' in text.lower() and href and href not in seen:
                parent = a_tag.find_parent(['li', 'div', 'tr'])
                if parent:
                    parent_text = parent.get_text(strip=True)
                    if len(parent_text) > 10 and len(parent_text) < 200:
                        full_url = urljoin(self.base_url, href)
                        categories.append({
                            'name': parent_text[:100],
                            'url': full_url,
                            'extracted_date': datetime.utcnow().isoformat(),
                        })
                        seen.add(href)
        
        return categories
    
    def _extract_from_html_page(self, category: Dict[str, Any]):
        """Extract FAQs from HTML page"""
        try:
            response = self.session.get(category['url'], timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract Q&A pairs - common patterns:
            # Pattern 1: <dt>Question</dt><dd>Answer</dd>
            dt_dd_pairs = soup.find_all('dt')
            for dt in dt_dd_pairs:
                dd = dt.find_next('dd')
                if dd:
                    question = dt.get_text(strip=True)
                    answer = dd.get_text(strip=True)
                    
                    if question and answer and len(question) > 5:
                        self._add_faq(
                            question=question,
                            answer=answer,
                            source_url=category['url'],
                            category=category['name']
                        )
            
            # Pattern 2: <h3>Question</h3><p>Answer</p>
            h3_tags = soup.find_all(['h3', 'h4'])
            for h_tag in h3_tags:
                p_tag = h_tag.find_next('p')
                if p_tag:
                    question = h_tag.get_text(strip=True)
                    answer = p_tag.get_text(strip=True)
                    
                    if question and answer and len(question) > 5 and len(answer) > 10:
                        self._add_faq(
                            question=question,
                            answer=answer,
                            source_url=category['url'],
                            category=category['name']
                        )
            
            # Pattern 3: <b>Question</b> or <strong>Question</strong> followed by text
            bold_tags = soup.find_all(['b', 'strong'])
            for bold in bold_tags:
                text = bold.get_text(strip=True)
                if len(text) > 5 and len(text) < 200 and '?' in text:
                    # Try to get the answer from next elements
                    next_elem = bold.find_next(['p', 'div'])
                    if next_elem:
                        answer = next_elem.get_text(strip=True)
                        if answer and len(answer) > 10:
                            self._add_faq(
                                question=text,
                                answer=answer,
                                source_url=category['url'],
                                category=category['name']
                            )
            
            logger.info(f"  Extracted {len([f for f in self.faqs if f['source_url'] == category['url']])} FAQs")
        
        except Exception as e:
            logger.warning(f"Error extracting from {category['url']}: {e}")
    
    def _extract_from_pdf(self, category: Dict[str, Any]):
        """Extract FAQs from PDF files"""
        try:
            response = self.session.get(category['url'], timeout=20)
            response.raise_for_status()
            
            from excel_extractor import scrape_faqs_from_pdf_bytes
            scraped = scrape_faqs_from_pdf_bytes(response.content, category['url'])
            
            for faq in scraped:
                self._add_faq(
                    question=faq['question'],
                    answer=faq['answer'],
                    source_url=faq['source_url'],
                    category=category['name']
                )
                    
            logger.info(f"  Extracted {len(scraped)} FAQs from PDF")
            
        except Exception as e:
            logger.warning(f"Error extracting from PDF {category['url']}: {e}")

    def _get_fallback_faqs(self, url: str, category_name: str) -> List[Dict[str, Any]]:
        """Load FAQs for a URL from pre-extracted JSON file as fallback"""
        fallback_list = []
        try:
            with open('sebi_faqs_extracted.json', 'r', encoding='utf-8') as f:
                pre_extracted = json.load(f)
            
            seen_questions = {faq['question'].lower() for faq in self.faqs}
            
            for item in pre_extracted:
                if item.get('source_url') == url:
                    q = self._clean_text(item['question'])
                    if q.lower() not in seen_questions:
                        fallback_list.append({
                            'question': q,
                            'answer': self._clean_text(item['answer']),
                            'source_url': url,
                            'extracted_by': 'offline_fallback',
                            'category': category_name,
                            'department': item.get('department', self._extract_department(category_name)),
                            'extracted_date': datetime.utcnow().isoformat(),
                            'metadata': item.get('metadata', {
                                'department': self._extract_department(category_name),
                                'category': category_name,
                                'subcategory': self._extract_subcategory(category_name),
                                'risk_level': 'medium',
                                'compliance_status': 'informational',
                                'authority': 'SEBI',
                                'compliance_framework': 'SEBI_REGULATIONS',
                            })
                        })
                        seen_questions.add(q.lower())
        except Exception as e:
            logger.error(f"Error loading fallback FAQs for URL {url}: {e}")
        return fallback_list
    
    def _add_faq(self, question: str, answer: str, source_url: str, category: str):
        """Add FAQ to collection with validation"""
        # Clean up question and answer
        question = self._clean_text(question)
        answer = self._clean_text(answer)
        
        # Validate
        if len(question) < 10:
            return
        if len(answer) < 20:
            return
        
        # Check for duplicates (same question, same category, and same answer)
        for faq in self.faqs:
            if faq['question'].lower() == question.lower() and faq['category'].lower() == category.lower() and faq['answer'].strip() == answer.strip():
                return
        
        # Extract department/category metadata
        dept = self._extract_department(category)
        
        faq = {
            'question': question,
            'answer': answer,
            'source_url': source_url,
            'extracted_by': 'sebi_scraper',
            'category': category,
            'department': dept,
            'extracted_date': datetime.utcnow().isoformat(),
            'metadata': {
                'department': dept,
                'category': category,
                'subcategory': self._extract_subcategory(category),
                'risk_level': 'medium',  # Default
                'compliance_status': 'informational',  # Default for FAQ
                'authority': 'SEBI',
                'compliance_framework': 'SEBI_REGULATIONS',
            }
        }
        
        self.faqs.append(faq)
    
    def _clean_text(self, text: str) -> str:
        """Clean text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return text.strip()
    
    def _extract_department(self, category: str) -> str:
        """Infer department from category name"""
        category_lower = category.lower()
        
        if 'mutual' in category_lower:
            return 'Mutual Funds'
        elif 'listing' in category_lower or 'icdr' in category_lower:
            return 'Listing & Disclosures'
        elif 'derivative' in category_lower or 'trading' in category_lower:
            return 'Market Operations'
        elif 'governance' in category_lower or 'corporate' in category_lower:
            return 'Corporate Governance'
        elif 'investor' in category_lower or 'grievance' in category_lower:
            return 'Investor Protection'
        elif 'research' in category_lower or 'analyst' in category_lower:
            return 'Research'
        elif 'intermediary' in category_lower or 'broker' in category_lower:
            return 'Intermediaries'
        elif 'bond' in category_lower or 'debenture' in category_lower:
            return 'Debt Markets'
        else:
            return 'Compliance & General'
    
    def _extract_subcategory(self, category: str) -> str:
        """Extract subcategory from category name"""
        # Return first 50 chars of category
        return category[:50]
    
    def save_to_json(self, filename: str = 'sebi_faqs_extracted.json'):
        """Save extracted FAQs to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.faqs, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Saved {len(self.faqs)} FAQs to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
            return None


def extract_sebi_faqs() -> List[Dict[str, Any]]:
    """Main extraction function"""
    extractor = SEBIFAQExtractor()
    faqs = extractor.extract_all()
    
    if faqs:
        json_file = extractor.save_to_json()
        logger.info(f"\n✓ Extraction complete!")
        logger.info(f"  Total FAQs: {len(faqs)}")
        logger.info(f"  JSON file: {json_file}")
        return faqs
    else:
        logger.error("No FAQs extracted")
        return []


if __name__ == "__main__":
    import sys
    
    # Extract FAQs
    faqs = extract_sebi_faqs()
    
    if faqs:
        print(f"\n{'='*60}")
        print(f"EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total FAQs: {len(faqs)}")
        
        # Show sample
        print(f"\nSample FAQs (first 3):")
        for idx, faq in enumerate(faqs[:3], 1):
            print(f"\n{idx}. Q: {faq['question'][:80]}...")
            print(f"   A: {faq['answer'][:100]}...")
            print(f"   Category: {faq['category']}")
        
        # Ingest?
        print(f"\n{'='*60}")
        response = input("Ingest FAQs into database? (yes/no): ").strip().lower()
        
        if response == 'yes':
            from ingest_faqs import ingest_faqs_from_json
            ingest_faqs_from_json('sebi_faqs_extracted.json')
