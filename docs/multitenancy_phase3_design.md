> **Status: IMPLEMENTED**

# Multi-Tenancy Phase 3: Tenant Isolation for Business Entities — Design Document

> **Source:** `docs/multitenancy_phase3_audit.md`
>
> **Goal:** Add `organization_id` to all 8 business entities, wire tenant filtering through the full stack, and close critical cross-tenant data leakage.

---

## 1. Design Decisions

### 1.1 Denormalized `organization_id`

Every entity gets its own `organization_id` FK column rather than filtering through Company joins. Rationale:

1. **Single-column WHERE** — `WHERE organization_id = :org_id` is the simplest, most efficient filter.
2. **No JOIN overhead** — Every query adds one equality check vs. a JOIN to companies.
3. **Works with nullable company_id** — AgentRun, EvidenceRecord, and Job have optional `company_id`.
4. **Consistent with Phase 2** — `BaseRepository._apply_tenant_filter()` already implements this pattern.
5. **Auditable** — The column is visible in every query plan; no magic middleware.

### 1.2 NOT NULL vs. Nullable

| Entity | Nullable? | Rationale |
|---|---|---|
| Company | **NOT NULL** | Every company belongs to an org |
| Contact | **NOT NULL** | Every contact belongs to an org (via company) |
| IntentSignal | **NOT NULL** | Every signal belongs to an org |
| OutreachMessage | **NOT NULL** | Every message belongs to an org |
| EvidenceRecord | **NOT NULL** | Default-scoped; allow NULL only for backfill orphans (flag for review) |
| AgentRun | **NOT NULL** | Every run belongs to an org |
| IntelligenceScore | **NOT NULL** | Every score belongs to an org |
| Job | **NULLABLE** | Pending jobs may not have an agent_run yet; backfilled when claimed |

### 1.3 Unique Constraints

| Entity | Current Unique | Phase 3 Unique |
|---|---|---|
| Company | `domain` (global) | `(organization_id, domain)` |
| Contact | `email` (global) | `(organization_id, email)` |

All composite unique indexes use `organization_id` as the leading column.

### 1.4 Job Runner Isolation

- **System worker** (`get_next_jobs()`, `claim_job()`): Remains unscoped — a single pool serves all orgs.
- **User-facing** (`list_jobs()`, `cancel_job()`): Org-scoped via `organization_id`.

### 1.5 Score Ranking

`list_top_scores()` defaults to **org-scoped**. Cross-org access requires `?global=true` query parameter gated by `owner` role. This is the safest default (no accidental data leak) with an explicit opt-in for admin use.

### 1.6 Context Objects

`AgentContext` and `WorkflowContext` gain `organization_id`:

```python
class AgentContext(IrtiqaSchema):
    agent_name: str
    company_id: str
    contact_id: str | None = None
    organization_id: str        # NEW
    workflow_name: str | None = None
    correlation_id: str | None = None
    options: MappingProxyType[str, Any]

class WorkflowContext(IrtiqaSchema):
    workflow_name: str
    company_id: str | None = None
    contact_id: str | None = None
    organization_id: str | None = None  # NEW (nullable: some workflows may be org-agnostic)
    correlation_id: str | None = None
    requested_by: str | None = None
    options: MappingProxyType[str, Any]
```

---

## 2. Model Changes

### 2.1 Company

```python
# app/models/company.py

class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'needs_review', 'archived')", name="status_allowed"),
        # DROP: Index("ix_companies_domain", "domain", unique=True)
        # ADD: UniqueConstraint("organization_id", "domain", name="uq_companies_org_domain")
        Index("ix_companies_name", "name"),
        Index("ix_companies_industry", "industry"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_created_at", "created_at"),
        Index("ix_companies_organization_id", "organization_id"),  # NEW
    )

    # ... existing columns ...

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.2 Contact

```python
# app/models/contact.py

class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        CheckConstraint("status IN ('active', 'unverified', 'qualified', 'disqualified', 'archived')", name="status_allowed"),
        Index("ix_contacts_company_id", "company_id"),
        # DROP: Index("ix_contacts_email", "email", unique=True)
        # ADD: UniqueConstraint("organization_id", "email", name="uq_contacts_org_email")
        Index("ix_contacts_linkedin_url", "linkedin_url"),
        Index("ix_contacts_department", "department"),
        Index("ix_contacts_seniority", "seniority"),
        Index("ix_contacts_status", "status"),
        Index("ix_contacts_organization_id", "organization_id"),          # NEW
    )

    # ... existing columns ...

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.3 IntentSignal

```python
# app/models/intent_signal.py

class IntentSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        # DROP: Index("ix_intent_signals_company_id", "company_id")
        # DROP: Index("ix_intent_signals_company_type_observed", "company_id", "signal_type", "observed_at")
        # ADD: Index("ix_intent_signals_org_company_type_observed", "organization_id", "company_id", "signal_type", "observed_at")
        Index("ix_intent_signals_organization_id", "organization_id"),     # NEW
    )

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.4 OutreachMessage

```python
# app/models/outreach_message.py

class OutreachMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        Index("ix_outreach_messages_organization_id", "organization_id"),   # NEW
    )

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.5 EvidenceRecord

```python
# app/models/evidence_record.py

class EvidenceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        Index("ix_evidence_organization_id", "organization_id"),            # NEW
        Index("ix_evidence_org_target", "organization_id", "target_type", "target_id"),  # NEW
        Index("ix_evidence_org_source", "organization_id", "source_type", "source_id"),  # NEW
    )

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.6 AgentRun

```python
# app/models/agent_run.py

