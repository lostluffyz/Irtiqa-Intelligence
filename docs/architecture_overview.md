# Architecture Overview

High-level map of how all components in Irtiqa Intelligence connect.

> **Note:** This is the main architectural reference. For specific subsystems, see:
> - [Database Design](database.md) — Schema, relationships, migrations
> - [Agent System](agents.md) — Intelligence gathering components
> - [Workflow System](workflows.md) — Multi-agent orchestration
> - [Background Jobs](background_job_foundation_design.md) — Async execution
> - [Authentication](authentication_multitenancy_v2_design.md) — JWT and multi-tenancy

---

## Terminology

Key terms used throughout the documentation:

| Term | Definition |
|------|------------|
| **Company** | Organization entity (canonical business entity) |
| **Contact** | Person entity linked to a company |
| **Lead** | Company + Contact + Intelligence Score (scored prospect for retrieval) |
| **Organization** | User-facing tenant entity (multi-tenancy boundary) |
| **Tenant** | Technical term for organization in multi-tenancy context |
| **Agent Run** | Single execution of an agent (stored in `agent_runs` table) |
| **Workflow Context** | Input parameters passed to workflow execution |

---

## System Layers

```mermaid
graph TD
    Client[Client Application] -->|HTTP Request| API[API Layer<br/>FastAPI + OpenAPI]
    
    API -->|Dependency Injection| Auth[Authentication<br/>JWT Verification]
    Auth -->|Organization Context| Service[Service Layer<br/>Business Logic + Transactions]
    
    Service -->|Orchestration| Workflow[Workflow System<br/>Multi-Agent Coordination]
    Service -->|Intelligence| Agent[Agent System<br/>6 Specialized Agents]
    Service -->|Data Access| Repository[Repository Layer<br/>Query Building + Tenant Filtering]
    
    Workflow --> Agent
    Agent --> Repository
    
    Repository -->|SQLAlchemy ORM| ORM[ORM Layer<br/>Models + Relationships]
    ORM -->|Database Connection| DB[(Database<br/>SQLite/PostgreSQL)]
    
    Service -.->|Async Tasks| Jobs[Background Job System<br/>Scheduler + Runner]
    Jobs -->|Execute| Workflow
    Jobs -->|Execute| Agent
    
    style API fill:#e1f5ff
    style Service fill:#fff4e1
    style Repository fill:#f0e1ff
    style DB fill:#e1ffe1
    style Agent fill:#ffe1e1
    style Workflow fill:#ffe1f5
```

### Layer Responsibilities

| Layer | Responsibility | Owns |
|-------|---------------|------|
| **API** | HTTP routing, request validation, OpenAPI docs | FastAPI routes, Pydantic schemas |
| **Service** | Business logic, transaction boundaries | Use case methods, `session_scope()` commits |
| **Workflow** | Multi-agent orchestration, step sequencing | Workflow definitions, error handling |
| **Agent** | Intelligence gathering, external API integration | Agent-specific logic, evidence recording |
| **Repository** | Query building, tenant filtering | SQLAlchemy queries, `_apply_tenant_filter()` |
| **ORM** | Object-relational mapping, relationships | Model definitions, foreign keys |
| **Database** | Data persistence, constraints, indexes | SQLite (dev), PostgreSQL (prod) |

---

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Auth as JWT Middleware
    participant Org as get_current_organization
    participant Service
    participant Repo as Repository
    participant DB as Database
    
    Client->>FastAPI: HTTP Request + Bearer Token
    FastAPI->>Auth: Extract & Verify JWT
    Auth->>Auth: Decode RS256 signature
    Auth->>Org: Verify membership(user_id, org_id)
    Org->>DB: SELECT memberships WHERE...
    DB-->>Org: Membership record
    Org-->>FastAPI: Organization context attached
    
    FastAPI->>Service: Call service method(org_id, ...)
    
    Note over Service: session_scope() context manager
    Service->>Service: Begin transaction
    Service->>Repo: Query with org_id filter
    Repo->>Repo: _apply_tenant_filter(organization_id)
    Repo->>DB: SELECT WHERE organization_id = ?
    DB-->>Repo: Filtered results
    Repo-->>Service: ORM objects
    Service->>Service: Business logic transformation
    Service->>DB: COMMIT transaction
    
    Service-->>FastAPI: Result data
    FastAPI-->>Client: HTTP Response (JSON)
    
    Note over Service: On exception: ROLLBACK
