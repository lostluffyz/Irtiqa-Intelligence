# Irtiqa Intelligence

[![CI](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-633%20passing-success)](https://github.com/Luffyz/irtiqa-intelligence)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)

**Production-grade lead intelligence platform for B2B sales teams.**

Irtiqa Intelligence automates lead discovery, enrichment, and prioritization through intelligent web scraping, technographic analysis, intent signal detection, and personalized outreach generation. Built with FastAPI, SQLAlchemy, and a modular agent-based architecture.

---

## What is Irtiqa?

Irtiqa transforms raw company data into actionable sales intelligence through a **multi-agent pipeline**:

1. **Discover** companies matching your ideal customer profile (ICP)
2. **Scrape** and analyze company websites for technology signals
3. **Detect** buying intent from hiring, funding, and technology changes
4. **Score** leads using multi-factor intelligence scoring
5. **Personalize** outreach messages based on company intelligence

**Result:** Prioritized, scored leads with context-aware outreach recommendations.

---

## Architecture

```mermaid
graph TD
    subgraph Client["Client Layer"]
        UI[Web UI / API Client]
    end
    
    subgraph API["API Layer (FastAPI)"]
        Routes[REST Endpoints<br/>70+ endpoints]
        Auth[JWT Authentication<br/>Multi-Tenancy]
    end
    
    subgraph Service["Service Layer"]
        Services[Business Logic<br/>Transaction Boundaries]
    end
    
    subgraph Intelligence["Intelligence Layer"]
        Workflows[3 Workflows<br/>Orchestration]
        Agents[6 Agents<br/>Specialized Intelligence]
    end
    
    subgraph Data["Data Layer"]
        Repos[Repositories<br/>Tenant Filtering]
        ORM[SQLAlchemy ORM<br/>19 Tables]
    end
    
    subgraph Storage["Storage Layer"]
        SQLite[(SQLite Dev)]
        Postgres[(PostgreSQL Prod)]
    end
    
    subgraph Jobs["Background Jobs"]
        Scheduler[Job Scheduler]
        Runner[Job Runner]
    end
    
    UI -->|HTTP + JWT| Routes
    Routes -->|Verify & Inject| Auth
    Auth -->|Call Methods| Services
    Services -->|Orchestrate| Workflows
    Services -->|Execute| Agents
    Workflows -->|Chain| Agents
    Agents -->|Query/Persist| Repos
    Services -->|Query/Persist| Repos
    Repos -->|Map Entities| ORM
    ORM -->|Connect| SQLite
    ORM -->|Connect| Postgres
    
    Services -.->|Schedule Async| Scheduler
    Scheduler -->|Poll & Execute| Runner
    Runner -->|Invoke| Workflows
    Runner -->|Invoke| Agents
    
    style API fill:#e1f5ff
    style Service fill:#fff4e1
    style Intelligence fill:#ffe1e1
    style Data fill:#f0e1ff
    style Storage fill:#e1ffe1
    style Jobs fill:#ffe1f5
```

**[📖 Complete Architecture Guide](docs/architecture_overview.md)**

---

## Features

### 🔐 Authentication & Multi-Tenancy
- **RS256 JWT Authentication** with JWKS endpoint for secure API access
- **Email Verification** and password reset workflows
- **Organization Management** with role-based access control (Owner, Admin, Member, Viewer)
- **Tenant Isolation** across all data and API endpoints
- **Rate Limiting** with database-backed tracking

**[📖 Authentication Design](docs/authentication_multitenancy_v2_design.md)**

### 🔍 Lead Discovery Engine

```mermaid
flowchart LR
    ICP[ICP Search<br/>Industry + Size + Tech] --> Discovery[Discovery Agent]
    
    Discovery -->|Query| EDGAR[SEC EDGAR<br/>US Companies]
    Discovery -->|Query| News[Google News RSS<br/>Funding Signals]
    Discovery -->|Query| OC[OpenCorporates<br/>Global Registry]
    
    EDGAR --> Dedupe[Deduplication<br/>Domain Matching]
    News --> Dedupe
    OC --> Dedupe
    
    Dedupe --> Score[Discovery Score<br/>0.0-1.0]
    Score --> Companies[(Companies<br/>needs_review)]
    
    Companies -.->|Manual Trigger| Pipeline[Intelligence Pipeline]
    
    style Discovery fill:#e1f5ff
    style Dedupe fill:#fff4e1
    style Score fill:#ffe1e1
    style Companies fill:#e1ffe1
```

- **ICP Search Management**: Define and save ideal customer profile criteria
- **Multi-Source Discovery**: Automated searches across SEC EDGAR, Google News RSS, and OpenCorporates
- **Smart Deduplication**: Domain-based duplicate detection with fuzzy matching
- **Discovery Scoring**: Lightweight match quality scores (0.0-1.0) for prioritization
- **Evidence Provenance**: Full audit trail of discovery sources

**[📖 Discovery Engine Design](docs/lead_discovery_engine_final.md)**

### 🤖 Intelligence Pipeline

```mermaid
flowchart LR
    Input[Company Domain] --> DS[Deep Scraper<br/>Web Extraction]
    DS -->|HTML + Text| Tech[Technographic<br/>Tech Detection]
    Tech -->|40+ Signatures| Intent[Intent Signal<br/>Buying Signals]
    Intent -->|8 Signal Types| Score[Intelligence Scoring<br/>Multi-Factor]
    Score -->|Weighted Score| Person[Personalization<br/>Outreach Generation]
    Person --> Output[Scored Lead<br/>+ Messages]
    
    style DS fill:#e1f5ff
    style Tech fill:#fff4e1
    style Intent fill:#ffe1e1
    style Score fill:#f0e1ff
    style Person fill:#e1ffe1
```

**6 Production Agents:**
1. **Deep Scraper Agent**: Web content extraction and parsing
2. **Technographic Agent**: Technology detection (40+ signatures across 8 categories)
3. **Intent Signal Agent**: Buying signal detection (8 signal families with deterministic rules)
4. **Intelligence Scoring Agent**: Multi-factor lead scoring (fit, intent, technographic, engagement)
5. **Personalization Agent**: Multi-variant outreach message generation
6. **Discovery Agent**: ICP-based company discovery from external sources

**[📖 Agent System](docs/agents.md)** | **[📖 Workflow System](docs/workflows.md)**

### 📊 Lead Retrieval API
- **Aggregated Intelligence**: Single endpoint returns companies with technologies, intent signals, scores, and outreach messages
- **Smart Filtering**: Filter by minimum score, pagination support
- **Tenant-Scoped**: Automatic organization isolation
- **N+1 Prevention**: Batch loading strategy for optimal performance

### ⚙️ Background Job System
- **Async Execution**: Agent and workflow scheduling with status tracking
- **Retry Policies**: Exponential backoff with configurable limits
- **Job Management**: Schedule, cancel, retry, and monitor background tasks

**[📖 Background Jobs Design](docs/background_job_foundation_design.md)**

### 📈 Evidence Records
- **Provenance Tracking**: Full audit trail for all intelligence data
- **Source Linking**: Evidence tied to agent runs, URLs, and API responses
- **Confidence Scoring**: Evidence quality metrics

### 🔄 Workflow Orchestration
- **Score Refresh**: Deterministic intelligence score recomputation
- **Intelligence Pipeline**: End-to-end enrichment (scrape → analyze → score → personalize)
- **Discovery Pipeline**: Company discovery orchestration (search → discover → deduplicate → create)

---

## Database Schema

```mermaid
erDiagram
    organizations ||--o{ companies : owns
    organizations ||--o{ contacts : owns
    companies ||--o{ websites : has
    companies ||--o{ technologies : uses
    companies ||--o{ intent_signals : emits
    companies ||--o{ intelligence_scores : receives
    companies ||--o{ outreach_messages : targeted_by
    
    agent_runs ||--o{ technologies : detects
    agent_runs ||--o{ intent_signals : finds
    agent_runs ||--o{ intelligence_scores : computes
    agent_runs ||--o{ outreach_messages : generates
    agent_runs ||--o{ evidence_records : produces
    
    discovery_searches ||--o{ discovery_runs : executes
    discovery_searches ||--o{ companies : discovers
    
    jobs ||--o{ agent_runs : triggers
```

**19 Tables:**
- 8 core intelligence tables (companies, contacts, websites, technologies, intent_signals, intelligence_scores, outreach_messages, evidence_records)
- 2 system tables (agent_runs, jobs)
- 2 discovery tables (discovery_searches, discovery_runs)
- 3 auth tables (users, organizations, memberships)
- 4 token tables (refresh_tokens, email_verification_tokens, password_reset_tokens, failed_login_attempts)

**[📖 Database Design](docs/database.md)** | **[📖 Entity Relationships](docs/entity_relationships.md)**

---

## Project Structure

```
irtiqa-intelligence/
├── app/
│   ├── agents/              # 6 production agents
│   │   ├── deep_scraper/    # Web scraping & content extraction
│   │   ├── technographic/   # Technology detection (40+ signatures)
│   │   ├── intent_signal/   # Buying signal detection (8 families)
│   │   ├── intelligence_scoring/  # Lead scoring
│   │   ├── personalization/ # Outreach generation
│   │   └── discovery/       # Company discovery (3 sources)
│   ├── api/                 # REST API endpoints (70+)
│   ├── core/                # Configuration, logging, errors
│   ├── database/            # Engine, session management
│   ├── jobs/                # Background job system
│   ├── models/              # SQLAlchemy ORM models (19 tables)
│   ├── repositories/        # Data access layer (15 repositories)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer (15 services)
│   └── workflows/           # Multi-agent orchestration (3 workflows)
├── database/
│   └── migrations/          # Alembic migration scripts (8 revisions)
├── docs/                    # Architecture & design documentation
├── tests/
│   ├── integration/         # End-to-end tests
│   └── unit/                # Component tests
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

```mermaid
flowchart LR
    Push[Git Push/PR] --> CI[GitHub Actions]
    
    CI --> Validate[Validation]
    CI --> Test[Testing]
    
    Validate --> Ruff[Ruff Lint<br/>Advisory]
    Validate --> Mypy[Mypy Types<br/>Advisory]
    Validate --> Compile[compileall<br/>BLOCKING]
    
    Test --> Migrate[Alembic Upgrade<br/>BLOCKING]
    Test --> Drift[Schema Drift Check<br/>BLOCKING]
    Test --> SQLiteTests[SQLite Tests<br/>606 tests<br/>BLOCKING]
    Test --> PGTests[PostgreSQL Tests<br/>27 tests<br/>BLOCKING]
    
    Compile --> Result{All Pass?}
    Migrate --> Result
    Drift --> Result
    SQLiteTests --> Result
    PGTests --> Result
    
    Result -->|Yes| Success[✓ CI Pass]
    Result -->|No| Failure[✗ CI Fail]
    
    style Success fill:#e1ffe1
    style Failure fill:#ffe1e1
```

**633 Tests** (606 SQLite, 27 PostgreSQL compatibility)  
**100% Pass Rate** on main branch

**Test Coverage:**
- Unit tests for agents, services, schemas, workflows
- Integration tests for API endpoints, repositories, pipelines
- Database tests for migrations, constraints, transactions
- PostgreSQL compatibility verification

---

## Development

### Installation

```bash
# Clone repository
git clone https://github.com/Luffyz/irtiqa-intelligence.git
cd irtiqa-intelligence

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate      # Windows

# Install dependencies
pip install -e .[dev]

# For PostgreSQL support
pip install "psycopg[binary]>=3.2.0"

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Run Migrations

```bash
# Apply database schema
python -m alembic upgrade head

# Check for schema drift
python -m alembic check
```

### Run Development Server

```bash
# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Run Tests

```bash
# Execute full test suite
python -m pytest

# Run with coverage
python -m pytest --cov=app --cov-report=html

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
```

---

## Documentation Map

### Getting Started
- **[README](README.md)** — This file (overview, setup, quick start)
- **[Architecture Overview](docs/architecture_overview.md)** — System layers, request lifecycle, patterns

### Core Systems
- **[Database Design](docs/database.md)** — Schema, tables, constraints, migrations
- **[Entity Relationships](docs/entity_relationships.md)** — FK relationships, cascade rules
- **[Agent System](docs/agents.md)** — All 6 agents, responsibilities, lifecycles
- **[Workflow System](docs/workflows.md)** — Workflow orchestration, implementations
- **[Background Jobs](docs/background_job_foundation_design.md)** — Async execution, retry policies

### Features
- **[Discovery Engine](docs/lead_discovery_engine_final.md)** — ICP search, external sources, deduplication
- **[Authentication](docs/authentication_multitenancy_v2_design.md)** — JWT, multi-tenancy, RBAC
- **[Evidence System](docs/evidence_records_system_design.md)** — Provenance tracking

### Specialized Documentation
- **[Agent Interface Design](docs/agent_interface_design.md)** — BaseAgent pattern details
- **[Deep Scraper Design](docs/deep_scraper_design.md)** — Web scraping architecture
- **[Technographic Agent Design](docs/technographic_agent_design.md)** — Technology detection
- **[Intent Signal Agent Design](docs/intent_signal_agent_design.md)** — Buying signal rules
- **[Personalization Agent Design](docs/personalization_agent_design.md)** — Outreach generation

---

## Roadmap

### ✅ Current Status: Backend Complete

The backend is production-ready with all planned features implemented:
- ✅ Authentication & multi-tenancy
- ✅ Lead discovery engine
- ✅ Intelligence pipeline (6 agents)
- ✅ Workflow orchestration
- ✅ Background job system
- ✅ REST API (70+ endpoints)
- ✅ 633 automated tests

### 🎯 Next Milestones

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
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) — Python SQL toolkit
- [Alembic](https://alembic.sqlalchemy.org/) — Database migrations
- [Pydantic](https://docs.pydantic.dev/) — Data validation
- [pytest](https://pytest.org/) — Testing framework

---

**Production-Ready Backend · 633 Tests · 19 Database Tables · 6 Intelligence Agents · 70+ API Endpoints**