class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        Index("ix_agent_runs_organization_id", "organization_id"),          # NEW
        Index("ix_agent_runs_org_agent_status", "organization_id", "agent_name", "status"),  # NEW
    )

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.7 IntelligenceScore

```python
# app/models/intelligence_score.py

class IntelligenceScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        # DROP: Index("ix_intelligence_scores_company_total", "company_id", "total_score")
        # ADD: Index("ix_intelligence_scores_org_company_total", "organization_id", "company_id", "total_score")
        Index("ix_intelligence_scores_organization_id", "organization_id"),  # NEW
    )

    organization_id: Mapped[str] = mapped_column(                          # NEW
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
```

### 2.8 Job

```python
# app/models/job.py

class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __table_args__ = (
        # ... existing constraints ...
        Index("ix_jobs_organization_id", "organization_id"),                # NEW
    )

    organization_id: Mapped[str | None] = mapped_column(                   # NEW (nullable)
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
```

---

## 3. Migration Strategy

### 3.1 Migration File

**Filename:** `database/migrations/versions/20260616_0007_add_organization_id_to_domain_tables.py`

```python
"""Add organization_id to all business entity tables.

Phase 3: Tenant isolation for business entities. Every domain table
gains an organization_id FK column for direct tenant scoping.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Company ──────────────────────────────────────────────────────────
    op.add_column("companies", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_companies_org", "companies", "organizations", ["organization_id"], ["id"])
    op.drop_index("ix_companies_domain")
    op.create_index("ix_companies_organization_id", "companies", ["organization_id"])
    op.create_unique_index("uq_companies_org_domain", "companies", ["organization_id", "domain"])

    # ── Contact ──────────────────────────────────────────────────────────
    op.add_column("contacts", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_contacts_org", "contacts", "organizations", ["organization_id"], ["id"])
    op.drop_index("ix_contacts_email")
    op.create_index("ix_contacts_organization_id", "contacts", ["organization_id"])
    op.create_unique_index("uq_contacts_org_email", "contacts", ["organization_id", "email"])

    # ── IntentSignal ─────────────────────────────────────────────────────
    op.add_column("intent_signals", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_intent_signals_org", "intent_signals", "organizations", ["organization_id"], ["id"])
    op.drop_index("ix_intent_signals_company_id")
    op.drop_index("ix_intent_signals_company_type_observed")
    op.create_index("ix_intent_signals_organization_id", "intent_signals", ["organization_id"])
    op.create_index(
        "ix_intent_signals_org_company_type_observed",
        "intent_signals",
        ["organization_id", "company_id", "signal_type", "observed_at"],
    )

    # ── OutreachMessage ──────────────────────────────────────────────────
    op.add_column("outreach_messages", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_outreach_messages_org", "outreach_messages", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_outreach_messages_organization_id", "outreach_messages", ["organization_id"])
    op.create_index("ix_outreach_messages_org_company", "outreach_messages", ["organization_id", "company_id"])

    # ── EvidenceRecord ───────────────────────────────────────────────────
    op.add_column("evidence_records", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_evidence_records_org", "evidence_records", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_evidence_organization_id", "evidence_records", ["organization_id"])
    op.create_index("ix_evidence_org_target", "evidence_records", ["organization_id", "target_type", "target_id"])
    op.create_index("ix_evidence_org_source", "evidence_records", ["organization_id", "source_type", "source_id"])

    # ── AgentRun ─────────────────────────────────────────────────────────
    op.add_column("agent_runs", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_agent_runs_org", "agent_runs", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_agent_runs_organization_id", "agent_runs", ["organization_id"])
    op.create_index("ix_agent_runs_org_agent_status", "agent_runs", ["organization_id", "agent_name", "status"])

    # ── IntelligenceScore ────────────────────────────────────────────────
    op.add_column("intelligence_scores", sa.Column("organization_id", sa.String(36), nullable=False))
    op.create_foreign_key("fk_intelligence_scores_org", "intelligence_scores", "organizations", ["organization_id"], ["id"])
    op.drop_index("ix_intelligence_scores_company_total")
    op.create_index("ix_intelligence_scores_organization_id", "intelligence_scores", ["organization_id"])
    op.create_index(
        "ix_intelligence_scores_org_company_total",
        "intelligence_scores",
        ["organization_id", "company_id", "total_score"],
    )

    # ── Job ──────────────────────────────────────────────────────────────
    op.add_column("jobs", sa.Column("organization_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_jobs_org", "jobs", "organizations", ["organization_id"], ["id"])
    op.create_index("ix_jobs_organization_id", "jobs", ["organization_id"])


def downgrade() -> None:
    # Reverse order to avoid FK constraint issues
    op.drop_index("ix_jobs_organization_id", "jobs")
    op.drop_constraint("fk_jobs_org", "jobs", type_="foreignkey")
    op.drop_column("jobs", "organization_id")

    op.drop_index("ix_intelligence_scores_organization_id", "intelligence_scores")
    op.drop_index("ix_intelligence_scores_org_company_total", "intelligence_scores")
    op.create_index("ix_intelligence_scores_company_total", "intelligence_scores", ["company_id", "total_score"])
    op.drop_constraint("fk_intelligence_scores_org", "intelligence_scores", type_="foreignkey")
    op.drop_column("intelligence_scores", "organization_id")

    op.drop_index("ix_agent_runs_organization_id", "agent_runs")
    op.drop_index("ix_agent_runs_org_agent_status", "agent_runs")
    op.drop_constraint("fk_agent_runs_org", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "organization_id")

    op.drop_index("ix_evidence_organization_id", "evidence_records")
    op.drop_index("ix_evidence_org_target", "evidence_records")
    op.drop_index("ix_evidence_org_source", "evidence_records")
    op.drop_constraint("fk_evidence_records_org", "evidence_records", type_="foreignkey")
    op.drop_column("evidence_records", "organization_id")

    op.drop_index("ix_outreach_messages_organization_id", "outreach_messages")
    op.drop_index("ix_outreach_messages_org_company", "outreach_messages")
    op.drop_constraint("fk_outreach_messages_org", "outreach_messages", type_="foreignkey")
    op.drop_column("outreach_messages", "organization_id")

    op.drop_index("ix_intent_signals_organization_id", "intent_signals")
    op.drop_index("ix_intent_signals_org_company_type_observed", "intent_signals")
    op.create_index("ix_intent_signals_company_type_observed", "intent_signals", ["company_id", "signal_type", "observed_at"])
    op.create_index("ix_intent_signals_company_id", "intent_signals", ["company_id"])
    op.drop_constraint("fk_intent_signals_org", "intent_signals", type_="foreignkey")
    op.drop_column("intent_signals", "organization_id")

    op.drop_index("ix_contacts_organization_id", "contacts")
    op.drop_unique_constraint("uq_contacts_org_email", "contacts")
    op.create_index("ix_contacts_email", "contacts", ["email"], unique=True)
    op.drop_constraint("fk_contacts_org", "contacts", type_="foreignkey")
    op.drop_column("contacts", "organization_id")

    op.drop_index("ix_companies_organization_id", "companies")
    op.drop_unique_constraint("uq_companies_org_domain", "companies")
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
    op.drop_constraint("fk_companies_org", "companies", type_="foreignkey")
    op.drop_column("companies", "organization_id")
```