```

### Transaction Boundaries

**Services own transaction boundaries:**
- Each service method wraps operations in `session_scope()` context manager
- Repositories **never commit** — they accept sessions and build queries
- API routes call services, not repositories directly
- Transactions commit on successful service method completion
- Transactions rollback automatically on exceptions

```python
# Service Layer Pattern
class CompanyService(BaseService):
    def create(self, organization_id: str, **values) -> Company:
        with session_scope() as session:  # Transaction boundary
            repository = self.repository(session)
            company = repository.create(**values)
            session.flush()  # Validate constraints
            return company  # Commit happens here automatically
```

---

## Dependency Injection

```mermaid
graph LR
    Request[HTTP Request] --> Deps[FastAPI Dependencies]
    
    Deps --> Session[get_db_session<br/>SQLAlchemy Session]
    Deps --> Org[get_current_organization<br/>Organization Context]
    
    Session --> ServiceFactory[Service Factories<br/>get_company_service<br/>get_contact_service<br/>etc.]
    Org --> ServiceFactory
    
    ServiceFactory --> Service[Service Instances<br/>with session + org_id]
    Service --> Repo[Repository Instances<br/>with session]
    
    style Deps fill:#e1f5ff
    style Session fill:#fff4e1
    style Org fill:#ffe1e1
```

**Dependency Chain:**
1. `get_db_session()` → Provides SQLAlchemy session for database access
2. `get_current_organization()` → Verifies JWT, validates membership, returns org context
3. Service factories (e.g., `get_company_service()`) → Inject session + org context into services
4. Repositories instantiated by services → Receive session, apply tenant filters

---

## Multi-Tenancy Boundary Enforcement

```mermaid
flowchart TD
    JWT[JWT Token<br/>Claims: sub, org] --> Verify[JWT Middleware<br/>Verify Signature]
    Verify --> Membership[get_current_organization<br/>Verify Membership]
    Membership --> DBCheck{Membership<br/>Exists?}
    
    DBCheck -->|No| Reject[403 Forbidden]
    DBCheck -->|Yes| Context[Attach Organization Context<br/>organization_id]
    
    Context --> Service[Service Method Call<br/>service.method(org_id, ...)]
    Service --> Repo[Repository Query<br/>repository.list(org_id)]
    Repo --> Filter[_apply_tenant_filter<br/>Add WHERE clause]
    Filter --> SQL["SQL Query<br/>SELECT * FROM companies<br/>WHERE organization_id = ?"]
    SQL --> Result[Tenant-Scoped Results]
    
    style DBCheck fill:#ffe1e1
    style Filter fill:#fff4e1
    style SQL fill:#e1ffe1
```

### Enforcement Layers

| Layer | Enforcement Mechanism | Failure Mode |
|-------|----------------------|--------------|
| **JWT** | RS256 signature verification | 401 Unauthorized |
| **Membership** | Database lookup on every request | 403 Forbidden |
| **Repository** | `_apply_tenant_filter()` adds WHERE clause | Empty result set (silent) |
| **Database** | Foreign key constraints on `organization_id` | IntegrityError exception |

**Security Principle:** Trust nothing. Verify at every layer.

See [Authentication & Multi-Tenancy](authentication_multitenancy_v2_design.md) for complete security design.

---

## Cross-Cutting Concerns

```mermaid
graph TD
    System[Core System<br/>API + Service + Repository]
    
    Logging[Centralized Logging<br/>irtiqa.* namespaces] -.->|logs all operations| System
    System -.->|emits log events| Logging
    
    Errors[Structured Errors<br/>IrtiqaError hierarchy] -.->|propagates exceptions| System
    System -.->|raises typed errors| Errors
    
    Tenant[Multi-Tenancy<br/>Organization ID filtering] -.->|enforces isolation| System
    System -.->|respects org boundaries| Tenant
    
    Jobs[Background Jobs<br/>Scheduler + Runner] -.->|schedules async work| System
    System -.->|delegates to jobs| Jobs
    
    Evidence[Evidence Records<br/>Audit trail] -.->|records provenance| System
    System -.->|creates evidence| Evidence
    
    style System fill:#e1f5ff
    style Logging fill:#fff4e1
    style Errors fill:#ffe1e1
    style Tenant fill:#f0e1ff
    style Jobs fill:#e1ffe1
    style Evidence fill:#ffe1f5
