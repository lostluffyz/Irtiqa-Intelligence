# Irtiqa Intelligence

[![CI](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-633%20passing-success)](https://github.com/Luffyz/irtiqa-intelligence)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)

**Production-grade lead intelligence platform for B2B sales teams.**

Irtiqa Intelligence automates lead discovery, enrichment, and prioritization through intelligent web scraping, technographic analysis, intent signal detection, and personalized outreach generation. Built with FastAPI, SQLAlchemy, and a modular agent-based architecture.

---

## Features

### 🔐 Authentication & Multi-Tenancy
- **RS256 JWT Authentication** with JWKS endpoint for secure API access
- **Email Verification** and password reset workflows
- **Organization Management** with role-based access control (Owner, Admin, Member, Viewer)
- **Tenant Isolation** across all data and API endpoints
- **Rate Limiting** with database-backed tracking

### 🔍 Lead Discovery Engine
- **ICP Search Management**: Define and save ideal customer profile criteria
- **Multi-Source Discovery**: Automated searches across SEC EDGAR, Google News RSS, and OpenCorporates
- **Smart Deduplication**: Domain-based duplicate detection with fuzzy matching
- **Discovery Scoring**: Lightweight match quality scores (0.0-1.0) for prioritization
- **Evidence Provenance**: Full audit trail of discovery sources

### 🤖 Intelligence Pipeline (6 Production Agents)
1. **Deep Scraper Agent**: Web content extraction and parsing
2. **Technographic Agent**: Technology detection (40+ signatures across 8 categories)
3. **Intent Signal Agent**: Buying signal detection (8 signal families with deterministic rules)
4. **Intelligence Scoring Agent**: Multi-factor lead scoring (fit, intent, technographic, engagement)
5. **Personalization Agent**: Multi-variant outreach message generation
6. **Discovery Agent**: ICP-based company discovery from external sources

### 📊 Lead Retrieval API
- **Aggregated Intelligence**: Single endpoint returns companies with technologies, intent signals, scores, and outreach messages
- **Smart Filtering**: Filter by minimum score, pagination support
- **Tenant-Scoped**: Automatic organization isolation

### ⚙️ Background Job System
- **Async Execution**: Agent and workflow scheduling with status tracking
- **Retry Policies**: Exponential backoff with configurable limits
- **Job Management**: Schedule, cancel, retry, and monitor background tasks

### 📈 Evidence Records
- **Provenance Tracking**: Full audit trail for all intelligence data
- **Source Linking**: Evidence tied to agent runs, URLs, and API responses
- **Confidence Scoring**: Evidence quality metrics

### 🔄 Workflow Orchestration
- **Score Refresh**: Deterministic intelligence score recomputation
- **Intelligence Pipeline**: End-to-end enrichment (scrape → analyze → score → personalize)
- **Discovery Pipeline**: Company discovery orchestration (search → discover → deduplicate → create)

---

## Architecture

Irtiqa Intelligence follows a **layered, modular architecture** designed for maintainability and testability:

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                  │
│  REST Endpoints · JWT Auth · Request Validation · CORS      │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                        Service Layer                         │
│  Business Logic · Transaction Boundaries · Validation        │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼─────────┐  ┌──────▼──────────┐
│  Agent System  │  │ Workflow System  │  │  Job Scheduler  │
│                │  │                  │  │                 │
│  6 Agents      │  │  3 Workflows     │  │  Background     │
│  Agent Registry│  │  Workflow Runner │  │  Execution      │
└───────┬────────┘  └────────┬─────────┘  └──────┬──────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                     Repository Layer                         │
│  Data Access · Query Building · No Business Logic            │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Database Layer (SQLAlchemy)                │
│  ORM Models · Alembic Migrations · Connection Pooling        │
│  SQLite (Development) · PostgreSQL (Production)              │
└─────────────────────────────────────────────────────────────┘
```

### Core Technologies

- **FastAPI**: High-performance async web framework with automatic OpenAPI docs
- **SQLAlchemy 2.0**: Modern ORM with full PostgreSQL compatibility
- **Alembic**: Database migration management with schema drift detection
- **Pydantic v2**: Request/response validation and serialization
- **SQLite**: Development database with WAL mode for concurrency
- **PostgreSQL**: Production database (verified compatible, 27 dedicated tests)

### Design Patterns

- **Repository Pattern**: Encapsulates data access logic
- **Service Layer**: Owns transaction boundaries and business rules
- **Agent Pattern**: Modular, reusable intelligence gathering components
- **Workflow Pattern**: Multi-step orchestration with error handling
- **Dependency Injection**: FastAPI dependencies for testability

---

## Discovery Engine

The **Lead Discovery Engine** enables proactive lead generation by searching external data sources based on ideal customer profiles (ICP).

### Discovery Search
Define search criteria once, reuse indefinitely:
- Industry filters (e.g., "fintech", "healthcare")
- Company size ranges (e.g., 10-500 employees)
- Technology requirements (e.g., "Salesforce", "HubSpot")
- Keywords (e.g., "Series A", "hiring engineer")
- Geography targeting

### Discovery Run
Execute a discovery search to find matching companies:
- **Status Tracking**: `running`, `succeeded`, `failed`
- **Statistics**: Sources queried, companies found/created/skipped
- **Error Reporting**: Detailed error messages for failed runs

### Discovery Agent
Multi-source discovery with graceful degradation:
1. **SEC EDGAR**: Unlimited full-text search for US public company filings
2. **Google News RSS**: Unlimited news feed searches for funding/hiring signals
3. **OpenCorporates**: 500 lookups/month for international company registry data

### Discovery Pipeline Workflow
```
Search Criteria → Discovery Agent → Deduplicate → Create Companies → Update Stats
                      │
                      ├── SEC EDGAR
                      ├── Google News RSS
                      └── OpenCorporates
```

Companies are created with:
- `status='needs_review'` for manual approval
- `discovered_via='discovery_pipeline'` for audit trail
- `discovery_score` (0.0-1.0) for prioritization
- Link to originating `discovery_search`

---

## Project Structure

```
irtiqa-intelligence/
├── app/
│   ├── agents/              # 6 production agents
│   │   ├── deep_scraper/    # Web scraping & content extraction
│   │   ├── technographic/   # Technology detection
│   │   ├── intent_signal/   # Buying signal detection
│   │   ├── intelligence_scoring/  # Lead scoring
│   │   ├── personalization/ # Outreach generation
│   │   └── discovery/       # Company discovery
│   ├── api/                 # REST API endpoints
│   │   └── v1/endpoints/    # Versioned API routes
│   ├── core/                # Configuration, logging, errors
│   ├── database/            # Engine, session management
│   ├── jobs/                # Background job system
│   ├── models/              # SQLAlchemy ORM models (19 tables)
│   ├── repositories/        # Data access layer (15 repositories)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer (15 services)
│   └── workflows/           # Multi-agent orchestration (3 workflows)
├── database/
│   └── migrations/          # Alembic migration scripts
├── docs/                    # Architecture & design documentation
├── tests/
│   ├── integration/         # End-to-end tests (database, API, workflows)
│   └── unit/                # Component tests (agents, services, schemas)
├── .env.example             # Environment variable template
├── alembic.ini              # Alembic configuration
├── pyproject.toml           # Dependencies & project metadata
└── README.md
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | FastAPI 0.115+ | Async web framework with OpenAPI |
| **ORM** | SQLAlchemy 2.0 | Database abstraction & query building |
| **Migrations** | Alembic 1.18+ | Schema versioning & evolution |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Database (Dev)** | SQLite 3.x | Local development with WAL mode |
| **Database (Prod)** | PostgreSQL 18+ | Production-grade relational database |
| **HTTP Client** | httpx | Async HTTP for external API calls |
| **Parsing** | BeautifulSoup4, feedparser | HTML & RSS feed parsing |
| **Testing** | pytest, pytest-asyncio | Test framework with async support |
| **CI/CD** | GitHub Actions | Automated testing & validation |

---

## Testing

Comprehensive test coverage across all layers:

- **633 Tests** (606 SQLite, 27 PostgreSQL compatibility)
- **100% Pass Rate** on main branch
- **Test Types**:
  - Unit tests for agents, services, schemas, workflows
  - Integration tests for API endpoints, repositories, pipelines
  - Database tests for migrations, constraints, transactions
  - PostgreSQL compatibility tests (18.x verified)

### CI Pipeline
Every push and PR runs:
1. **Validation**: Ruff linting, mypy type checking, compileall syntax check
2. **Migration Check**: Alembic schema drift detection
3. **SQLite Tests**: Full test suite (606 tests)
4. **PostgreSQL Tests**: Compatibility verification (27 tests)

**GitHub Actions Badge:** ![CI](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml/badge.svg)

---

## Development

### Prerequisites
- Python 3.11+
- pip or uv (recommended)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Luffyz/irtiqa-intelligence.git
   cd irtiqa-intelligence
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .[dev]
   ```

   For PostgreSQL support:
   ```bash
   pip install "psycopg[binary]>=3.2.0"
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

### Environment Variables

Key configuration options in `.env`:

```bash
# Database
DATABASE_URL=sqlite:///database/irtiqa.db
# For PostgreSQL: postgresql+psycopg://user:pass@localhost:5432/irtiqa

# Logging
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true

# Discovery Engine
SEC_EDGAR_USER_AGENT=YourCompany/1.0 (your-email@example.com)
OPENCORPORATES_API_KEY=your-key-here  # Optional
ENABLED_SOURCES=sec_edgar,google_news_rss,opencorporates
MAX_COMPANIES_PER_RUN=100

# Authentication
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=RS256
```

### Run Migrations

Apply database schema:
```bash
python -m alembic upgrade head
```

Check for schema drift:
```bash
python -m alembic check
```

### Run Development Server

Start the FastAPI server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Run Tests

Execute full test suite:
```bash
python -m pytest
```

Run with coverage:
```bash
python -m pytest --cov=app --cov-report=html
```

Run specific test categories:
```bash
# Unit tests only
python -m pytest tests/unit/

# Integration tests only
python -m pytest tests/integration/

# PostgreSQL compatibility tests
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_test \
python -m pytest tests/integration/test_postgresql_compatibility.py
```

### Alembic Commands

```bash
# Create new migration
python -m alembic revision --autogenerate -m "description"

# Upgrade to latest
python -m alembic upgrade head

# Downgrade one revision
python -m alembic downgrade -1

# Show current revision
python -m alembic current

# Show migration history
python -m alembic history
```

---

## API Documentation

Once the server is running, explore the interactive API documentation:

- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/companies` | GET, POST | Company CRUD operations |
| `/api/v1/leads` | GET | Aggregated lead intelligence |
| `/api/v1/discovery/searches` | GET, POST | ICP search management |
| `/api/v1/discovery/runs` | GET | Discovery run status & history |
| `/api/v1/intelligence/pipeline` | POST | Trigger intelligence enrichment |
| `/api/v1/jobs` | GET | Background job monitoring |
| `/api/v1/evidence/by-company/{id}` | GET | Evidence audit trail |
| `/auth/register` | POST | User registration |
| `/auth/login` | POST | JWT authentication |

---

## Roadmap

### Current Status: Backend Complete ✅

The backend is production-ready with all planned features implemented:
- ✅ Authentication & multi-tenancy
- ✅ Lead discovery engine
- ✅ Intelligence pipeline (6 agents)
- ✅ Workflow orchestration
- ✅ Background job system
- ✅ REST API (70+ endpoints)
- ✅ 633 automated tests

### Next Milestones

**Phase 1: Frontend Development**
- React/Vue.js web application
- ICP search builder UI
- Discovery run monitoring dashboard
- Lead review & enrichment interface
- Intelligence score visualization

**Phase 2: Production Deployment**
- Docker containerization
- PostgreSQL database migration
- Kubernetes/cloud deployment manifests
- CI/CD pipeline for releases
- Monitoring & observability (Grafana, Prometheus)

**Phase 3: Advanced Features**
- Scheduled discovery runs (daily/weekly ICP searches)
- ML-based lead scoring models
- CRM integrations (Salesforce, HubSpot)
- Email automation & outreach tracking
- Advanced analytics & reporting

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Ensure all tests pass (`python -m pytest`)
5. Check for schema drift (`python -m alembic check`)
6. Commit with descriptive messages
7. Push to your fork and submit a pull request

---

## License

This project is proprietary software. All rights reserved.

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL toolkit
- [Alembic](https://alembic.sqlalchemy.org/) - Database migrations
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [pytest](https://pytest.org/) - Testing framework

---

**Production-Ready Backend · 633 Tests · 19 Database Tables · 6 Intelligence Agents · 70+ API Endpoints**