### 3.2 Backfill Strategy (Dev Only)

In the development environment, existing test data has no `organization_id`. After the migration runs, seed scripts must be updated to provide `organization_id` for every entity created. Since it's a development-only database, the simplest approach is:

1. Create a default organization per existing user (or use the migration to set a placeholder).
2. OR reset the test database and re-seed with org-scoped data.

**For production:** A data migration step between the column add and the NOT NULL constraint. This is not needed for Phase 3 dev work.

---

## 4. Repository Changes

### 4.1 BaseRepository

```python
# app/repositories/base.py

class BaseRepository(Generic[ModelT]):
    # ... existing methods ...

    def list(
        self,
        *,
        organization_id: str | None = None,    # NEW parameter
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ModelT]:
        statement = select(self.model)
        statement = self._apply_tenant_filter(statement, organization_id)  # NEW
        self._check_tenant_filter(statement, organization_id)             # NEW
        statement = statement.offset(offset).limit(limit)
        return self.session.scalars(statement).all()

    # _apply_tenant_filter and _check_tenant_filter already exist (Phase 2a)
    # They will now be reached because list() calls them.
```

### 4.2 CompanyRepository

```python
# app/repositories/company_repository.py

class CompanyRepository(BaseRepository[Company]):
    model = Company

    def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
        statement = select(Company).where(Company.domain == domain)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)

    def search_by_name(self, name: str, *, organization_id: str, limit: int = 50) -> Sequence[Company]:
        statement = select(Company).where(Company.name.ilike(f"%{name}%"))
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Company]:
        statement = select(Company).where(Company.status == status)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.3 ContactRepository

```python
# app/repositories/contact_repository.py

class ContactRepository(BaseRepository[Contact]):
    model = Contact

    def get_by_email(self, email: str, organization_id: str) -> Contact | None:
        statement = select(Contact).where(Contact.email == email)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)

    def list_by_company(self, company_id: str, *, organization_id: str, limit: int = 100) -> Sequence[Contact]:
        statement = select(Contact).where(Contact.company_id == company_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Contact]:
        statement = select(Contact).where(Contact.status == status)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.4 IntentSignalRepository

```python
# app/repositories/intent_signal_repository.py

class IntentSignalRepository(BaseRepository[IntentSignal]):
    model = IntentSignal

    def list_by_company(self, company_id: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = select(IntentSignal).where(IntentSignal.company_id == company_id).order_by(IntentSignal.observed_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_contact(self, contact_id: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = select(IntentSignal).where(IntentSignal.contact_id == contact_id).order_by(IntentSignal.observed_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_type(self, signal_type: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = select(IntentSignal).where(IntentSignal.signal_type == signal_type).order_by(IntentSignal.observed_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.5 OutreachMessageRepository

```python
# app/repositories/outreach_message_repository.py

