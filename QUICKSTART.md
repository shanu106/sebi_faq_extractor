"""
SEBI FAQ System - Quick Start Guide
"""

# ============================================================================
# QUICK START (5 minutes)
# ============================================================================

## 1. Start the System

```bash
cd sebi-faq-system

# Copy environment variables
cp .env.example .env

# Start all services (PostgreSQL, Qdrant, FastAPI)
docker-compose up -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps
```

Expected output:
```
NAME              STATUS
sebi-postgres    healthy
sebi-qdrant      healthy
sebi-faq-app     running
```

## 2. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Swagger UI (Interactive API docs)
open http://localhost:8000/docs
```

## 3. Ingest Sample FAQs

```bash
cd sebi-faq-system

# Create and ingest sample FAQs
python ingest_faqs.py

# Expected output:
# Loaded 5 FAQs from sample_faqs.json
# ✓ Ingested: 5/5
# Ingestion took 2.34s
```

## 4. Search for FAQs

```bash
# Semantic search (find similar content)
curl -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are compliance requirements for listed companies?",
    "limit": 5,
    "min_similarity": 0.5
  }'

# Metadata filter search
curl -X POST http://localhost:8000/api/v1/search/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "department": "Investor Protection",
    "risk_level": "high"
  }'

# Combined search (semantic + metadata + full-text)
curl -X POST http://localhost:8000/api/v1/search/combined \
  -H "Content-Type: application/json" \
  -d '{
    "query": "audit requirements",
    "semantic_weight": 0.5,
    "fulltext_weight": 0.3,
    "limit": 10
  }'
```

## 5. View Statistics

```bash
# FAQ statistics
curl http://localhost:8000/api/v1/stats/faqs

# Search analytics (last 7 days)
curl http://localhost:8000/api/v1/stats/searches?days=7
```

# ============================================================================
# DETAILED WORKFLOW
# ============================================================================

## Phase 1: Setup (One-time)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (.env file)
   - Database URL
   - Qdrant URL
   - Embedding model
   - API settings

3. **Initialize database** (automatic on app startup)
   ```bash
   # Or manually:
   python -c "from database import init_db; init_db()"
   ```

## Phase 2: Data Ingestion (Recurring)

### Option A: Via JSON File

1. **Prepare FAQ JSON file** (e.g., sebi_faqs.json)
   ```json
   [
     {
       "question": "...",
       "answer": "...",
       "source_url": "...",
       "extracted_by": "...",
       "metadata": {
         "department": "...",
         "category": "...",
         "risk_level": "...",
         ...
       }
     }
   ]
   ```

2. **Ingest via API**
   ```bash
   python ingest_faqs.py sebi_faqs.json
   ```

3. **Or ingest via direct database**
   ```python
   from ingest_faqs import ingest_faqs_from_db
   ingest_faqs_from_db("sebi_faqs.json")
   ```

### Option B: Via API Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/faqs/bulk-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "faqs": [
      {
        "question": "...",
        "answer": "...",
        "metadata": {...}
      }
    ],
    "skip_duplicates": true
  }'
```

### Option C: One FAQ at a Time

```bash
curl -X POST http://localhost:8000/api/v1/faqs \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is SEBI?",
    "answer": "SEBI is the Securities and Exchange Board of India...",
    "source_url": "https://www.sebi.gov.in/",
    "metadata": {
      "department": "Investor Education",
      "category": "General Knowledge",
      "risk_level": "low"
    }
  }'
```

## Phase 3: Search & Retrieval

### Search Types

| Type | Use Case | Endpoint |
|------|----------|----------|
| **Semantic** | Find FAQs similar in meaning | `/search/semantic` |
| **Metadata** | Filter by department, risk level, etc. | `/search/metadata` |
| **Full-Text** | Keyword/phrase search | `/search/fulltext` |
| **Combined** | All three with weighting | `/search/combined` |

### Example Queries

```bash
# Find FAQs about audit requirements
curl -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "audit compliance requirements", "limit": 5}'

# Find all high-risk mandatory FAQs
curl -X POST http://localhost:8000/api/v1/search/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "risk_level": "high",
    "compliance_status": "mandatory"
  }'

# Find FAQs matching query AND filters
curl -X POST http://localhost:8000/api/v1/search/combined \
  -H "Content-Type: application/json" \
  -d '{
    "query": "listing requirements",
    "metadata_filters": {
      "department": "Listing & Disclosures"
    },
    "limit": 10
  }'
```

## Phase 4: Customization

### Add Custom Metadata Fields

1. **Update the model**
   ```python
   # models.py - FAQMetadata class
   internal_priority = Column(String(50))
   regulatory_reference = Column(String(255))
   ```

2. **Create migration**
   ```bash
   alembic revision --autogenerate -m "Add custom fields"
   ```

3. **Apply migration**
   ```bash
   alembic upgrade head
   ```

4. **Use in API**
   ```json
   {
     "metadata": {
       "department": "Compliance",
       "internal_priority": "P1",
       "regulatory_reference": "SEBI/2024/123"
     }
   }
   ```

### Modify Search Weights

Update `CombinedSearchRequest` in `schemas.py`:
```python
class CombinedSearchRequest(BaseModel):
    semantic_weight: float = Field(0.5)  # Change this
    fulltext_weight: float = Field(0.3)  # Change this
```

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

## Issue: "Connection refused" to PostgreSQL

```bash
# Check if container is running
docker-compose ps

# If not, start it
docker-compose up -d postgres

# Check logs
docker-compose logs postgres
```

