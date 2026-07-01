# Entity Relationships

Complete entity relationship documentation for all 19 tables in Irtiqa Intelligence.

> **Note:** For detailed table schemas, see [Database Design](database.md).

---

## Complete Entity Relationship Diagram

```mermaid
erDiagram
    %% Multi-Tenancy Foundation
    organizations ||--o{ memberships : "has members"
    users ||--o{ memberships : "belongs to orgs"
    
    %% Domain Entities (Tenant-Scoped)
    organizations ||--o{ companies : "owns"
    organizations ||--o{ contacts : "owns"
    organizations ||--o{ technologies : "owns"
    organizations ||--o{ intent_signals : "owns"
    organizations ||--o{ intelligence_scores : "owns"
    organizations ||--o{ outreach_messages : "owns"
    organizations ||--o{ evidence_records : "owns"
    organizations ||--o{ agent_runs : "owns"
    organizations ||--o{ jobs : "owns"
    organizations ||--o{ discovery_searches : "owns"
    organizations ||--o{ discovery_runs : "owns"
    
    %% Core Intelligence Relationships
    companies ||--o{ contacts : "employs"
    companies ||--o{ websites : "has"
    companies ||--o{ technologies : "uses"
    companies ||--o{ intent_signals : "emits"
    companies ||--o{ intelligence_scores : "receives"
    companies ||--o{ outreach_messages : "targeted by"
    companies ||--o{ agent_runs : "analyzed by"
    companies ||--o{ evidence_records : "evidenced by"
    
    contacts ||--o{ intent_signals : "shows"
    contacts ||--o{ intelligence_scores : "receives"
    contacts ||--o{ outreach_messages : "receives"
    contacts ||--o{ agent_runs : "analyzed by"
    
    websites ||--o{ technologies : "reveals"
    websites ||--o{ intent_signals : "supports"
    
    technologies ||--o{ intent_signals : "influences"
    technologies ||--o{ intelligence_scores : "contributes to"
    
    %% Agent Observability
    agent_runs ||--o{ technologies : "detects"
    agent_runs ||--o{ intent_signals : "finds"
    agent_runs ||--o{ intelligence_scores : "computes"
    agent_runs ||--o{ outreach_messages : "generates"
    agent_runs ||--o{ evidence_records : "produces"
    
    %% Intelligence Score → Outreach Message
    intelligence_scores ||--o{ outreach_messages : "drives personalization"
    
    %% Background Jobs
    jobs ||--o{ agent_runs : "executes"
    
    %% Authentication
    users ||--o{ refresh_tokens : "has"
    users ||--o{ email_verification_tokens : "has"
    users ||--o{ password_reset_tokens : "has"
    users ||--o{ failed_login_attempts : "tracked by"
    
    %% Discovery Engine
    discovery_searches ||--o{ discovery_runs : "executed as"
    discovery_searches ||--o{ companies : "discovers"
    
    %% Table Definitions (Key Fields Only)
    companies {
        uuid id PK
        uuid organization_id FK
        string domain UK
        string name
        string industry
        string status
        string discovered_via
        uuid discovery_search_id FK
        float discovery_score
    }
    
    contacts {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        string email UK
        string full_name
        string title
    }
    
    websites {
        uuid id PK
        uuid company_id FK
        string normalized_url
        text raw_html
        text extracted_text
        int http_status
    }
    
    technologies {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        uuid website_id FK
        uuid agent_run_id FK
        string name
        string category
        float confidence
    }
    
    intent_signals {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        uuid contact_id FK
        uuid website_id FK
        uuid technology_id FK
        uuid agent_run_id FK
        string signal_type
        float strength
        float confidence
    }
    
    intelligence_scores {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        uuid contact_id FK
        uuid technology_id FK
        uuid agent_run_id FK
        float fit_score
        float intent_score
        float technographic_score
        float engagement_score
        float total_score
    }
    
    outreach_messages {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        uuid contact_id FK
        uuid intelligence_score_id FK
        uuid agent_run_id FK
        string channel
        string variant
        text message_body
    }
    
    evidence_records {
        uuid id PK
        uuid organization_id FK
        uuid agent_run_id FK
        string source_type
        string source_id
        string evidence_type
        text evidence_value
        string target_type
        string target_id
        float confidence
    }
    
    agent_runs {
        uuid id PK
        uuid organization_id FK
        uuid company_id FK
        uuid contact_id FK
        uuid job_id FK
        string agent_name
        string workflow_name
        string status
    }
    
    jobs {
        uuid id PK
        uuid organization_id FK
        uuid agent_run_id FK
        string job_type
        string target_name
        string status
        int retry_count
        int max_retries
    }
    
    organizations {
        uuid id PK
        string name
        string slug UK
    }
    
    memberships {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        string role
    }
    
    users {
        uuid id PK
        string email UK
        string password_hash
        boolean is_verified
    }
    
    discovery_searches {
        uuid id PK
        uuid organization_id FK
        string name
        text criteria
        string status
        int total_discovered
    }
    
    discovery_runs {
        uuid id PK
        uuid organization_id FK
        uuid search_id FK
        string status
        int companies_found
        int companies_created
        int companies_skipped
    }
```

