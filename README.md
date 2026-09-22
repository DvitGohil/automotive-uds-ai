# UDS Diagnostics and Automated Test Generation Assistant

An AI-powered engineering tool for **ISO 14229 UDS (Unified Diagnostic Services)** that automates diagnostic test case generation, request construction, ECU response validation, and automation template creation — all grounded in approved source documents with full traceability.

---

## Key Features

- **Document Ingestion & RAG** — Upload UDS specs (PDF/TXT), extract structured content, chunk, embed, and retrieve relevant context for grounded answers.
- **Grounded LLM Assistant** — Ask engineering questions answered *only* from approved documents. Never fabricates UDS data.
- **UDS Knowledge Model** — Structured representation of services, subfunctions, DIDs, RIDs, and NRCs with full source traceability.
- **Deterministic Request Construction** — Build well-formed UDS request byte sequences from a generic ISO 14229 service registry.
- **Deterministic Request Validation** — Validate request structure, field requirements, and byte-representation consistency — no LLM in the decision path.
- **Positive & Negative Test Generation** — Generate test cases deterministically from validated requests. Expected responses are never guessed.
- **ECU Response Validation** — Compare actual ECU hex responses against expected outcomes with structured PASS/FAIL/UNKNOWN results.
- **Automation Templates** — Generate automation-ready test templates from validated test cases.
- **Audit & Traceability** — Every action is logged. Full chain from source document → test case → validation result → template.
- **Authentication & Authorization** — JWT-based login/register, project-membership authorization with IDOR protection.
- **React Frontend** — 7-tab UI for knowledge lookup, request construction, test generation, response validation, templates, and audit/traceability.

---

## Architecture

```
requirements.txt
backend/
├── app/
│   ├── main.py                     # FastAPI application entry point
│   ├── api/routes/
│   │   ├── health.py               # Health check endpoint
│   │   ├── auth.py                 # Register, login, logout, /me
│   │   ├── documents.py            # Document ingestion & segment listing
│   │   └── uds.py                  # UDS workflow (construct, validate, generate, templates, audit)
│   ├── core/
│   │   ├── config.py               # Central configuration (pydantic-settings)
│   │   ├── auth.py                 # Password hashing (PBKDF2) & JWT issuing/verification
│   │   └── security.py             # API key gate, JWT auth, project-membership authorization
│   ├── db/
│   │   ├── database.py             # SQLAlchemy engine, session, Base
│   │   └── models.py              # 11 tables (User, Project, Document, TestCase, AuditRecord, etc.)
│   ├── ingestion/
│   │   ├── extractors.py           # PDF (pdfplumber) + TXT extraction with section detection
│   │   └── service.py              # Document ingestion orchestration
│   ├── rag/
│   │   ├── embeddings.py           # Embedding providers (hash/sentence_transformers)
│   │   ├── vector_store.py         # Local FAISS vector store (per-project)
│   │   ├── chunking.py             # Section/table-aware document chunking
│   │   ├── chunking_service.py     # Chunking orchestration
│   │   ├── indexing_service.py     # Embed & index chunks into vector store
│   │   ├── retrieval.py            # Project-scoped RAG retrieval
│   │   ├── llm.py                  # LLM providers (mock/anthropic)
│   │   └── assistant.py            # Grounded Q&A with citations & confidence
│   ├── uds/
│   │   ├── knowledge_model.py      # UDS dataclasses (Service, DID, RID, NRC, Request, Response)
│   │   ├── repository.py           # Persist/load UDS entities via DiagnosticKnowledgeUnit table
│   │   ├── request_builder.py      # Deterministic UDS request construction
│   │   └── request_validator.py    # Deterministic UDS request validation
│   ├── test_generation/
│   │   ├── models.py               # PositiveTestCase, NegativeTestCase, TestGenerationResult
│   │   ├── positive.py             # Positive test case generation
│   │   ├── negative.py             # Negative test case generation (6 scenario categories)
│   │   └── persistence.py          # Save/load test cases to/from DB
│   ├── response_validation/
│   │   └── ecu_validator.py        # Deterministic ECU response validation (PASS/FAIL/UNKNOWN)
│   ├── automation/
│   │   └── template_generator.py   # Automation-ready test template generation
│   └── audit/
│       └── service.py              # Audit logging service
├── migrations/                     # Alembic migration scripts
├── tests/                          # 176 pytest tests
└── .env.example

frontend/
├── src/
│   ├── App.jsx                     # 7-tab layout
│   ├── api.js                      # Backend API client
│   ├── components/
│   │   ├── UdsKnowledgePanel.jsx
│   │   ├── RequestConstructionPanel.jsx
│   │   ├── PositiveTestsPanel.jsx
│   │   ├── NegativeTestsPanel.jsx
│   │   ├── ResponseValidationPanel.jsx
│   │   ├── AutomationTemplatesPanel.jsx
│   │   ├── AuditTraceabilityPanel.jsx
│   │   └── common.jsx             # Shared UI components (ErrorBanner, StatusBadge, etc.)
│   ├── index.css
│   └── main.jsx
├── package.json
└── vite.config.js

deployment/
├── docker-compose.yml              # Orchestrates backend + frontend services
├── backend.Dockerfile              # Multi-stage Python build (FastAPI + Uvicorn)
├── frontend.Dockerfile             # Multi-stage Node → Nginx build (React SPA)
├── nginx.conf                      # Nginx: SPA routing + API reverse proxy
├── .env.docker                     # Environment variables template for Docker
├── .dockerignore                   # Build context filter
└── README.md                       # Docker deployment guide
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+

### Backend

```bash
pip install -r requirements.txt
cd backend
cp .env.example .env          # Review and edit settings as needed
alembic upgrade head          # Create database tables
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