## Issue: "No results" from semantic search

1. Verify FAQs are created:
   ```bash
   curl http://localhost:8000/api/v1/faqs?limit=1
   ```

2. Check embeddings generated:
   ```bash
   # In database, check FAQ.embedding_vector is not null
   # SELECT id, embedding_vector FROM faqs LIMIT 5;
   ```

3. Verify Qdrant has data:
   ```bash
   curl http://localhost:6333/collections/faq_embeddings
   ```

## Issue: Slow searches

1. Check database performance:
   ```bash
   # Connect to PostgreSQL
   psql -U sebi_user -d sebi_faq_db
   
   # Check indexes
   \d faq_metadata
   
   # Query performance
   EXPLAIN ANALYZE SELECT * FROM faqs WHERE is_active = true;
   ```

2. Monitor Qdrant:
   - Dashboard: http://localhost:6333/dashboard
   - Check collection stats

3. Check API response times:
   ```bash
   curl http://localhost:8000/api/v1/stats/searches?days=1
   ```

## Issue: Out of memory with embeddings

- Use smaller model: `sentence-transformers/all-MiniLM-L6-v2` (384 dims, 22M params)
- Alternative: `all-mpnet-base-v2` (768 dims, larger)
- Reduce batch size in `embeddings.py`

# ============================================================================
# INTEGRATION WITH ORCHESTRATOR
# ============================================================================

Use SEBI FAQ system as a data source for your compliance orchestrator:

```python
from orchestrator.registry.base import RegistryClient
from sqlalchemy.orm import Session
from search_service import SearchService
from schemas import CombinedSearchRequest

class SEBIFAQRegistry(RegistryClient):
    def __init__(self, db_session: Session):
        self.search_service = SearchService(db_session)
    
    def retrieve_obligations(self, query: str) -> List[str]:
        """Get SEBI FAQs as compliance obligations"""
        request = CombinedSearchRequest(
            query=query,
            limit=10,
            semantic_weight=0.6,
            fulltext_weight=0.4
        )
        response = self.search_service.combined_search(request)
        return [r.faq.answer for r in response.results]
    
    def get_by_id(self, obligation_id: str) -> Optional[str]:
        """Get specific FAQ"""
        from faq_service import FAQService
        service = FAQService(self.db)
        faq = service.get_faq(obligation_id)
        return faq.answer if faq else None
```

# ============================================================================
# MONITORING & ANALYTICS
# ============================================================================

### View Search Patterns

```bash
# Most searched queries
curl http://localhost:8000/api/v1/stats/searches?days=30

# Response:
# {
#   "total_searches": 1250,
#   "most_common_queries": [
#     ["listing requirements", 89],
#     ["audit compliance", 76],
#     ...
#   ],
#   "average_response_time_ms": 145.5,
#   "search_type_distribution": {
#     "combined": 600,
#     "semantic": 400,
#     "fulltext": 200,
#     "filter": 50
#   }
# }
```

### FAQ Coverage

```bash
# FAQ statistics
curl http://localhost:8000/api/v1/stats/faqs

# Response:
# {
#   "total_faqs": 250,
#   "verified_faqs": 180,
#   "faqs_by_department": {
#     "Listing & Disclosures": 65,
#     "Investor Protection": 85,
#     ...
#   },
#   "faqs_by_risk_level": {
#     "high": 100,
#     "medium": 120,
#     "low": 30
#   }
# }
```

# ============================================================================
# NEXT STEPS
# ============================================================================

1. **Extract SEBI FAQs** from their website
   - Visit: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doFaq=yes
   - Extract Q&A pairs with metadata
   - Save as JSON file

2. **Ingest FAQs** into the system
   ```bash
   python ingest_faqs.py your_sebi_faqs.json
   ```

3. **Test searches** to verify quality
   ```bash
   # Try various search queries
   # Verify results are relevant
   # Adjust similarity threshold if needed
   ```

4. **Customize schema** based on your needs
   - Add department-specific fields
   - Adjust metadata structure
   - Create Alembic migrations

5. **Integrate with orchestrator**
   - Create RegistryClient wrapper
   - Use in compliance workflows
   - Monitor performance

# ============================================================================
# USEFUL COMMANDS
# ============================================================================

```bash
# Start/Stop services
docker-compose up -d
docker-compose down
docker-compose restart app

# View logs
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f qdrant

# Database access
docker-compose exec postgres psql -U sebi_user -d sebi_faq_db

# API documentation
open http://localhost:8000/docs

# Run tests
pytest tests/ -v

# Create database backup
docker-compose exec postgres pg_dump -U sebi_user sebi_faq_db > backup.sql

# Restore from backup
docker-compose exec postgres psql -U sebi_user sebi_faq_db < backup.sql
```

# ============================================================================
# FILE STRUCTURE
# ============================================================================

```
sebi-faq-system/
├── main.py                  # FastAPI app
├── config.py               # Configuration
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic schemas
├── database.py             # DB connection
├── vector_db.py            # Qdrant integration
├── embeddings.py           # Embedding service
├── faq_service.py          # Business logic (FAQs)
├── search_service.py       # Business logic (Search)
├── ingest_faqs.py          # Data ingestion script
├── docker-compose.yml      # Docker setup
├── Dockerfile              # FastAPI image
├── requirements.txt        # Dependencies
├── alembic.ini            # Migration config
├── .env.example           # Environment template
└── README.md              # Full documentation
```

---

**Ready to use! Start with `docker-compose up -d` and visit http://localhost:8000/docs**