---

## Table Categories

### Core Intelligence Tables

| Table | Purpose | Owned By |
|-------|---------|----------|
| `companies` | Canonical company accounts. Primary lookup by domain. | Organization (tenant-scoped) |
| `contacts` | People associated with companies. | Organization (tenant-scoped) |
| `websites` | Company-related URLs discovered during enrichment. | Company |
| `technologies` | Company-specific detected technology usage. | Organization + Company |
| `intent_signals` | Buying intent, technology change, growth, partnership signals. | Organization + Company |
| `intelligence_scores` | Versioned score records for companies. Append-only. | Organization + Company |
| `outreach_messages` | Outreach message drafts and personalization outputs. | Organization + Company |
| `evidence_records` | Provenance links between intelligence outputs and source evidence. | Organization + Agent Run |

### System Tables

| Table | Purpose | Owned By |
|-------|---------|----------|
| `agent_runs` | Execution history for agents and workflows. | Organization |
| `jobs` | Scheduled background jobs for agent and workflow execution. | Organization |

### Discovery Engine Tables

| Table | Purpose | Owned By |
|-------|---------|----------|
| `discovery_searches` | Saved ICP search criteria for recurring or one-shot discovery. | Organization |
| `discovery_runs` | Execution history for discovery searches. | Organization + Search |

### Auth & Multi-Tenancy Tables

| Table | Purpose | Owned By |
|-------|---------|----------|
| `users` | User accounts with email, password hash, display name. | Global (not tenant-scoped) |
| `organizations` | Tenant organizations. | Global |
| `memberships` | User-organization associations with roles (owner, admin, member, viewer). | Organization + User |
| `refresh_tokens` | Hashed refresh tokens for JWT renewal. | User |
| `email_verification_tokens` | Email verification tokens. | User |
| `password_reset_tokens` | Password reset tokens. | User |
| `failed_login_attempts` | Rate limiting records. | User |

---

## Foreign Key Cascade Strategy

```mermaid
graph TD
    Org[organizations] -->|CASCADE| Companies[companies]
    Org -->|CASCADE| Contacts[contacts]
    Org -->|CASCADE| Technologies[technologies]
    Org -->|CASCADE| IntentSignals[intent_signals]
    Org -->|CASCADE| Scores[intelligence_scores]
    Org -->|CASCADE| Messages[outreach_messages]
    Org -->|CASCADE| Evidence[evidence_records]
    Org -->|CASCADE| AgentRuns[agent_runs]
    Org -->|CASCADE| Jobs[jobs]
    Org -->|CASCADE| Searches[discovery_searches]
    Org -->|CASCADE| Runs[discovery_runs]
    Org -->|CASCADE| Memberships[memberships]
    
    Companies -->|CASCADE| CompanyContacts[contacts]
    Companies -->|CASCADE| Websites[websites]
    Companies -->|CASCADE| CompanyTech[technologies]
    Companies -->|CASCADE| CompanySignals[intent_signals]
    Companies -->|CASCADE| CompanyScores[intelligence_scores]
    Companies -->|CASCADE| CompanyMessages[outreach_messages]
    
    Contacts -.->|SET NULL| ContactSignals[intent_signals.contact_id]
    Contacts -.->|SET NULL| ContactScores[intelligence_scores.contact_id]
    Contacts -.->|SET NULL| ContactMessages[outreach_messages.contact_id]
    
    AgentRuns -->|CASCADE| RunTech[technologies.agent_run_id]
    AgentRuns -->|CASCADE| RunSignals[intent_signals.agent_run_id]
    AgentRuns -.->|SET NULL| RunJobs[jobs.agent_run_id]
    
    Users -->|CASCADE| UserTokens[refresh_tokens]
    Users -->|CASCADE| UserVerification[email_verification_tokens]
    Users -->|CASCADE| UserReset[password_reset_tokens]
    Users -->|CASCADE| UserAttempts[failed_login_attempts]
    
    Searches -->|CASCADE| SearchRuns[discovery_runs]
    Searches -.->|SET NULL| SearchCompanies[companies.discovery_search_id]
    
    style Org fill:#e1f5ff
    style Companies fill:#fff4e1
    style Contacts fill:#f0e1ff
    style Users fill:#ffe1e1
    
    linkStyle 11,12,13 stroke:#ff6b6b,stroke-width:2px,stroke-dasharray: 5 5
    linkStyle 16 stroke:#ff6b6b,stroke-width:2px,stroke-dasharray: 5 5
    linkStyle 21 stroke:#ff6b6b,stroke-width:2px,stroke-dasharray: 5 5
```