### Docker Deployment

```bash
# From the project root — single command to build & run everything
docker compose -f deployment/docker-compose.yml up --build
```

| Service  | URL                                      |
|----------|------------------------------------------|
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Backend  | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) |

To customise environment variables (LLM keys, auth secrets, ports), edit `deployment/.env.docker` before starting. See [`deployment/README.md`](deployment/README.md) for the full guide.

### Run Tests

```bash
cd backend
pytest                        # 176 tests, all passing
```

---

## Configuration

All configuration is via environment variables (or `.env` file). See `backend/.env.example` for the full list:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./uds_assistant.db` | Database connection string |
| `API_KEY` | *(empty = disabled)* | Set to require `X-API-Key` header on all API routes |
| `JWT_SECRET` | *(empty = disabled)* | Set to enable JWT authentication and project authorization |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | Token expiry |
| `EMBEDDING_PROVIDER` | `hash` | `hash` (offline/deterministic) or `sentence_transformers` (real) |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Model for sentence_transformers provider |
| `LLM_PROVIDER` | `mock` | `mock` (offline/deterministic) or `anthropic` (real) |
| `LLM_API_KEY` | *(empty)* | Required when `LLM_PROVIDER=anthropic` |
| `CHUNK_SIZE` | `800` | Document chunk size in characters |
| `RETRIEVAL_TOP_K` | `5` | Number of chunks retrieved per query |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |

---

## API Endpoints

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create account, returns JWT |
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `POST` | `/api/v1/auth/logout` | Logout (client discards token) |
| `GET` | `/api/v1/auth/me` | Current user info |

### Documents
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/ingest` | Upload and ingest a PDF/TXT document |
| `GET` | `/api/v1/documents/{id}/segments` | List extracted segments for a document |

### UDS Workflow
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/uds/knowledge/{doc_ver_id}/{type}/{id}` | Retrieve structured UDS knowledge |
| `POST` | `/api/v1/uds/requests/construct` | Build a UDS request from service/DID/RID |
| `POST` | `/api/v1/uds/requests/validate` | Validate a UDS request structure |
| `POST` | `/api/v1/uds/tests/positive` | Generate a positive test case |
| `POST` | `/api/v1/uds/tests/negative` | Generate a negative test case |
| `GET` | `/api/v1/uds/tests/{project_id}` | List test cases for a project |
| `POST` | `/api/v1/uds/response-validation` | Validate an actual ECU response |
| `POST` | `/api/v1/uds/automation-templates/positive` | Generate positive automation template |
| `POST` | `/api/v1/uds/automation-templates/negative` | Generate negative automation template |
| `POST` | `/api/v1/uds/automation-templates/from-test-case` | Template from a saved test case |
| `GET` | `/api/v1/uds/audit/{project_id}` | Audit log for a project |
| `GET` | `/api/v1/uds/traceability/test-case/{id}` | Full traceability chain for a test case |

---

## Engineering Pipeline

```
Document Upload
    → PDF/TXT Extraction (page/section/table-aware)
    → Chunking (configurable size/overlap)
    → Embedding (hash or sentence_transformers)
    → Vector Store (per-project FAISS)
    → RAG Retrieval (relevance-filtered)
    → Grounded LLM Assistant (citations, confidence)
    → UDS Knowledge Model (structured, traceable)
    → Request Construction (deterministic, ISO 14229)
    → Request Validation (deterministic, no LLM)
    → Test Generation (positive + negative, 6 categories)
    → ECU Response Validation (PASS/FAIL/UNKNOWN)
    → Automation Templates
    → Audit Logging & Traceability
    → JWT Authentication & Project Authorization
```

---

## Design Principles

1. **Never fabricate UDS data** — Expected responses, NRCs, DID meanings, and OEM-specific values are only used when explicitly supplied from approved sources. Unknown values are marked as such, never guessed.
2. **Deterministic validation** — No LLM is involved in pass/fail decisions. All request construction and validation is pure application logic.
3. **Full traceability** — Every generated artifact traces back to its source document (document → version → page → section → chunk). Every action is audit-logged.
4. **Decision-support only** — The system assists engineers; it never suggests or implies automatic execution against a real ECU.
5. **Offline-safe defaults** — `EMBEDDING_PROVIDER=hash` and `LLM_PROVIDER=mock` work without network access, API keys, or model downloads.

---

## Test Coverage

**176 tests** across 19 test files covering:

- Health check & database models
- Document ingestion (PDF + TXT)
- Chunking (section/table-aware, overlap, edge cases)
- Embeddings & vector store (FAISS indexing, dedup, search)
- RAG retrieval (relevance filtering, project scoping)
- Grounded assistant (citations, confidence, audit)
- UDS knowledge model (serialization round-trips, repository)
- Request builder (all service types, error cases)
- Request validator (field validation, byte consistency)
- Positive & negative test generation
- ECU response validation (positive/negative/malformed/incomplete)
- Automation templates
- Test case persistence (save/load, all fields preserved)
- API integration (all endpoints, error handling)
- Audit & traceability (full chain)
- Security & access control (JWT, project membership, IDOR protection)

---

## Known Limitations

- **No token revocation** — JWTs are stateless and self-expiring. `/logout` discards client-side.
- **`KNOWN_SERVICES` coverage** — 9 standardized ISO 14229 services. OEM extensions come from document ingestion.
- **No automated frontend tests** — React UI verified via production build + lint only.
- **UDS Knowledge panel** — Requires manually entering `document_version_id` (no document browsing endpoint yet).

---