```

### Integration Points

| Concern | How It Integrates |
|---------|------------------|
| **Logging** | Services and repositories emit structured logs via `get_logger()` |
| **Errors** | All layers raise `IrtiqaError` subclasses with error codes and details |
| **Multi-Tenancy** | Repository layer automatically filters by `organization_id` |
| **Background Jobs** | API routes schedule long-running work via `JobService` |
| **Evidence** | Agents record provenance via `BaseAgent.execute()` lifecycle |

---

## Intelligence Pipeline Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as POST /intelligence/pipeline
    participant JobService
    participant JobRunner
    participant Workflow as IntelligencePipelineWorkflow
    participant Agents as Agents (5 sequential)
    participant Services as Domain Services
    participant DB as Database
    
    Client->>API: Trigger pipeline for company_id
    API->>JobService: schedule_workflow(intelligence_pipeline)
    JobService->>DB: INSERT INTO jobs (status=pending)
    JobService-->>API: Job ID
    API-->>Client: 202 Accepted + job_id
    
    Note over JobRunner: Background polling loop
    JobRunner->>DB: SELECT * FROM jobs WHERE status=pending
    DB-->>JobRunner: Job record
    JobRunner->>JobRunner: Lock job (status=running)
    JobRunner->>Workflow: execute(context)
    
    Workflow->>Agents: 1. DeepScraperAgent.execute()
    Agents->>Services: WebsiteService.create_batch()
    Services->>DB: INSERT INTO websites
    Agents-->>Workflow: Website IDs + HTML
    
    Workflow->>Agents: 2. TechnographicAgent.execute()
    Agents->>Services: TechnologyService.create_batch()
    Services->>DB: INSERT INTO technologies
    Agents-->>Workflow: Technology IDs
    
    Workflow->>Agents: 3. IntentSignalAgent.execute()
    Agents->>Services: IntentSignalService.create_batch()
    Services->>DB: INSERT INTO intent_signals
    Agents-->>Workflow: Signal IDs
    
    Workflow->>Agents: 4. IntelligenceScoringAgent.execute()
    Agents->>Services: IntelligenceScoreService.create()
    Services->>DB: INSERT INTO intelligence_scores
    Agents-->>Workflow: Score ID
    
    Workflow->>Agents: 5. PersonalizationAgent.execute()
    Agents->>Services: OutreachMessageService.create_batch()
    Services->>DB: INSERT INTO outreach_messages
    Agents-->>Workflow: Message IDs
    
    Workflow-->>JobRunner: WorkflowResult(status=succeeded)
    JobRunner->>DB: UPDATE jobs SET status=succeeded
    
    Note over JobRunner,DB: Each agent creates agent_runs record for observability
```

Each step creates an `agent_runs` record for observability. Pipeline stops on first agent failure.

---

## Lead Retrieval Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as GET /api/v1/leads
    participant Service as LeadRetrievalService
    participant CompanyRepo as CompanyRepository
    participant DB as Database
    
    Client->>API: GET /leads?minimum_score=70&limit=50
    API->>Service: list_leads(org_id, min_score, limit, offset)
    
    Note over Service: Batch loading strategy (N+1 prevention)
    
    Service->>CompanyRepo: list(organization_id, limit, offset)
    CompanyRepo->>DB: SELECT * FROM companies WHERE...
    DB-->>CompanyRepo: Company records
    CompanyRepo-->>Service: companies (50 records)
    
    Service->>Service: Extract company_ids: [id1, id2, ...]
    
    par Batch Load Technologies
        Service->>DB: SELECT * FROM technologies WHERE company_id IN (...)
    and Batch Load Intent Signals
        Service->>DB: SELECT * FROM intent_signals WHERE company_id IN (...)
    and Batch Load Latest Scores
        Service->>DB: SELECT DISTINCT ON (company_id) * FROM intelligence_scores<br/>WHERE company_id IN (...) ORDER BY created_at DESC
    and Batch Load Outreach Messages
        Service->>DB: SELECT * FROM outreach_messages WHERE company_id IN (...)
    end
    
    DB-->>Service: All related data
    
    Service->>Service: Aggregate data per company<br/>Filter by minimum_score<br/>Build LeadResponse objects
    
    Service-->>API: LeadListResponse(items, total, limit, offset)
    API-->>Client: JSON response (aggregated leads)
    
    Note over Service: Single batch query per relationship<br/>No N+1 queries
