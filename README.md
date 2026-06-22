# SEBI FAQ Intelligent Retrieval System

A production-grade **intelligent FAQ retrieval system** for SEBI (Securities and Exchange Board of India) compliance documentation using:

- **Semantic Search** (Qdrant vector database with embeddings)
- **Metadata Filtering** (Risk level, Compliance status, Department, Authority)
- **Full-Text Search** (Keyword matching on questions & answers)
- **Combined Search** (All three methods with weighted scoring)
- **Version History & Change Tracking** (Audit trail)
- **Implementation Checklists** (Actionable compliance items)
- **Flexible, User-Controlled Schema** (Alembic migrations for customization)

---

## System Architecture

```
┌─────────────────┐
│   FastAPI App   │
│   (Endpoints)   │
└────────┬────────┘
         │
    ┌────┴─────────────┬──────────────────┐
    │                  │                  │
┌───▼────────┐  ┌─────▼──────┐  ┌───────▼──────┐
│ PostgreSQL │  │   Qdrant   │  │ Embedding    │
│ (Metadata) │  │ (Vectors)  │  │ Service      │
└────────────┘  └────────────┘  └──────────────┘
```

### Components

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **PostgreSQL** | Metadata, versioning, relationships | SQLAlchemy ORM |
| **Qdrant** | Vector storage & semantic search | Qdrant Client |
| **Embeddings** | Generate semantic vectors | Sentence Transformers (all-MiniLM-L6-v2) |
| **FastAPI** | REST API & business logic | FastAPI + Pydantic |
| **Alembic** | Database schema migrations | SQLAlchemy + Alembic |

---

## Quick Start

### 1. **Clone & Setup**

```bash
cd sebi-faq-system

# Copy environment
cp .env.example .env

# Install dependencies
pip install -r requirements.txt
```

### 2. **Using Docker Compose** (Recommended)

```bash
# Start all services (PostgreSQL, Qdrant, FastAPI)
docker-compose up -d

# Verify services
docker-compose ps

# View logs
docker-compose logs -f app
```

Services will be available at:
- **FastAPI**: http://localhost:8000
- **Docs (Swagger UI)**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **PostgreSQL**: localhost:5432

### 3. **Manual Setup** (Development)

```bash
# Start PostgreSQL
psql -U sebi_user -d sebi_faq_db

# Start Qdrant (Docker)
docker run -p 6333:6333 qdrant/qdrant:latest

# Run FastAPI
uvicorn main:app --reload
```

---

## API Documentation

### FAQ Management

#### Create FAQ
```bash
POST /api/v1/faqs

{
  "question": "What are the compliance requirements for listed companies?",
  "answer": "Listed companies must comply with SEBI Listing Regulations...",
  "source_url": "https://www.sebi.gov.in/...",
  "extracted_by": "admin@sebi.gov.in",
  "metadata": {
    "department": "Investor Protection",
    "category": "Listing Requirements",
    "risk_level": "high",
    "compliance_status": "mandatory",
    "authority": "SEBI",
    "compliance_framework": "DORA"
  }
}
```

#### Bulk Ingest FAQs
```bash
POST /api/v1/faqs/bulk-ingest

{
  "faqs": [
    {
      "question": "...",
      "answer": "...",
      "metadata": {...}
    },
    ...
  ],
  "skip_duplicates": true
}
```

#### Get FAQ with Details
```bash
GET /api/v1/faqs/{faq_id}
```

Returns full FAQ with versions, checklists, and related FAQs.

#### Update FAQ
```bash
PUT /api/v1/faqs/{faq_id}

{
  "question": "Updated question",
  "answer": "Updated answer",
  "change_reason": "Clarification for compliance"
}
```

#### List All FAQs
```bash
GET /api/v1/faqs?skip=0&limit=100&is_active=true
```

#### Add Implementation Checklist
```bash
POST /api/v1/faqs/{faq_id}/checklists

{
  "title": "SOC2 Compliance Checklist",
  "description": "Steps to achieve SOC2 compliance",
  "items": [
    {"id": "1", "title": "Conduct risk assessment", "completed": false},
    {"id": "2", "title": "Document policies", "completed": false}
  ],
  "priority": "high",
  "estimated_effort": "2 weeks",
  "applicable_departments": ["IT", "Compliance"]
}
```