**Legend:**
- **Solid arrows (→):** CASCADE delete — child records are deleted when parent is deleted
- **Dashed arrows (-.->):** SET NULL — child foreign key is set to NULL when parent is deleted

### CASCADE Deletes (Child Owned by Parent)

When the parent is deleted, all children are automatically deleted.

| Parent | Child | Column | Rationale |
|--------|-------|--------|-----------|
| `organizations` | `companies` | `organization_id` | Company belongs to organization |
| `organizations` | `contacts` | `organization_id` | Contact belongs to organization |
| `organizations` | `intent_signals` | `organization_id` | Signal belongs to organization |
| `organizations` | `intelligence_scores` | `organization_id` | Score belongs to organization |
| `organizations` | `outreach_messages` | `organization_id` | Message belongs to organization |
| `organizations` | `evidence_records` | `organization_id` | Evidence belongs to organization |
| `organizations` | `agent_runs` | `organization_id` | Agent run belongs to organization |
| `organizations` | `jobs` | `organization_id` | Job belongs to organization |
| `organizations` | `memberships` | `organization_id` | Membership belongs to organization |
| `organizations` | `discovery_searches` | `organization_id` | Search belongs to organization |
| `organizations` | `discovery_runs` | `organization_id` | Run belongs to organization |
| `companies` | `contacts` | `company_id` | Contact belongs to company |
| `companies` | `technologies` | `company_id` | Technology belongs to company |
| `companies` | `intent_signals` | `company_id` | Signal belongs to company |
| `companies` | `intelligence_scores` | `company_id` | Score belongs to company |
| `companies` | `outreach_messages` | `company_id` | Message belongs to company |
| `companies` | `websites` | `company_id` | Website belongs to company |
| `websites` | `technologies` | `website_id` | Technology detected on website |
| `agent_runs` | `technologies` | `agent_run_id` | Agent run produced technology |
| `agent_runs` | `intent_signals` | `agent_run_id` | Agent run produced signal |
| `users` | `refresh_tokens` | `user_id` | Token belongs to user |
| `users` | `email_verification_tokens` | `user_id` | Verification belongs to user |
| `users` | `password_reset_tokens` | `user_id` | Reset token belongs to user |
| `users` | `failed_login_attempts` | `user_id` | Attempt belongs to user |
| `discovery_searches` | `discovery_runs` | `search_id` | Run belongs to search |

### SET NULL on Delete (Child Survives Parent)

When the parent is deleted, the child's foreign key is set to NULL but the child record survives.

| Parent | Child | Column | Rationale |
|--------|-------|--------|-----------|
| `contacts` | `intent_signals` | `contact_id` | Signal may exist without specific contact attribution |
| `contacts` | `intelligence_scores` | `contact_id` | Score applies to company even if contact deleted |
| `contacts` | `outreach_messages` | `contact_id` | Message template survives contact deletion |
| `websites` | `intent_signals` | `website_id` | Signal may exist without specific website |
| `technologies` | `intent_signals` | `technology_id` | Signal may exist without technology link |
| `technologies` | `intelligence_scores` | `technology_id` | Score applies to company even if tech removed |
| `intelligence_scores` | `outreach_messages` | `intelligence_score_id` | Message template survives score recalculation |
| `agent_runs` | `jobs` | `agent_run_id` | Job record survives agent run cleanup |
| `discovery_searches` | `companies` | `discovery_search_id` | Company survives search deletion (provenance preserved) |

---

## Unique Constraints

Prevent duplicate data within tenant boundaries.

| Table | Columns | Description | Enforcement |
|-------|---------|-------------|-------------|
| `companies` | `(organization_id, domain)` | One domain per organization | Database UNIQUE constraint |
| `contacts` | `(organization_id, email)` | One email per organization | Database UNIQUE constraint |
| `technologies` | `(company_id, name, category)` | Unique technology per company | Database UNIQUE constraint |
| `organizations` | `slug` | Global unique slug | Database UNIQUE constraint |
| `users` | `email` | Global unique email | Database UNIQUE constraint |
| `memberships` | `(organization_id, user_id)` | One membership per user-org pair | Database UNIQUE constraint |

---

## Indexes for Performance

All domain tables have indexes on `organization_id` for tenant-scoped queries.

### Composite Indexes (Query Optimization)