```

**Performance Strategy:**
- Single query for companies (paginated)
- Batch query for each relationship using `WHERE company_id IN (...)`
- Subquery for latest intelligence scores (DISTINCT ON pattern)
- Aggregation in memory (acceptable for paginated results)

---

## Key Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Multi-tenancy** | `organization_id` column on all domain tables, filtered via `_apply_tenant_filter()` | Repository layer |
| **Pagination** | `items`, `total`, `limit`, `offset` on all list responses | Service + API layer |
| **Error handling** | Structured `IrtiqaError` hierarchy with stable error codes | `app/core/errors.py` |
| **Logging** | Centralized via `irtiqa.*` logger namespaces | `app/core/logging.py` |
| **Testing** | pytest with temporary SQLite databases per test | `tests/conftest.py` |
| **Dependency Injection** | FastAPI `Depends()` for session, organization, services | `app/api/dependencies.py` |
| **Transaction Ownership** | Services own `session_scope()`, repositories never commit | Service layer |
| **Agent Template Method** | `BaseAgent.execute()` calls `_validate()`, `_run()`, `_record_evidence()` | `app/agents/base.py` |
| **Workflow Orchestration** | `WorkflowRunner` manages lifecycle, delegates to agents | `app/workflows/runner.py` |

---

## CI/CD Pipeline

```mermaid
flowchart LR
    Push[Git Push] --> Trigger[GitHub Actions Workflow]
    
    Trigger --> Validate[Validation Job]
    Validate --> Ruff[Ruff Linting<br/>Advisory]
    Validate --> Mypy[Mypy Type Check<br/>Advisory]
    Validate --> Compile[compileall Syntax<br/>BLOCKING]
    
    Trigger --> Test[Test Job]
    Test --> Migrate[Alembic Upgrade<br/>BLOCKING]
    Test --> Drift[Alembic Check<br/>BLOCKING]
    Test --> SQLite[SQLite Test Suite<br/>606 tests<br/>BLOCKING]
    Test --> Postgres[PostgreSQL Tests<br/>27 tests<br/>BLOCKING]
    
    Compile --> Status{All Checks Pass?}
    Migrate --> Status
    Drift --> Status
    SQLite --> Status
    Postgres --> Status
    
    Status -->|Yes| Success[✓ CI Pass]
    Status -->|No| Failure[✗ CI Fail]
    
    style Success fill:#e1ffe1
    style Failure fill:#ffe1e1
    style Compile fill:#fff4e1
    style Migrate fill:#fff4e1
    style Drift fill:#fff4e1
    style SQLite fill:#fff4e1
    style Postgres fill:#fff4e1
```

**CI Strategy:**
- **Ruff & Mypy:** Advisory during debt reduction phase (continue-on-error: true)
- **Compileall:** BLOCKING (syntax errors fail build)
- **Migrations:** BLOCKING (schema drift fails build)
- **Tests:** BLOCKING (633 tests must pass)

GitHub Actions workflow: `.github/workflows/ci.yml`

---

## Related Documentation

- **[Database Design](database.md)** — Complete schema, relationships, migrations, backup procedures
- **[Entity Relationships](entity_relationships.md)** — Detailed FK relationships and constraints
- **[Agent System](agents.md)** — All 6 agents, responsibilities, lifecycles
- **[Agent Interface](agent_interface_design.md)** — BaseAgent pattern, AgentContext, AgentResult
- **[Workflow System](workflows.md)** — Workflow orchestration, concrete implementations
- **[Background Jobs](background_job_foundation_design.md)** — Async execution, retry policies
- **[Authentication](authentication_multitenancy_v2_design.md)** — JWT, multi-tenancy, RBAC
- **[Discovery Engine](lead_discovery_engine_final.md)** — ICP search, external sources, deduplication
- **[Evidence System](evidence_records_system_design.md)** — Provenance tracking, audit trail

---

**Last Updated:** 2026-07-01  
**Status:** Production-Ready Backend  
**Test Coverage:** 633 tests (100% pass rate)