### Search Endpoints

#### Semantic Search (Vector Similarity)
```bash
POST /api/v1/search/semantic

{
  "query": "What are audit requirements?",
  "limit": 10,
  "min_similarity": 0.5
}
```

Returns FAQs ranked by semantic relevance.

#### Metadata Filter Search
```bash
POST /api/v1/search/metadata

{
  "department": "Investor Protection",
  "risk_level": "high",
  "compliance_status": "mandatory",
  "is_verified": true
}
```

#### Full-Text Search
```bash
POST /api/v1/search/fulltext

{
  "query": "audit compliance requirements",
  "limit": 10
}
```

#### Combined Search (Recommended)
```bash
POST /api/v1/search/combined

{
  "query": "What are the main compliance requirements?",
  "semantic_weight": 0.5,
  "fulltext_weight": 0.3,
  "min_similarity": 0.5,
  "metadata_filters": {
    "department": "Compliance",
    "risk_level": "high"
  },
  "limit": 10,
  "offset": 0
}
```

### Analytics

#### FAQ Statistics
```bash
GET /api/v1/stats/faqs
```

Returns count by department, risk level, compliance status.

#### Search Analytics
```bash
GET /api/v1/stats/searches?days=7
```

Returns most common queries, average response time, search type distribution.

---

## Database Schema (Customizable)

### Core Tables

**faqs**
```
id (UUID)
question (String, indexed)
answer (Text)
source_url (String, optional)
extraction_date (DateTime)
extracted_by (String, optional)
full_text_searchable (Text, denormalized)
embedding_vector (String, reference to Qdrant)
is_active (Boolean)
is_verified (Boolean)
created_at, updated_at (DateTime, indexed)
```

**faq_metadata** (Flexible, User-Controlled)
```
id (UUID)
faq_id (Foreign Key)
department (String, indexed)
category (String, indexed)
subcategory (String)
risk_level (String, indexed)
compliance_status (String)
authority (String)
compliance_framework (String)
custom_attributes (JSON) ← Add your own fields here
created_at, updated_at (DateTime)
```

**faq_versions** (Version History)
```
id (UUID)
faq_id (Foreign Key)
version_number (Integer)
question (String)
answer (Text)
change_type (String) ← "created", "updated", "clarified"
change_reason (Text, optional)
changed_by (String)
created_at (DateTime, indexed)
```

**implementation_checklists**
```
id (UUID)
faq_id (Foreign Key)
title (String)
description (Text)
items (JSON) ← Checklist items with completion status
priority (String)
estimated_effort (String)
applicable_departments (JSON array)
created_at, updated_at (DateTime)
```

**search_logs** (Analytics)
```
id (UUID)
query_text (String)
search_type (String) ← "semantic", "fulltext", "filter", "combined"
results_count (Integer)
top_result_id (String, optional)
applied_filters (JSON)
response_time_ms (Float)
user_id (String, optional)
created_at (DateTime, indexed)
```

---

## Customizing the Schema

The system uses **Alembic** for schema migrations, allowing you to modify the schema without data loss.

### Add Custom Metadata Fields

1. **Modify the FAQMetadata model** in `models.py`:
```python
class FAQMetadata(Base):
    # ... existing fields ...
    internal_priority = Column(String(50), nullable=True)
    regulatory_reference = Column(String(255), nullable=True)
    custom_attributes = Column(JSON, nullable=True)
```

2. **Create migration**:
```bash
alembic revision --autogenerate -m "Add internal_priority to faq_metadata"
```

3. **Apply migration**:
```bash
alembic upgrade head
```

4. **Use in API**:
```python
metadata = MetadataCreate(
    department="Compliance",
    internal_priority="P1",
    regulatory_reference="SEBI Circular 123/2024",
    custom_attributes={"custom_field": "value"}
)
```

---

## Example: Ingesting SEBI FAQs

### Step 1: Prepare FAQ Data

