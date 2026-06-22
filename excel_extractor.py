"""
Excel URL Extractor and PDF FAQ Scraper Utilities
"""

import re
import csv
import logging
from io import BytesIO, StringIO
from typing import List, Dict, Any, Set, Optional
import requests
import openpyxl
import PyPDF2

logger = logging.getLogger(__name__)

def extract_pdf_links_from_excel(file_contents: bytes) -> List[str]:
    """
    Reads an Excel file and extracts all unique PDF URLs.
    Looks at cell text content and cell hyperlinks.
    """
    pdf_links: List[str] = []
    seen_links: Set[str] = set()

    # Regular expressions for finding HTTP/HTTPS URLs
    pdf_pattern = re.compile(r'https?://[^\s"\'<>]+?\.pdf(?:[?#][^\s"\'<>]*)?', re.IGNORECASE)
    general_url_pattern = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)

    try:
        wb = openpyxl.load_workbook(BytesIO(file_contents), data_only=True)
        for name in wb.sheetnames:
            sheet = wb[name]
            for row in sheet.iter_rows():
                for cell in row:
                    # 1. Check cell hyperlinks
                    if cell.hyperlink and cell.hyperlink.target:
                        url = cell.hyperlink.target
                        if '.pdf' in url.lower() and url not in seen_links:
                            seen_links.add(url)
                            pdf_links.append(url)
                            continue

                    # 2. Check cell text value
                    val = cell.value
                    if val and isinstance(val, str):
                        # Extract any matching PDF URL
                        matches = pdf_pattern.findall(val)
                        for url in matches:
                            if url not in seen_links:
                                seen_links.add(url)
                                pdf_links.append(url)
                        
                        # Fallback: scan any URLs and check for '.pdf'
                        if not matches:
                            urls = general_url_pattern.findall(val)
                            for url in urls:
                                if '.pdf' in url.lower() and url not in seen_links:
                                    seen_links.add(url)
                                    pdf_links.append(url)

    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        raise ValueError(f"Failed to parse Excel workbook: {str(e)}")

    logger.info(f"Extracted {len(pdf_links)} unique PDF links from Excel")
    return pdf_links


def extract_pdf_links_from_csv(file_contents: bytes) -> List[str]:
    """
    Reads a CSV file and extracts all unique PDF URLs.
    """
    pdf_links: List[str] = []
    seen_links: Set[str] = set()

    # Regular expressions for finding HTTP/HTTPS URLs
    pdf_pattern = re.compile(r'https?://[^\s"\'<>]+?\.pdf(?:[?#][^\s"\'<>]*)?', re.IGNORECASE)
    general_url_pattern = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)

    try:
        # Decode contents
        try:
            text = file_contents.decode('utf-8')
        except UnicodeDecodeError:
            text = file_contents.decode('latin-1')

        reader = csv.reader(StringIO(text))
        for row in reader:
            for val in row:
                if val:
                    # Extract any matching PDF URL
                    matches = pdf_pattern.findall(val)
                    for url in matches:
                        if url not in seen_links:
                            seen_links.add(url)
                            pdf_links.append(url)
                    
                    # Fallback: scan any URLs and check for '.pdf'
                    if not matches:
                        urls = general_url_pattern.findall(val)
                        for url in urls:
                            if '.pdf' in url.lower() and url not in seen_links:
                                seen_links.add(url)
                                pdf_links.append(url)

    except Exception as e:
        logger.error(f"Error parsing CSV file: {e}")
        raise ValueError(f"Failed to parse CSV file: {str(e)}")

    logger.info(f"Extracted {len(pdf_links)} unique PDF links from CSV")
    return pdf_links