class OutreachMessageRepository(BaseRepository[OutreachMessage]):
    model = OutreachMessage

    def list_by_company(self, company_id: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = select(OutreachMessage).where(OutreachMessage.company_id == company_id).order_by(OutreachMessage.generated_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_contact(self, contact_id: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = select(OutreachMessage).where(OutreachMessage.contact_id == contact_id).order_by(OutreachMessage.generated_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = select(OutreachMessage).where(OutreachMessage.status == status)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.6 EvidenceRepository

```python
# app/repositories/evidence_repository.py

class EvidenceRepository(BaseRepository[EvidenceRecord]):
    model = EvidenceRecord

    def list_by_target(self, target_type: str, target_id: str, *, organization_id: str, limit: int = 100, offset: int = 0) -> Sequence[EvidenceRecord]:
        statement = select(EvidenceRecord).where(
            EvidenceRecord.target_type == target_type,
            EvidenceRecord.target_id == target_id,
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.order_by(EvidenceRecord.evidence_type, EvidenceRecord.created_at).offset(offset).limit(limit)
        return self.scalars(statement)

    def list_by_source(self, source_type: str, source_id: str, *, organization_id: str, limit: int = 100, offset: int = 0) -> Sequence[EvidenceRecord]:
        statement = select(EvidenceRecord).where(
            EvidenceRecord.source_type == source_type,
            EvidenceRecord.source_id == source_id,
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.order_by(EvidenceRecord.created_at).offset(offset).limit(limit)
        return self.scalars(statement)

    def list_by_agent_run(self, agent_run_id: str, *, organization_id: str, limit: int = 100, offset: int = 0) -> Sequence[EvidenceRecord]:
        statement = select(EvidenceRecord).where(EvidenceRecord.agent_run_id == agent_run_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.order_by(EvidenceRecord.created_at).offset(offset).limit(limit)
        return self.scalars(statement)

    def list_by_company(self, company_id: str, *, organization_id: str, target_type: str | None = None, limit: int = 100, offset: int = 0) -> Sequence[EvidenceRecord]:
        statement = select(EvidenceRecord).where(EvidenceRecord.company_id == company_id)
        if target_type is not None:
            statement = statement.where(EvidenceRecord.target_type == target_type)
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.order_by(EvidenceRecord.created_at).offset(offset).limit(limit)
        return self.scalars(statement)

    def list_by_entity_type(self, target_type: str, *, organization_id: str, limit: int = 100, offset: int = 0) -> Sequence[EvidenceRecord]:
        statement = select(EvidenceRecord).where(EvidenceRecord.target_type == target_type)
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.order_by(EvidenceRecord.created_at).offset(offset).limit(limit)
        return self.scalars(statement)

    def count_by_target(self, target_type: str, target_id: str, *, organization_id: str) -> int:
        statement = select(func.count()).select_from(EvidenceRecord).where(
            EvidenceRecord.target_type == target_type,
            EvidenceRecord.target_id == target_id,
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.session.scalar(statement) or 0

    def delete_by_target(self, target_type: str, target_id: str, *, organization_id: str) -> int:
        statement = select(EvidenceRecord).where(
            EvidenceRecord.target_type == target_type,
            EvidenceRecord.target_id == target_id,
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        records = self.session.scalars(statement).all()
        count = len(records)
        for r in records:
            self.session.delete(r)
        return count
```

### 4.7 AgentRunRepository

```python
# app/repositories/agent_run_repository.py

class AgentRunRepository(BaseRepository[AgentRun]):
    model = AgentRun

    def list_by_agent(self, agent_name: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        statement = select(AgentRun).where(AgentRun.agent_name == agent_name).order_by(AgentRun.started_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        statement = select(AgentRun).where(AgentRun.status == status).order_by(AgentRun.started_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_workflow(self, workflow_name: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        statement = select(AgentRun).where(AgentRun.workflow_name == workflow_name).order_by(AgentRun.started_at.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.8 IntelligenceScoreRepository

```python
# app/repositories/intelligence_score_repository.py

class IntelligenceScoreRepository(BaseRepository[IntelligenceScore]):
    model = IntelligenceScore

    def latest_for_company(self, company_id: str, *, organization_id: str) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.order_by(IntelligenceScore.scored_at.desc()).limit(1)).one_or_none()

    def latest_for_contact(self, contact_id: str, *, organization_id: str) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.contact_id == contact_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.order_by(IntelligenceScore.scored_at.desc()).limit(1)).one_or_none()

    def latest_for_target(self, *, company_id: str, organization_id: str, contact_id: str | None = None) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        if contact_id is None:
            statement = statement.where(IntelligenceScore.contact_id.is_(None))
        else:
            statement = statement.where(IntelligenceScore.contact_id == contact_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.order_by(IntelligenceScore.scored_at.desc()).limit(1)).one_or_none()

    def list_top_scores(self, *, organization_id: str | None = None, limit: int = 100) -> Sequence[IntelligenceScore]:
        """Org-scoped by default. Pass organization_id=None to get global top scores."""
        statement = select(IntelligenceScore).order_by(IntelligenceScore.total_score.desc())
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
```

### 4.9 JobRepository

```python
# app/repositories/job_repository.py

class JobRepository(BaseRepository[Job]):
    model = Job

    def get_pending_jobs(self, *, limit: int = 10) -> Sequence[Job]:
        """UNSCOPED — system worker polls across all organizations."""
        statement = select(Job).where(
            Job.status == "pending",
            Job.scheduled_at <= datetime.now(timezone.utc),
        ).order_by(Job.scheduled_at.asc()).limit(limit)
        return self.scalars(statement)

    def get_job_by_agent_run_id(self, agent_run_id: str, *, organization_id: str | None = None) -> Job | None:
        statement = select(Job).where(Job.agent_run_id == agent_run_id)
        if organization_id is not None:
            statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)
```

---

## 5. Service Changes

### 5.1 BaseService

```python
# app/services/base.py

class BaseService(Generic[ModelT, RepositoryT]):
    def create(self, organization_id: str, **values: Any) -> ModelT:     # organization_id added
        # ... existing logic, passes org_id through ...

    def list(self, *, organization_id: str | None = None, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        # ... passes organization_id to repository.list() ...
        def operation(session: Session) -> Sequence[ModelT]:
            return self._repository(session).list(organization_id=organization_id, limit=limit, offset=offset)
        return self._run_in_transaction("list", operation)
```

### 5.2 Pattern: Entity-Specific Service

```python
# app/services/company_service.py — representative pattern

class CompanyService(BaseService[Company, CompanyRepository]):
    def create(self, organization_id: str, **values: Any) -> Company:
        # require_role("member", role, "create companies")  # called by endpoint layer
        return super().create(organization_id=organization_id, **values)

    def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
        self._validate_identifier(domain, field_name="domain")
        def operation(session: Session) -> Company | None:
            return self._repository(session).get_by_domain(domain, organization_id=organization_id)
        return self._run_in_transaction("get_by_domain", operation)

    def search_by_name(self, name: str, *, organization_id: str, limit: int = 50) -> Sequence[Company]:
        self._validate_identifier(name, field_name="name")
        self._validate_limit(limit)
        def operation(session: Session) -> Sequence[Company]:
            return self._repository(session).search_by_name(name, organization_id=organization_id, limit=limit)
        return self._run_in_transaction("search_by_name", operation)

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Company]:
        self._validate_identifier(status, field_name="status")
        self._validate_limit(limit)
        def operation(session: Session) -> Sequence[Company]:
            return self._repository(session).list_by_status(status, organization_id=organization_id, limit=limit)
        return self._run_in_transaction("list_by_status", operation)

    def _before_create(self, repository: CompanyRepository, values: dict) -> None:
        domain = values.get("domain", "")
        org_id = values.get("organization_id", "")
        if domain:
            existing = repository.get_by_domain(domain, organization_id=org_id)
            if existing is not None:
                raise EntityConflictError("A company with this domain already exists in this organization.")
```

### 5.3 All Service Signatures (by entity)

| Service | Method | New Signature |
|---|---|---|
| `CompanyService` | `create` | `(self, organization_id: str, **values) -> Company` |
| | `get_by_domain` | `(self, domain: str, organization_id: str) -> Company \| None` |
| | `search_by_name` | `(self, name: str, *, organization_id: str, limit=50) -> Sequence[Company]` |
| | `list_by_status` | `(self, status: str, *, organization_id: str, limit=100) -> Sequence[Company]` |
| `ContactService` | `create` | `(self, organization_id: str, **values) -> Contact` |
| | `get_by_email` | `(self, email: str, organization_id: str) -> Contact \| None` |
| | `list_by_company` | `(self, company_id: str, *, organization_id: str, limit=100) -> Sequence[Contact]` |
| | `list_by_status` | `(self, status: str, *, organization_id: str, limit=100) -> Sequence[Contact]` |
| `IntentSignalService` | `create` | `(self, organization_id: str, **values) -> IntentSignal` |
| | `list_by_company` | `(self, company_id: str, *, organization_id: str, limit=100) -> Sequence[IntentSignal]` |
| | `list_by_contact` | `(self, contact_id: str, *, organization_id: str, limit=100) -> Sequence[IntentSignal]` |
| | `list_by_type` | `(self, signal_type: str, *, organization_id: str, limit=100) -> Sequence[IntentSignal]` |
| `OutreachMessageService` | `create` | `(self, organization_id: str, **values) -> OutreachMessage` |
| | `list_by_company` | `(self, company_id: str, *, organization_id: str, limit=100) -> Sequence[OutreachMessage]` |
| | `list_by_contact` | `(self, contact_id: str, *, organization_id: str, limit=100) -> Sequence[OutreachMessage]` |
| | `list_by_status` | `(self, status: str, *, organization_id: str, limit=100) -> Sequence[OutreachMessage]` |
| `EvidenceService` | `record_evidence` | `(self, *, organization_id: str, ...) -> EvidenceRecord` |
| | `record_evidence_batch` | `(self, items, *, organization_id: str, ...) -> list[EvidenceRecord]` |
| | `get_target_evidence` | `(self, target_type, target_id, *, organization_id: str, ...)` |
| | `get_source_targets` | `(self, source_type, source_id, *, organization_id: str, ...)` |
| | `get_company_evidence` | `(self, company_id, *, organization_id: str, ...)` |
| | `get_agent_run_evidence` | `(self, agent_run_id, *, organization_id: str, ...)` |
| | `get_evidence_summary` | `(self, target_type, target_id, *, organization_id: str) -> EvidenceSummary` |
| | `delete_target_evidence` | `(self, target_type, target_id, *, organization_id: str) -> int` |
| `AgentRunService` | `create` | `(self, organization_id: str, **values) -> AgentRun` |
| | `start_workflow_run` | `(self, *, organization_id: str, agent_name, workflow_name, ...)` |
| | `list_by_agent` | `(self, agent_name, *, organization_id: str, limit=100)` |
| | `list_by_status` | `(self, status, *, organization_id: str, limit=100)` |
| | `list_by_workflow` | `(self, workflow_name, *, organization_id: str, limit=100)` |
| `IntelligenceScoreService` | `create` | `(self, organization_id: str, **values)` |
| | `latest_for_company` | `(self, company_id, *, organization_id: str)` |
| | `latest_for_contact` | `(self, contact_id, *, organization_id: str)` |
| | `latest_for_target` | `(self, *, company_id, organization_id: str, contact_id=None)` |
| | `list_top_scores` | `(self, *, organization_id: str \| None = None, limit=100) -> Sequence[IntelligenceScore]` |
| `JobService` | `schedule_agent` | `(self, name, context: AgentContext, ...) -> Job` — context now carries `organization_id` |
| | `schedule_workflow` | `(self, name, context: WorkflowContext, ...) -> Job` — context now carries `organization_id` |
| | `list_jobs` | `(self, *, organization_id: str, ...)` |
| | `cancel_job` | `(self, job_id, *, organization_id: str)` |
| | `get_next_jobs` | **UNSCOPED** — `(self, *, limit=10) -> Sequence[Job]` |

---

## 6. Schema Changes

Every `*Create` schema gains a `organization_id` field that is **injected by the endpoint layer** (not user input). Every `*Read` schema gains an `organization_id: str` field.

### 6.1 Pattern

```python
# CompanyCreate — organization_id is NOT a user field
class CompanyCreate(IrtiqaSchema):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    # ... no organization_id here — injected by endpoint

# CompanyRead — organization_id IS in the response
class CompanyRead(TimestampedReadSchema):
    # ... existing fields ...
    organization_id: str  # NEW
```

**Per-entity schema fields:**

| Entity | Create Schema | Read Schema |
|---|---|---|
| Company | No org_id field | `organization_id: str` |
| Contact | No org_id field | `organization_id: str` |
| IntentSignal | No org_id field | `organization_id: str` |
| OutreachMessage | No org_id field | `organization_id: str` |
| EvidenceRecord | No org_id field | `organization_id: str` |
| AgentRun | No org_id field | `organization_id: str` |
| IntelligenceScore | No org_id field | `organization_id: str` |
| Job | No org_id field | `organization_id: str \| None` |

---

## 7. Endpoint Changes

### 7.1 Pattern

Every endpoint in every entity router gains:

```python
from app.api.dependencies import get_current_organization
from app.core.tenant import TenantContext, require_role

@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    tenant: TenantContext = Depends(get_current_organization),   # NEW
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    require_role("member", tenant.role, "create companies")
    company = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return CompanyRead.model_validate(company)


@router.get("", response_model=CompanyList)
def list_companies(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),   # NEW
    service: CompanyService = Depends(get_company_service),
) -> CompanyList:
    companies = service.list(organization_id=tenant.organization_id, limit=limit, offset=offset)
    return CompanyList(
        items=[CompanyRead.model_validate(c) for c in companies],
        total=len(companies),
        limit=limit,
        offset=offset,
    )


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: str,
    tenant: TenantContext = Depends(get_current_organization),   # NEW
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.get_required(company_id)
    # Verify ownership: 403 if not in caller's org
    if company.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return CompanyRead.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    tenant: TenantContext = Depends(get_current_organization),   # NEW
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    require_role("member", tenant.role, "update companies")
    company = service.get_required(company_id)
    if company.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    company = service.update(company_id, **payload.model_dump(exclude_unset=True))
    return CompanyRead.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: str,
    tenant: TenantContext = Depends(get_current_organization),   # NEW
    service: CompanyService = Depends(get_company_service),
) -> Response:
    require_role("admin", tenant.role, "delete companies")
    company = service.get_required(company_id)
    if company.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    service.delete(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

### 7.2 Intelligence-Score-Specific: Top Scores

```python
@router.get("/intelligence-scores/top", response_model=IntelligenceScoreList)
def list_top_scores(
    limit: int = Query(default=100, ge=1, le=500),
    global_scores: bool = Query(default=False, alias="global"),
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreList:
    org_id: str | None = None
    if global_scores:
        require_role("owner", tenant.role, "view global scores")
    else:
        org_id = tenant.organization_id
    scores = service.list_top_scores(organization_id=org_id, limit=limit)
    return IntelligenceScoreList(
        items=[IntelligenceScoreRead.model_validate(s) for s in scores],
        total=len(scores),
        limit=limit,
        offset=0,
    )
```

### 7.3 Entities Requiring Changes

All 8 entities' endpoint files must be updated:

| Endpoint File | Current Auth | Phase 3 Auth |
|---|---|---|
| `companies.py` | None | `get_current_organization()` |
| `contacts.py` | None | `get_current_organization()` |
| `intent_signals.py` | None | `get_current_organization()` |
| `outreach_messages.py` | None | `get_current_organization()` |
| `evidence.py` | None | `get_current_organization()` |
| `agent_runs.py` | None | `get_current_organization()` |
| `intelligence.py` | None | `get_current_organization()` |
| `jobs.py` | None | `get_current_organization()` |

---

## 8. Context Object Changes

### 8.1 AgentContext

```python
# app/agents/context.py

class AgentContext(IrtiqaSchema):
    agent_name: str = Field(min_length=1, max_length=150)
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    organization_id: str = Field(min_length=36, max_length=36)  # NEW — required
    workflow_name: str | None = Field(default=None, min_length=1, max_length=150)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=100)
    options: MappingProxyType[str, Any] = Field(default_factory=lambda: MappingProxyType({}))
```

### 8.2 WorkflowContext

```python
# app/workflows/context.py

class WorkflowContext(IrtiqaSchema):
    workflow_name: str = Field(min_length=1, max_length=150)
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    organization_id: str | None = Field(default=None, min_length=36, max_length=36)  # NEW
    correlation_id: str | None = Field(default=None, min_length=1, max_length=100)
    requested_by: str | None = Field(default=None, min_length=1, max_length=150)
    options: MappingProxyType[str, Any] = Field(default_factory=lambda: MappingProxyType({}))
```

### 8.3 JobService Schedule Methods

```python
# app/services/job_service.py

def schedule_agent(self, name: str, context: AgentContext, ...) -> Job:
    # context.organization_id is now available
    payload = json.dumps({
        "company_id": context.company_id,
        "contact_id": context.contact_id,
        "organization_id": context.organization_id,  # NEW — stored in payload
        "workflow_name": context.workflow_name,
        "correlation_id": context.correlation_id,
        "options": dict(context.options),
    })
    # ... rest unchanged
```

---

## 9. Test Plan

### 9.1 Test Fixtures

```python
# tests/conftest.py — NEW fixtures

@pytest.fixture()
def organization(session: Session) -> Organization:
    """Create a default test organization."""
    from app.models.organization import Organization
    org = Organization(
        name="Test Organization",
        slug="test-org",
        status="active",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(org)
    session.flush()
    return org


@pytest.fixture()
def different_organization(session: Session) -> Organization:
    """A second organization for cross-tenant tests."""
    from app.models.organization import Organization
    org = Organization(
        name="Other Organization",
        slug="other-org",
        status="active",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(org)
    session.flush()
    return org


@pytest.fixture()
def tenant_context(organization: Organization, user: User) -> TenantContext:
    """A TenantContext for the default user+org (owner role)."""
    return TenantContext(
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
        is_api_key=False,
    )


@pytest.fixture()
def override_get_current_organization(app, tenant_context):
    """Override the dependency so all endpoints use the test TenantContext."""
    from app.api.dependencies import get_current_organization
    app.dependency_overrides[get_current_organization] = lambda: tenant_context
    yield
    app.dependency_overrides.pop(get_current_organization, None)
```

### 9.2 Test Cases by Category

**Cross-tenant isolation (16 tests — 2 per entity):**
- Entity created in Org A is visible when queried in Org A
- Entity created in Org A returns 403 when accessed from Org B

**Repository tenant filter (24 tests — 3 per entity repository):**
- Custom method applies `_apply_tenant_filter`
- Filter with correct org_id returns matching entity
- Filter with wrong org_id returns None/empty

**Service scoping (24 tests — 3 per entity service):**
- `list_by_*` with org_id returns only that org's entities
- `create` with org_id stores correct value
- `*_for_target` with wrong org_id returns None

**API auth (8 tests — 1 per entity router):**
- Endpoint without valid JWT returns 401
- Endpoint without org claim returns 403
- Endpoint with valid org returns 200

**Unique constraint (4 tests):**
- Same domain in two different orgs — OK
- Same domain in same org — 409
- Same email in two different orgs — OK
- Same email in same org — 409

**Job isolation (6 tests):**
- User-facing `list_jobs` returns only caller's org jobs
- `get_next_jobs` returns jobs from all orgs
- `claim_job` works cross-org

**Score ranking (4 tests):**
- Default `list_top_scores` returns only caller's org
- `?global=true` returns cross-org but requires owner role
- Member role gets 403 for `?global=true`

**Estimated total: ~86 new tests**

---

## 10. Rollback Strategy

| Scenario | Rollback Action |
|---|---|
| **Migration failure** (column add fails) | `alembic downgrade -1` — drops all 8 columns, restores old indexes |
| **Repository bug** (wrong org_id filter) | Revert the repository file; `BaseRepository.list()` falls back to unscoped behavior |
| **Service bug** (org_id not passed through) | Revert the service file; callers pass `organization_id=""` which `_apply_tenant_filter` treats as unscoped (skips filter) |
| **Endpoint bug** (wrong dependency) | Revert the endpoint file; endpoints lose tenant check but keep working unscoped |
| **Test failure cascade** | Temporarily revert `dependency_overrides` in conftest to stabilize CRUD phase tests |
| **Full rollback** | `git revert <merge-commit>` — returns to Phase 2 state |

---

## 11. Commit-by-Commit Execution Plan

### Commit 1: Models + Migration

```text
Files:
  M  app/models/company.py              (+5 lines: organization_id column)
  M  app/models/contact.py              (+5 lines)
  M  app/models/intent_signal.py        (+5 lines)
  M  app/models/outreach_message.py     (+5 lines)
  M  app/models/evidence_record.py      (+5 lines)
  M  app/models/agent_run.py            (+5 lines)
  M  app/models/intelligence_score.py   (+5 lines)
  M  app/models/job.py                  (+5 lines)
  A  database/migrations/versions/...0007...py  (+200 lines)

Verification:
  python -m compileall app/models/
  python -m pytest tests/unit/test_models.py
  python -m alembic upgrade head
  python -m alembic downgrade -1
  python -m alembic upgrade head

Risk: Low — additive-only changes; no logic modified.
```

### Commit 2: Repository Tenant Filtering

```text
Files:
  M  app/repositories/base.py                    (+5 lines: wire _apply_tenant_filter in list())
  M  app/repositories/company_repository.py      (+5 lines per method × 3 methods)
  M  app/repositories/contact_repository.py      (+5 lines per method × 3 methods)
  M  app/repositories/intent_signal_repository.py   (+5 lines per method × 3 methods)
  M  app/repositories/outreach_message_repository.py (+5 lines per method × 3 methods)
  M  app/repositories/evidence_repository.py     (+5 lines per method × 7 methods)
  M  app/repositories/agent_run_repository.py    (+5 lines per method × 3 methods)
  M  app/repositories/intelligence_score_repository.py (+5 lines per method × 4 methods)
  M  app/repositories/job_repository.py          (+5 lines per method)

Verification:
  python -m compileall app/repositories/
  python -m pytest tests/unit/test_repository_tenant_filter.py

Risk: Medium — changing BaseRepository.list() signature breaks any subclasses
      that override list() without the new parameter. Audit for overrides first.
```

### Commit 3: Service Scoping

```text
Files:
  M  app/services/base.py                          (+organization_id to create and list)
  M  app/services/company_service.py               (+org_id to 4 methods)
  M  app/services/contact_service.py               (+org_id to 4 methods)
  M  app/services/intent_signal_service.py         (+org_id to 4 methods)
  M  app/services/outreach_message_service.py      (+org_id to 4 methods)
  M  app/services/evidence_service.py              (+org_id to 8 methods)
  M  app/services/agent_run_service.py             (+org_id to 5 methods)
  M  app/services/intelligence_score_service.py    (+org_id to 5 methods)
  M  app/services/job_service.py                   (+org_id to list_jobs, cancel_job; extract from context)
  M  app/agents/context.py                         (+organization_id to AgentContext)
  M  app/workflows/context.py                      (+organization_id to WorkflowContext)

Verification:
  python -m compileall app/services/ app/agents/ app/workflows/
  python -m pytest tests/unit/

Risk: High — every service method signature changes. All callers must be updated
      in the same commit or the code won't compile.
```

### Commit 4: Endpoints + Schemas

```text
Files:
  M  app/api/v1/endpoints/companies.py             (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/contacts.py              (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/intent_signals.py        (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/outreach_messages.py     (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/evidence.py              (+get_current_organization to 6 routes)
  M  app/api/v1/endpoints/agent_runs.py            (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/intelligence.py          (+get_current_organization to 5 routes)
  M  app/api/v1/endpoints/jobs.py                  (+get_current_organization to 2 routes)
  M  app/schemas/company.py                        (+organization_id to *Read schemas)
  M  app/schemas/contact.py                        (+organization_id to *Read schemas)
  M  app/schemas/intent_signal.py                  (+organization_id to *Read schemas)
  M  app/schemas/outreach_message.py               (+organization_id to *Read schemas)
  M  app/schemas/evidence.py                       (+organization_id to EvidenceRead)
  M  app/schemas/agent_run.py                      (+organization_id to AgentRunRead)
  M  app/schemas/intelligence_score.py             (+organization_id to *Read schemas)
  M  app/schemas/job.py                            (+organization_id to JobRead)

Verification:
  python -m compileall app/api/ app/schemas/
  python -c "from app.main import create_app; create_app(configure_logging_on_startup=False)"
  python -m pytest tests/integration/api/ -x -v --tb=short

Risk: High — all existing integration tests will fail because they don't inject
      TenantContext. Must use dependency_overrides or skip existing tests temporarily.
```

### Commit 5: Test Fixtures + Full Test Suite

```text
Files:
  M  tests/conftest.py                             (+organization, different_organization, tenant_context fixtures)
  M  tests/integration/api/conftest.py             (+override_get_current_organization fixture)
  M  tests/integration/api/test_crud_phase_1.py    (+use org-scoped fixtures)
  M  tests/integration/api/test_crud_phase_2.py    (+use org-scoped fixtures)
  M  tests/integration/api/test_crud_phase_3.py    (+use org-scoped fixtures)
  M  tests/unit/test_repository_tenant_filter.py   (+tests for all 8 entity repositories)
  A  tests/unit/test_tenant_isolation.py           (+cross-tenant access tests)
  A  tests/integration/api/test_tenant_isolation.py (+cross-tenant API tests)

Verification:
  python -m pytest tests/ -v --tb=short
  # Expected: all tests pass (existing + new)

Risk: Medium — ensuring all existing tests work with org scoping requires
      careful fixture setup. Some tests may need seed data updates.
```

---

## 12. Dependency Graph

```text
Commit 1: Models + Migration ───────────────── (no deps)
                    │
                    ▼
Commit 2: Repository Filters ─────────── (needs models with org_id)
                    │
                    ▼
Commit 3: Service Scoping ────────────── (needs repositories gated)
                    │
                    ▼
Commit 4: Endpoints + Schemas ────────── (needs services gated)
                    │
                    ▼
Commit 5: Test Fixtures + Full Suite ─── (needs all of the above)
```

---

## 13. Risk Register

| # | Risk | P | I | R | Mitigation | Owner |
|---|---|---|---|---|---|---|
| 1 | `BaseRepository.list()` breaks subclasses without org_id | M | H | H | Audit all override() methods before changing; add compatibility shim | C2 |
| 2 | EvidenceRecord polymorphic queries skip org filter | L | H | M | Each `list_by_*` method explicitly wires `_apply_tenant_filter` | C2 |
| 3 | Existing tests fail because they don't inject TenantContext | H | M | H | Use `dependency_overrides` in conftest; document in PR description | C4-C5 |
| 4 | `AgentContext` callers don't provide org_id | M | H | H | Make org_id required field; fix all callers in C3 commit | C3 |
| 5 | Migration fails on NOT NULL without backfill | H | M | M | In dev: refresh database; in prod: two-step (ADD NULL → backfill → NOT NULL) | C1 |
| 6 | `list_top_scores` regression exposes all orgs | L | H | M | Default-scope to org; integration test verifies scoping | C4 |
| 7 | Job runner hangs if `get_next_jobs` becomes scoped | L | H | M | `get_next_jobs()` explicitly unscoped with inline comment | C2-C3 |
| 8 | Concurrent claim of job by two workers | L | L | L | Already handled by `claim_job` atomic UPDATE with status check | Phase 1 |

**P=Probability, I=Impact, R=Risk (P×I)**

---

## 14. Summary

| Metric | Value |
|---|---|
| Models modified | 8 |
| Migration version | 0007 (adds 8 columns, 8 FK constraints, 14 indexes) |
| Repository files modified | 9 |
| Service files modified | 9 |
| Endpoint files modified | 8 |
| Schema files modified | 8 |
| Context files modified | 2 |
| Test files created/modified | ~10 |
| **Total estimated files** | **~45** |
| **Estimated new tests** | **~86** |
| **Implementation commits** | **5** |
| **Rollback safety** | Full (each commit revertable) |
| **Data migration for dev** | None (reset database, re-seed) |