Create a JSON file `sebi_faqs.json`:
```json
[
  {
    "question": "What is the process for listing on NSE?",
    "answer": "The listing process involves... (detailed answer)",
    "source_url": "https://www.sebi.gov.in/faq/listing-process",
    "extracted_by": "compliance_team",
    "metadata": {
      "department": "Listing & Disclosures",
      "category": "Stock Exchange Listing",
      "risk_level": "high",
      "compliance_status": "mandatory",
      "authority": "SEBI",
      "compliance_framework": "DORA"
    }
  },
  ...
]
```

### Step 2: Ingest via API

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# Read FAQs
with open("sebi_faqs.json") as f:
    faqs = json.load(f)

# Bulk ingest
response = requests.post(
    f"{BASE_URL}/faqs/bulk-ingest",
    json={"faqs": faqs, "skip_duplicates": True}
)

result = response.json()
print(f"Ingested: {result['successful']}/{result['total_ingested']}")
print(f"Failed: {result['failed']}")
```

### Step 3: Verify Ingestion

```bash
# Check FAQ count
curl http://localhost:8000/api/v1/stats/faqs

# Search for a FAQ
curl -X POST http://localhost:8000/api/v1/search/combined \
  -H "Content-Type: application/json" \
  -d '{
    "query": "listing requirements",
    "limit": 5
  }'
```

---

## Integration with Your Orchestrator

The SEBI FAQ system can integrate with your `agents-orc-system` as a data source:

```python
from orchestrator.registry.base import RegistryClient
from sebi_faq_system.search_service import SearchService

class SEBIFAQRegistry(RegistryClient):
    """SEBI FAQ system as compliance registry"""
    
    def __init__(self, db_session):
        self.search_service = SearchService(db_session)
    
    def retrieve_obligations(self, query: str) -> List[str]:
        """Retrieve relevant SEBI FAQs as obligations"""
        response = self.search_service.combined_search(
            CombinedSearchRequest(query=query, limit=10)
        )
        return [r.faq.answer for r in response.results]
```

---

## Performance Tuning

### Vector Search Optimization
- **Embedding Model**: Using `all-MiniLM-L6-v2` (fast, 384-dim, good accuracy)
- **Similarity Threshold**: Default 0.5 (tune based on results)
- **Qdrant HNSW Config**: m=16, ef_construct=100 (configured in `vector_db.py`)

### Database Optimization
- **Indexes**: On `created_at`, `is_active`, `department`, `category`, `risk_level`
- **Connection Pooling**: pool_size=10, max_overflow=20
- **Query**: Use `.limit()` for pagination

### API Response Time
- **Semantic Search**: ~50-100ms (vector DB query)
- **Metadata Filter**: ~10-20ms (indexed SQL query)
- **Full-Text**: ~20-50ms (ILIKE query)
- **Combined**: ~80-200ms (all three + merge)

---

## Troubleshooting

### "Connection refused" to PostgreSQL/Qdrant

```bash
# Check services running
docker-compose ps

# Restart services
docker-compose restart

# View logs
docker-compose logs postgres
docker-compose logs qdrant
```

### "No results" from semantic search

1. Check FAQ is created: `GET /api/v1/faqs`
2. Verify embedding: Check if `embedding_vector` is populated
3. Check Qdrant: `curl http://localhost:6333/collections`
4. Lower similarity threshold: Use `min_similarity: 0.3`

### Slow searches

1. Check database indexes: `\d faq_metadata` in psql
2. Monitor Qdrant: http://localhost:6333/dashboard
3. Check response_time_ms in `/api/v1/stats/searches`

---

## API Reference

See **Swagger UI** at http://localhost:8000/docs for interactive API documentation.

All endpoints return JSON with proper HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad request
- `404`: Not found
- `500`: Server error

---

## Testing

```bash
# Run tests
pytest tests/ -v

# Test with coverage
pytest tests/ --cov=. --cov-report=html
```

---

## Roadmap

- [ ] GraphQL API support
- [ ] Full-text search optimization (PostgreSQL FTS)
- [ ] SEBI regulation change notifications
- [ ] Multi-language support
- [ ] Dashboard UI for FAQ management
- [ ] Advanced analytics & reporting

---

## Support & Questions

For issues or questions:
1. Check logs: `docker-compose logs app`
2. Review API docs: http://localhost:8000/docs
3. Check database: Connect to PostgreSQL and inspect tables

---

## License

MIT License - This system is designed for SEBI compliance use cases.