def scrape_faqs_from_pdf_bytes(pdf_bytes: bytes, source_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parses questions and answers (FAQs) from raw PDF bytes.
    Uses robust boundary splitting based on sequential numbers and question mark index.
    Falls back to regex-based parser if sequential extraction is not applicable.
    """
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        logger.error(f"Failed to parse PDF pages: {e}")
        raise RuntimeError(f"PDF parsing error: {str(e)}")

    faqs: List[Dict[str, Any]] = []
    seen_questions: Set[str] = set()

    def clean_text(t: str) -> str:
        t = ' '.join(t.split())
        t = t.replace('&nbsp;', ' ').replace('&amp;', '&')
        return t.strip()

    def clean_question_text(q: str) -> str:
        q_clean = q.strip()
        # Remove footnote junk at start if present
        match = re.search(r'\b(\d+)\.\s+([A-Z])', q_clean)
        if match:
            start_idx = match.start()
            if start_idx > 0:
                q_clean = q_clean[start_idx:]
        # Strip leading Q/number markers
        q_clean = re.sub(r'^\s*(?:Q\d+\.?|Q\.?\s*\d+\.?|\d+\.?|[Qq]uestion\s*\d+\.?)\s*', '', q_clean)
        return q_clean.strip()

    def clean_answer_text(a: str) -> str:
        a_clean = a.strip()
        # Strip leading footnote numbers
        a_clean = re.sub(r'^\s*\d+\s+([A-Z])', r'\1', a_clean)
        return a_clean.strip()

    def extract_question_number(line_str: str) -> Optional[int]:
        match = re.match(r'^\s*(?:[Qq](?:uestion)?\.?\s*)?(\d+)(?:[\.\s:-]+|$)', line_str)
        if match:
            return int(match.group(1))
        return None

    # Pre-split text into lines for structured parsing
    raw_lines = [line.strip() for line in text.split('\n')]
    lines = []

    # Pre-process lines: Clean page headers/footers
    header_footer_patterns = [
        r'SEBI\s+FAQs\s+on\s+.*?\s+Page\s+\d+\s+of\s+\d+',
        r'Page\s+\d+\s+of\s+\d+',
        r'^\d+\s+of\s+\d+$',
        r'Frequently\s+Asked\s+Questions\s+on\s+.*',
    ]

    for line in raw_lines:
        is_hf = False
        for pat in header_footer_patterns:
            if re.search(pat, line, re.IGNORECASE):
                is_hf = True
                break
        
        # Extract question portion if page header is prepended to a question
        header_match = re.search(r'^(.*?Page\s+\d+\s+of\s+\d+)\s*(?:[A-Za-z]+\s+\d+\s*,\s*\d+)?\s*', line, re.IGNORECASE)
        if header_match:
            cleaned = line[header_match.end():].strip()
            if cleaned:
                lines.append(cleaned)
            continue
            
        if not is_hf:
            lines.append(line)

    # Find question start indices using sequential number matching + lookahead
    question_start_indices = []
    expected_next_num = 1

    for idx, line in enumerate(lines):
        num = extract_question_number(line)
        if num == expected_next_num:
            # Lookahead to see if there is a question mark before next number or within next 10 lines
            has_qmark = False
            for look_idx in range(idx, min(len(lines), idx + 10)):
                if look_idx > idx:
                    next_num = extract_question_number(lines[look_idx])
                    if next_num is not None:
                        break
                if '?' in lines[look_idx]:
                    has_qmark = True
                    break
            
            if has_qmark:
                question_start_indices.append(idx)
                expected_next_num = num + 1

    # Extract Q&As using the identified boundary indexes
    if question_start_indices:
        for i in range(len(question_start_indices)):
            start_idx = question_start_indices[i]
            end_idx = question_start_indices[i+1] if i + 1 < len(question_start_indices) else len(lines)
            
            block_lines = lines[start_idx : end_idx]
            
            # Find the last line containing '?' in the first few lines of the block (up to 8 lines)
            qmark_line_idx = -1
            for k in range(min(len(block_lines), 8)):
                if '?' in block_lines[k]:
                    qmark_line_idx = k
            
            if qmark_line_idx != -1:
                # Split the line containing '?' at the last '?'
                target_line = block_lines[qmark_line_idx]
                split_idx = target_line.rfind('?')
                q_line_end = target_line[:split_idx + 1]
                a_line_start = target_line[split_idx + 1:].strip()
                
                # Assemble question and answer text
                q_text = " ".join(block_lines[:qmark_line_idx]) + " " + q_line_end
                a_text_parts = []
                if a_line_start:
                    a_text_parts.append(a_line_start)
                a_text_parts.extend(block_lines[qmark_line_idx + 1:])
                a_text = " ".join(a_text_parts)
            else:
                # Fallback if no question mark is found in the first 8 lines
                q_text = block_lines[0]
                a_text = " ".join(block_lines[1:])
            
            q_cleaned = clean_text(clean_question_text(q_text))
            a_cleaned = clean_text(clean_answer_text(a_text))
            
            # Filter page numbers and headers from answers
            filtered_ans = []
            for line in a_cleaned.split('\n'):
                line_str = line.strip()
                if re.search(r'Page \d+ of \d+', line_str, re.I) or re.search(r'^\d+ of \d+$', line_str):
                    continue
                if 'sebi' in line_str.lower() and 'faq' in line_str.lower():
                    continue
                filtered_ans.append(line_str)
            a_cleaned = " ".join(filtered_ans).strip()
            
            if len(q_cleaned) >= 10 and len(a_cleaned) >= 20:
                q_lower = q_cleaned.lower()
                if q_lower not in seen_questions:
                    seen_questions.add(q_lower)
                    faqs.append({
                        "question": q_cleaned,
                        "answer": a_cleaned,
                        "source_url": source_url
                    })

    # Fallback to Regex-based parsing if no structured Q&As extracted (e.g. unnumbered pages)
    if len(faqs) < 2:
        faqs.clear()
        seen_questions.clear()
        qa_pattern = r'[Qq]\.?\s*([^\n?]+\?)\s*[Aa]\.?\s*([^\n]+(?:\n(?!Q\.)[^\n]+)*)'
        matches = re.findall(qa_pattern, text)
        for q, a in matches:
            q_cleaned = clean_text(clean_question_text(q))
            a_cleaned = clean_text(clean_answer_text(a))
            
            # Filter page numbers and headers
            filtered_ans = []
            for line in a_cleaned.split('\n'):
                line_str = line.strip()
                if re.search(r'Page \d+ of \d+', line_str, re.I) or re.search(r'^\d+ of \d+$', line_str):
                    continue
                if 'sebi' in line_str.lower() and 'faq' in line_str.lower():
                    continue
                filtered_ans.append(line_str)
            a_cleaned = " ".join(filtered_ans).strip()
            
            if len(q_cleaned) >= 10 and len(a_cleaned) >= 20:
                q_lower = q_cleaned.lower()
                if q_lower not in seen_questions:
                    seen_questions.add(q_lower)
                    faqs.append({
                        "question": q_cleaned,
                        "answer": a_cleaned,
                        "source_url": source_url
                    })


    return faqs


def scrape_faqs_from_pdf(pdf_url: str) -> List[Dict[str, Any]]:
    """
    Downloads a PDF and extracts questions and answers (FAQs).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(pdf_url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download PDF from {pdf_url}: {e}")
        raise RuntimeError(f"Download failed: {str(e)}")

    return scrape_faqs_from_pdf_bytes(response.content, pdf_url)


def find_column_index(headers: List[str], possible_names: List[str]) -> Optional[int]:
    """Finds index of column matching one of possible names (exact first, then substring)."""
    # 1. Exact case-insensitive match
    for name in possible_names:
        for idx, h in enumerate(headers):
            if h and str(h).strip().lower() == name.lower():
                return idx
    # 2. Case-insensitive substring match
    for name in possible_names:
        for idx, h in enumerate(headers):
            if h and name.lower() in str(h).lower():
                return idx
    return None

import datetime
def parse_date(val: Any) -> Optional[datetime.datetime]:
    """Parses standard date strings and datetime objects from Excel/CSV."""
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time.min)
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    # Try common formats in SEBI files
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None

def parse_excel_or_csv(file_contents: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses spreadsheet row by row, matching headers and extracting values.
    Returns:
        List of dicts: {pdf_url, publication_date, topic, sub_topic, category}
    """
    rows = []
    headers = []
    data_rows = []

    if filename.lower().endswith('.csv'):
        try:
            text = file_contents.decode('utf-8')
        except UnicodeDecodeError:
            text = file_contents.decode('latin-1')
        reader = csv.reader(StringIO(text))
        csv_rows = list(reader)
        if not csv_rows:
            return []
        headers = [h.strip() for h in csv_rows[0]]
        data_rows = csv_rows[1:]
    else:
        wb = openpyxl.load_workbook(BytesIO(file_contents), data_only=True)
        sheet = wb.active
        excel_rows = list(sheet.iter_rows(values_only=True))
        if not excel_rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in excel_rows[0]]
        data_rows = excel_rows[1:]

    # Map column headers to indices
    pdf_idx = find_column_index(headers, ['pdf links', 'pdf link', 'pdf_links', 'pdf_link', 'url', 'link'])
    date_idx = find_column_index(headers, ['dates', 'date', 'published date', 'publication date'])
    topic_idx = find_column_index(headers, ['topic', 'topics'])
    sub_topic_idx = find_column_index(headers, ['sub topic', 'sub-topic', 'subtopics', 'subtopic'])
    category_idx = find_column_index(headers, ['category', 'categories'])

    # We must have at least the PDF link column to process
    if pdf_idx is None:
        logger.error(f"Spreadsheet columns {headers} missing PDF URL column.")
        return []

    for r in data_rows:
        if not r or len(r) <= pdf_idx:
            continue
        pdf_url = r[pdf_idx]
        if not pdf_url:
            continue
        pdf_url = str(pdf_url).strip()
        # Simple URL format validate
        if not pdf_url.startswith(('http://', 'https://')):
            continue

        raw_date = r[date_idx] if (date_idx is not None and date_idx < len(r)) else None
        pub_date = parse_date(raw_date)

        topic = str(r[topic_idx]).strip() if (topic_idx is not None and topic_idx < len(r) and r[topic_idx] is not None) else None
        sub_topic = str(r[sub_topic_idx]).strip() if (sub_topic_idx is not None and sub_topic_idx < len(r) and r[sub_topic_idx] is not None) else None
        category = str(r[category_idx]).strip() if (category_idx is not None and category_idx < len(r) and r[category_idx] is not None) else None

        rows.append({
            "pdf_url": pdf_url,
            "document_publish_date": pub_date,
            "topic": topic,
            "sub_topic": sub_topic,
            "category": category
        })

    logger.info(f"Parsed {len(rows)} rows with PDF links from {filename}")
    return rows