| Table | Index Columns | Purpose |
|-------|--------------|---------|
| `intent_signals` | `(organization_id, company_id, signal_type, observed_at)` | Company signal timeline queries |
| `intelligence_scores` | `(organization_id, company_id, total_score)` | Lead retrieval with score filtering |
| `outreach_messages` | `(organization_id, company_id)` | Company outreach message lookup |
| `agent_runs` | `(organization_id, agent_name, status, created_at)` | Agent run history and monitoring |
| `jobs` | `(status, scheduled_at)` | Job scheduler polling query |
| `jobs` | `(target_name)` | Job filtering by agent/workflow name |
| `discovery_runs` | `(organization_id, search_id, status)` | Discovery run history queries |

---

## Data Ownership Model

```mermaid
graph TD
    subgraph Global["Global Scope (No Tenant)"]
        Users[users]
        Orgs[organizations]
    end
    
    subgraph TenantScoped["Tenant-Scoped (organization_id)"]
        Companies[companies]
        Contacts[contacts]
        Tech[technologies]
        Signals[intent_signals]
        Scores[intelligence_scores]
        Messages[outreach_messages]
        Evidence[evidence_records]
        Runs[agent_runs]
        Jobs[jobs]
        Searches[discovery_searches]
        DiscoveryRuns[discovery_runs]
    end
    
    subgraph UserOwned["User-Owned (user_id)"]
        Tokens[refresh_tokens]
        Verify[email_verification_tokens]
        Reset[password_reset_tokens]
        Attempts[failed_login_attempts]
    end
    
    subgraph CrossTenant["Cross-Tenant Join Table"]
        Memberships[memberships]
    end
    
    Orgs -.->|owns| TenantScoped
    Users -.->|owns| UserOwned
    Users -.->|joins via| Memberships
    Orgs -.->|joins via| Memberships
    
    style Global fill:#e1ffe1
    style TenantScoped fill:#fff4e1
    style UserOwned fill:#ffe1e1
    style CrossTenant fill:#f0e1ff
```

### Ownership Rules

| Category | Tables | Access Pattern |
|----------|--------|----------------|
| **Global** | `users`, `organizations` | No tenant filter, globally unique |
| **Tenant-Scoped** | 11 domain tables | Always filtered by `organization_id` |
| **User-Owned** | 4 auth token tables | Filtered by `user_id`, no cross-user access |
| **Cross-Tenant** | `memberships` | Join table, filtered by both `organization_id` and `user_id` |

---

## Discovery Engine Relationships

Added in migration `20260618_0008`.

```mermaid
erDiagram
    organizations ||--o{ discovery_searches : "creates"
    discovery_searches ||--o{ discovery_runs : "executed as"
    discovery_searches ||--o{ companies : "discovers"
    discovery_runs ||--o{ companies : "creates"
    
    discovery_searches {
        uuid id PK
        uuid organization_id FK
        string name
        text criteria "JSON ICP criteria"
        string status "active | archived"
        int total_discovered
        datetime last_run_at
    }
    
    discovery_runs {
        uuid id PK
        uuid organization_id FK
        uuid search_id FK
        string status "running | succeeded | failed"
        int sources_queried
        int companies_found
        int companies_created
        int companies_skipped
        datetime started_at
        datetime finished_at
        text error_message
    }
    
    companies {
        string discovered_via "NULL | discovery_pipeline"
        uuid discovery_search_id FK "SET NULL"
        float discovery_score "0.0-1.0"
    }
```

### Discovery Flow

1. User creates `discovery_search` with ICP criteria (industry, company size, technologies, keywords)
2. User triggers `discovery_run` for a search
3. `DiscoveryAgent` queries external sources (SEC EDGAR, Google News RSS, OpenCorporates)
4. `DiscoveryPipelineWorkflow` creates `companies` with:
   - `discovered_via = 'discovery_pipeline'`
   - `discovery_search_id` linking back to originating search
   - `discovery_score` (0.0-1.0) for prioritization
5. `discovery_run` updates statistics (companies_found, companies_created, companies_skipped)

See [Discovery Engine Design](lead_discovery_engine_final.md) for complete documentation.

---

## Related Documentation

- **[Database Design](database.md)** — Complete table schemas, column definitions, constraints
- **[Architecture Overview](architecture_overview.md)** — System layers, request lifecycle, multi-tenancy
- **[Agent System](agents.md)** — How agents create and link intelligence records
- **[Workflow System](workflows.md)** — How workflows orchestrate entity creation
- **[Authentication](authentication_multitenancy_v2_design.md)** — User, organization, membership design
- **[Discovery Engine](lead_discovery_engine_final.md)** — Discovery search and run lifecycle

---

**Last Updated:** 2026-07-01  
**Total Tables:** 19  
**Total Relationships:** 45+ foreign keys
