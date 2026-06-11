# SQLite Database Design

Irtiqa Intelligence uses a SQLite-first relational database with SQLAlchemy as the ORM layer. The schema should remain portable to PostgreSQL by avoiding SQLite-only modeling assumptions and by keeping database-specific behavior behind the SQLAlchemy engine, session, and migration layers.

## Design Goals

- SQLite first for local development and initial production usage.
- PostgreSQL compatible for future scale.
- SQLAlchemy ORM friendly.
- Proper entity relationships and foreign keys.
- Indexed for common company and contact intelligence queries.
- Timestamped records for auditability and refresh workflows.
- Append-friendly intelligence history for scores, signals, messages, and agent runs.

## Core Entities

- `companies`
- `contacts`
- `websites`
- `technologies`
- `intent_signals`
- `intelligence_scores`
- `outreach_messages`
- `evidence_records`
- `agent_runs`

## Entity Relationship Diagram

```mermaid
erDiagram
    companies ||--o{ contacts : has
    companies ||--o{ websites : owns
    companies ||--o{ intent_signals : emits
    companies ||--o{ intelligence_scores : receives
    companies ||--o{ outreach_messages : targeted_by
    companies ||--o{ agent_runs : analyzed_by

    contacts ||--o{ intent_signals : associated_with
    contacts ||--o{ intelligence_scores : receives
    contacts ||--o{ outreach_messages : receives
    contacts ||--o{ agent_runs : analyzed_by

    websites ||--o{ technologies : reveals
    websites ||--o{ intent_signals : supports

    technologies ||--o{ intent_signals : influences
    technologies ||--o{ intelligence_scores : contributes_to

    agent_runs ||--o{ evidence_records : produces
    agent_runs ||--o{ intent_signals : produces
    agent_runs ||--o{ intelligence_scores : produces
    agent_runs ||--o{ outreach_messages : produces
    agent_runs ||--o{ technologies : detects

    companies {
        uuid id PK
        text name
        text domain
        text industry
        text company_size
        text headquarters
        text description
        text linkedin_url
        text status
        datetime created_at
        datetime updated_at
    }

    contacts {
        uuid id PK
        uuid company_id FK
        text first_name
        text last_name
        text full_name
        text email
        text phone
        text title
        text department
        text seniority
        text linkedin_url
        text status
        datetime created_at
        datetime updated_at
    }

    websites {
        uuid id PK
        uuid company_id FK
        text url
        text normalized_url
        text page_type
        integer http_status
        datetime last_scraped_at
        datetime created_at
        datetime updated_at
    }

    technologies {
        uuid id PK
        uuid company_id FK
        uuid website_id FK
        uuid agent_run_id FK
        text name
        text category
        text vendor
        text detection_method
        real confidence
        datetime first_detected_at
        datetime last_detected_at
        datetime created_at
        datetime updated_at
    }

    intent_signals {
        uuid id PK
        uuid company_id FK
        uuid contact_id FK
        uuid website_id FK
        uuid technology_id FK
        uuid agent_run_id FK
        text signal_type
        text signal_name
        text signal_value
        real strength
        real confidence
        text source_url
        datetime observed_at
        datetime created_at
        datetime updated_at
    }

    intelligence_scores {
        uuid id PK
        uuid company_id FK
        uuid contact_id FK
        uuid technology_id FK
        uuid agent_run_id FK
        real fit_score
        real intent_score
        real technographic_score
        real engagement_score
        real total_score
        real confidence
        text score_version
        text rationale
        datetime scored_at
        datetime created_at
        datetime updated_at
    }

    outreach_messages {
        uuid id PK
        uuid company_id FK
        uuid contact_id FK
        uuid intelligence_score_id FK
        uuid agent_run_id FK
        text channel
        text subject
        text message_body
        text personalization_angle
        text call_to_action
        text status
        real confidence
        datetime generated_at
        datetime created_at
        datetime updated_at
    }

    agent_runs {
        uuid id PK
        uuid company_id FK
        uuid contact_id FK
        text agent_name
        text workflow_name
        text status
        text input_summary
        text output_summary
        text error_message
        datetime started_at
        datetime finished_at
        datetime created_at
        datetime updated_at
    }
```

## SQLAlchemy Modeling Guidelines

Use SQLAlchemy ORM models with explicit relationships between entities. The model layer should use portable column types and avoid database-specific assumptions.

| Concern | SQLite First | PostgreSQL Compatible Direction |
| --- | --- | --- |
| Primary keys | Store UUIDs as text strings | Can migrate to native UUID later |
| JSON-like metadata | Store as validated text | Can migrate to JSONB later |
| Date/time | Store UTC timestamps | Use timezone-aware timestamps later |
| Boolean values | SQLAlchemy boolean abstraction | Native boolean |
| Foreign keys | Enable SQLite foreign keys explicitly | Native enforcement |
| Write reliability | WAL mode and busy timeout | Native MVCC and lock management |
| Indexes | SQLAlchemy index definitions | Same index declarations migrate cleanly |
| Migrations | Alembic | Alembic |

Recommended timestamp fields:

| Field | Purpose |
| --- | --- |
| `created_at` | When the record was first stored. |
| `updated_at` | When the record was last changed. |
| Domain-specific timestamps | Examples: `observed_at`, `scored_at`, `generated_at`, `started_at`, `finished_at`. |

## SQLite Production Settings

SQLite remains the first database target. The SQLAlchemy engine applies SQLite-specific PRAGMAs on connection while keeping this behavior isolated from repositories and models.

| Setting | Default | Purpose |
| --- | --- | --- |
| `PRAGMA foreign_keys` | `ON` | Enforces relational integrity in SQLite. |
| `PRAGMA journal_mode` | `WAL` | Improves read/write concurrency for production SQLite deployments. |
| `PRAGMA busy_timeout` | `5000` ms | Gives locked writers time to complete before raising lock errors. |

Environment variables:

| Variable | Default |
| --- | --- |
| `SQLITE_FOREIGN_KEYS` | `true` |
| `SQLITE_JOURNAL_MODE` | `WAL` |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` |

PostgreSQL does not use these PRAGMAs. They are applied only when the configured SQLAlchemy database URL starts with `sqlite`.

## SQLite Backup Strategy

SQLite database files are generated runtime artifacts. The default local database path is:

```text
database/irtiqa.db
```

This file and related SQLite sidecar files must remain uncommitted:

- `database/irtiqa.db`
- `database/irtiqa.db-wal`
- `database/irtiqa.db-shm`
- `*.db`
- `*.sqlite`
- `*.sqlite3`

Backups should be treated as operational artifacts and stored outside the source tree. Recommended local backup destinations include an encrypted local backup directory, an encrypted external volume, or a managed backup location configured by the deployment environment.

### Local Backup Procedure

Use SQLite's online backup behavior instead of copying the database file while the application may be writing to it. A direct file copy can miss committed data that still lives in the WAL file.

Recommended local backup flow:

1. Confirm the configured `DATABASE_URL` points to the intended SQLite database.
2. Stop write-heavy workflows when possible, especially before migrations.
3. Create a timestamped backup file outside the repository.
4. Use the SQLite backup command or an equivalent application-managed online backup connection.
5. Run an integrity check against the backup.
6. Record the source database path, backup path, timestamp, application version, and Alembic revision.

Recommended SQLite shell pattern:

```text
sqlite3 database/irtiqa.db ".backup 'C:/path/to/backups/irtiqa-YYYYMMDD-HHMMSS.db'"
sqlite3 C:/path/to/backups/irtiqa-YYYYMMDD-HHMMSS.db "PRAGMA integrity_check;"
sqlite3 C:/path/to/backups/irtiqa-YYYYMMDD-HHMMSS.db "SELECT version_num FROM alembic_version;"
```

The expected `PRAGMA integrity_check` result is:

```text
ok
```

### Automated Backup Recommendations

Automated backups should be added before the system stores production lead intelligence.

Recommended policy:

- Run scheduled online backups at least daily for low-volume local deployments.
- Run more frequent backups before and after large imports, enrichment runs, workflow execution, or schema migrations.
- Keep short-term rolling backups for fast operator recovery.
- Keep longer retention copies in encrypted off-machine storage.
- Verify every backup with `PRAGMA integrity_check`.
- Capture the Alembic revision with every backup.
- Emit structured logs for backup start, success, failure, source path, destination path, duration, file size, and revision.
- Alert on missed backups, failed integrity checks, and repeated backup failures.

Retention should be defined by deployment needs. A reasonable starting point for early production is daily backups for 14 days, weekly backups for 8 weeks, and monthly backups for 12 months, adjusted once real data volume and recovery requirements are known.

### WAL Considerations

Irtiqa Intelligence enables SQLite WAL mode by default. WAL mode improves concurrency, but it changes backup expectations:

- Do not back up only `irtiqa.db` with a plain file copy while the application is running.
- The `-wal` file may contain committed transactions that have not been checkpointed into the main database file.
- The `-shm` file is a shared-memory coordination file and should not be treated as an independent database backup.
- Prefer SQLite's online `.backup` command or a future application-level backup utility using SQLite backup APIs.
- If a cold filesystem copy is required, stop all application processes first and copy the main database plus sidecar files together.
- Run `PRAGMA wal_checkpoint(FULL);` only during a controlled maintenance window if a checkpoint is needed before a cold copy.

The normal backup path should remain online backup, not manual copying of WAL sidecar files.

### Restore Procedure

Restore operations should be deliberate and should preserve the failed or suspect database for later inspection.

Recommended restore flow:

1. Stop the application, workers, scheduled jobs, and any process that may open the SQLite database.
2. Move the current database and any sidecar files to a quarantine location instead of deleting them.
3. Copy the selected backup into the configured database path.
4. Run `PRAGMA integrity_check` against the restored database.
5. Confirm the Alembic revision in `alembic_version`.
6. Run `python -m alembic upgrade head` if the backup is valid but behind the current code's migration head.
7. Start the application.
8. Perform a read-only smoke check against core tables before allowing writes.

Restore verification commands:

```text
sqlite3 database/irtiqa.db "PRAGMA integrity_check;"
sqlite3 database/irtiqa.db "SELECT version_num FROM alembic_version;"
python -m alembic upgrade head
python -m alembic check
```

Do not restore a backup over a live database with active writers.

### Backup Order Around Migrations

Schema migrations should always be recoverable.

Recommended migration order:

1. Stop application writes or place the deployment into maintenance mode.
2. Create and verify a pre-migration backup.
3. Record the current Alembic revision.
4. Run `python -m alembic upgrade head`.
5. Run `python -m alembic check`.
6. Run the relevant test or smoke-check path for the changed schema.
7. Create and verify a post-migration backup.
8. Resume writes.

If a migration fails, keep the failed database state for diagnosis and restore the verified pre-migration backup before restarting write traffic.

## Table Definitions

## companies

Stores canonical company accounts.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `name` | Text | Yes | Company name. |
| `domain` | Text | Yes | Normalized primary domain. |
| `industry` | Text | No | Normalized industry. |
| `company_size` | Text | No | Employee range or size band. |
| `headquarters` | Text | No | Human-readable location. |
| `description` | Text | No | Company summary. |
| `linkedin_url` | Text | No | Company LinkedIn profile. |
| `status` | Text | Yes | Suggested values: `active`, `needs_review`, `archived`. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- One company has many contacts.
- One company has many websites.
- One company has many technologies.
- One company has many intent signals.
- One company has many intelligence scores.
- One company has many outreach messages.
- One company has many agent runs.

Indexes:

- Unique index on `domain`.
- Index on `name`.
- Index on `industry`.
- Index on `status`.
- Index on `created_at`.

## contacts

Stores people associated with companies.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `first_name` | Text | No | Given name. |
| `last_name` | Text | No | Family name. |
| `full_name` | Text | Yes | Display name. |
| `email` | Text | No | Email address when known. |
| `phone` | Text | No | Phone number when known. |
| `title` | Text | No | Job title. |
| `department` | Text | No | Example: `sales`, `marketing`, `engineering`, `operations`, `finance`. |
| `seniority` | Text | No | Example: `manager`, `director`, `vp`, `c_level`, `founder`. |
| `linkedin_url` | Text | No | Contact LinkedIn profile. |
| `status` | Text | Yes | Suggested values: `active`, `unverified`, `qualified`, `disqualified`, `archived`. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many contacts belong to one company.
- One contact has many intent signals.
- One contact has many intelligence scores.
- One contact has many outreach messages.
- One contact has many agent runs.

Indexes:

- Index on `company_id`.
- Unique nullable index on `email`.
- Index on `linkedin_url`.
- Index on `department`.
- Index on `seniority`.
- Index on `status`.

## websites

Stores websites and pages discovered for a company.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `url` | Text | Yes | Original URL. |
| `normalized_url` | Text | Yes | Canonical URL used for deduplication. |
| `page_type` | Text | No | Example: `homepage`, `pricing`, `careers`, `blog`, `docs`, `case_study`, `unknown`. |
| `http_status` | Integer | No | Last observed HTTP status. |
| `last_scraped_at` | DateTime | No | Last successful scrape time. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many websites belong to one company.
- One website can reveal many technologies.
- One website can support many intent signals.

Indexes:

- Unique index on `normalized_url`.
- Index on `company_id`.
- Index on `page_type`.
- Index on `http_status`.
- Index on `last_scraped_at`.

## technologies

Stores technologies detected for a company. This table represents detected company technology usage, not only a global technology catalog.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `website_id` | UUID/Text | No | Foreign key to `websites.id`. |
| `agent_run_id` | UUID/Text | No | Foreign key to `agent_runs.id`. |
| `name` | Text | Yes | Technology name. |
| `category` | Text | Yes | Example: `crm`, `cms`, `analytics`, `payments`, `cloud`, `marketing_automation`. |
| `vendor` | Text | No | Vendor or owner. |
| `detection_method` | Text | Yes | Example: `html_signature`, `script_src`, `header`, `dns`, `job_posting`, `manual_review`. |
| `confidence` | Real | Yes | Detection confidence from `0.0` to `1.0`. |
| `first_detected_at` | DateTime | Yes | First detection time. |
| `last_detected_at` | DateTime | Yes | Most recent detection time. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many technologies belong to one company.
- Many technologies may be associated with one website.
- Many technologies may be detected by one agent run.
- One technology detection can influence many intent signals and intelligence scores.

Indexes:

- Composite unique index on `company_id`, `name`, `category`.
- Index on `company_id`.
- Index on `website_id`.
- Index on `agent_run_id`.
- Index on `name`.
- Index on `category`.
- Index on `confidence`.
- Index on `last_detected_at`.

Future option:

- If the catalog grows, split this into `technology_catalog` and `company_technologies`. For the current requested entity set, `technologies` should store company-specific detected usage.

## intent_signals

Stores detected buying intent, operational signals, and trigger events.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `contact_id` | UUID/Text | No | Foreign key to `contacts.id`. |
| `website_id` | UUID/Text | No | Foreign key to `websites.id`. |
| `technology_id` | UUID/Text | No | Foreign key to `technologies.id`. |
| `agent_run_id` | UUID/Text | No | Foreign key to `agent_runs.id`. |
| `signal_type` | Text | Yes | Example: `hiring`, `funding`, `technology_change`, `growth`, `pain_indicator`, `content_activity`. |
| `signal_name` | Text | Yes | Human-readable signal label. |
| `signal_value` | Text | No | Captured value or summary. |
| `strength` | Real | Yes | Commercial strength from `0.0` to `1.0`. |
| `confidence` | Real | Yes | Evidence confidence from `0.0` to `1.0`. |
| `source_url` | Text | No | URL supporting the signal. |
| `observed_at` | DateTime | Yes | When the signal was observed. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many intent signals belong to one company.
- Many intent signals may relate to one contact.
- Many intent signals may be supported by one website.
- Many intent signals may be influenced by one technology.
- Many intent signals may be produced by one agent run.

Indexes:

- Index on `company_id`.
- Index on `contact_id`.
- Index on `website_id`.
- Index on `technology_id`.
- Index on `agent_run_id`.
- Index on `signal_type`.
- Index on `strength`.
- Index on `confidence`.
- Index on `observed_at`.
- Composite index on `company_id`, `signal_type`, `observed_at`.

## intelligence_scores

Stores versioned scoring outputs for companies and contacts.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `contact_id` | UUID/Text | No | Foreign key to `contacts.id`. |
| `technology_id` | UUID/Text | No | Foreign key to `technologies.id` when a specific technology drives the score. |
| `agent_run_id` | UUID/Text | No | Foreign key to `agent_runs.id`. |
| `fit_score` | Real | Yes | ICP fit score from `0.0` to `100.0`. |
| `intent_score` | Real | Yes | Intent score from `0.0` to `100.0`. |
| `technographic_score` | Real | Yes | Technology relevance score from `0.0` to `100.0`. |
| `engagement_score` | Real | Yes | Outreach readiness or engagement potential from `0.0` to `100.0`. |
| `total_score` | Real | Yes | Weighted total score from `0.0` to `100.0`. |
| `confidence` | Real | Yes | Overall confidence from `0.0` to `1.0`. |
| `score_version` | Text | Yes | Version of scoring policy. |
| `rationale` | Text | Yes | Explanation of score drivers. |
| `scored_at` | DateTime | Yes | When score was calculated. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many intelligence scores belong to one company.
- Many intelligence scores may belong to one contact.
- Many intelligence scores may reference one technology.
- Many intelligence scores may be produced by one agent run.
- One intelligence score can support many outreach messages.

Indexes:

- Index on `company_id`.
- Index on `contact_id`.
- Index on `technology_id`.
- Index on `agent_run_id`.
- Index on `total_score`.
- Index on `confidence`.
- Index on `score_version`.
- Index on `scored_at`.
- Composite index on `company_id`, `total_score`.
- Composite index on `contact_id`, `total_score`.

Data rule:

- Scores should be append-only. A new scoring policy or refreshed input data should create a new row rather than overwriting historical scores.

## outreach_messages

Stores generated outreach recommendations and message drafts.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | Yes | Foreign key to `companies.id`. |
| `contact_id` | UUID/Text | No | Foreign key to `contacts.id`. |
| `intelligence_score_id` | UUID/Text | No | Foreign key to `intelligence_scores.id`. |
| `agent_run_id` | UUID/Text | No | Foreign key to `agent_runs.id`. |
| `channel` | Text | Yes | Example: `email`, `linkedin`, `call`, `sms`. |
| `subject` | Text | No | Subject line when relevant. |
| `message_body` | Text | Yes | Draft or structured message body. |
| `personalization_angle` | Text | Yes | Main reason this message is relevant. |
| `call_to_action` | Text | No | Suggested next step. |
| `status` | Text | Yes | Suggested values: `draft`, `ready_for_review`, `approved`, `sent`, `archived`. |
| `confidence` | Real | Yes | Personalization confidence from `0.0` to `1.0`. |
| `generated_at` | DateTime | Yes | When generated. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many outreach messages belong to one company.
- Many outreach messages may target one contact.
- Many outreach messages may use one intelligence score.
- Many outreach messages may be produced by one agent run.

Indexes:

- Index on `company_id`.
- Index on `contact_id`.
- Index on `intelligence_score_id`.
- Index on `agent_run_id`.
- Index on `channel`.
- Index on `status`.
- Index on `confidence`.
- Index on `generated_at`.

Data rule:

- Outreach messages should retain the exact intelligence score reference used at generation time when available.

## evidence_records

Stores provenance links between intelligence outputs and the source evidence that produced them. Every evidence record maps a source entity to a target entity with a typed relationship and supporting content.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `source_type` | Text | Yes | Discriminator: `website`, `agent_run`, `job`. |
| `source_id` | UUID/Text | Yes | Polymorphic FK to the source entity. |
| `source_detail` | Text | No | Free-text description of the source (e.g., "extracted_text paragraph 3"). |
| `source_location_type` | Text | No | Structured location method: `css_selector`, `xpath`, `line_number`, `paragraph_index`, `url_fragment`. |
| `source_location_value` | Text | No | Structured location value (e.g., `#main > p:nth-child(3)`). |
| `evidence_type` | Text | Yes | Type: `html_snippet`, `text_excerpt`, `url_match`, `signature_match`, `computed_metric`, `agent_summary`. |
| `evidence_value` | Text | Yes | The actual evidence excerpt (max ~5000 characters). Full raw content remains in source tables. |
| `evidence_hash` | Text | No | SHA-256 hex digest of `evidence_value` for deduplication. |
| `relationship_type` | Text | Yes | How this evidence relates to its target: `supports`, `contradicts`, `contributes_to`, `generates`. |
| `target_type` | Text | Yes | Target discriminator: `technology`, `intent_signal`, `intelligence_score`, `outreach_message`. |
| `target_id` | UUID/Text | Yes | Polymorphic FK to the target entity. |
| `confidence` | Real | Yes | Confidence in this evidence from `0.0` to `1.0`. |
| `agent_run_id` | UUID/Text | No | Declarative FK to `agent_runs.id` with `ON DELETE SET NULL`. |
| `company_id` | UUID/Text | No | Denormalized for efficient per-company queries. |
| `contact_id` | UUID/Text | No | Denormalized for efficient per-contact queries. |
| `created_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many evidence records may be produced by one agent run.
- Evidence records use polymorphic source and target FKs (application-enforced, not declarative).

Indexes:

- Composite index on `target_type`, `target_id`.
- Composite index on `source_type`, `source_id`.
- Index on `evidence_type`.
- Index on `relationship_type`.
- Index on `agent_run_id`.
- Index on `company_id`.
- Index on `contact_id`.
- Index on `evidence_hash`.
- Index on `target_type`.
- Index on `created_at`.
- Composite index on `source_location_type`, `source_location_value`.

Data rules:

- Evidence recording is additive and non-blocking. If evidence recording fails, the source agent execution still succeeds.
- Deduplication uses SHA-256 of `evidence_value` within the same `target_type`/`target_id` scope. Deduplication works across separate transactions, not within a single unflushed batch.

## agent_runs

Stores execution history for all agents.

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | UUID/Text | Yes | Primary key. |
| `company_id` | UUID/Text | No | Foreign key to `companies.id`. |
| `contact_id` | UUID/Text | No | Foreign key to `contacts.id`. |
| `agent_name` | Text | Yes | Example: `deep_scraper`, `technographic_intelligence`, `intent_signal`, `intelligence_scoring`, `personalization`. |
| `workflow_name` | Text | No | Parent workflow name. |
| `status` | Text | Yes | Suggested values: `pending`, `running`, `succeeded`, `failed`, `cancelled`. |
| `input_summary` | Text | No | Safe summary of input context. |
| `output_summary` | Text | No | Safe summary of produced output. |
| `error_message` | Text | No | Failure reason. |
| `started_at` | DateTime | Yes | Execution start time. |
| `finished_at` | DateTime | No | Execution finish time. |
| `created_at` | DateTime | Yes | UTC timestamp. |
| `updated_at` | DateTime | Yes | UTC timestamp. |

Relationships:

- Many agent runs may belong to one company.
- Many agent runs may belong to one contact.
- One agent run may produce many technologies.
- One agent run may produce many intent signals.
- One agent run may produce many intelligence scores.
- One agent run may produce many outreach messages.

Indexes:

- Index on `company_id`.
- Index on `contact_id`.
- Index on `agent_name`.
- Index on `workflow_name`.
- Index on `status`.
- Index on `started_at`.
- Index on `finished_at`.
- Composite index on `agent_name`, `status`.
- Composite index on `workflow_name`, `status`.

## Relationship Summary

| Parent | Child | Relationship |
| --- | --- | --- |
| `companies` | `contacts` | One-to-many |
| `companies` | `websites` | One-to-many |
| `companies` | `technologies` | One-to-many |
| `companies` | `intent_signals` | One-to-many |
| `companies` | `intelligence_scores` | One-to-many |
| `companies` | `outreach_messages` | One-to-many |
| `companies` | `agent_runs` | One-to-many |
| `contacts` | `intent_signals` | One-to-many, optional |
| `contacts` | `intelligence_scores` | One-to-many, optional |
| `contacts` | `outreach_messages` | One-to-many, optional |
| `contacts` | `agent_runs` | One-to-many, optional |
| `websites` | `technologies` | One-to-many, optional |
| `websites` | `intent_signals` | One-to-many, optional |
| `technologies` | `intent_signals` | One-to-many, optional |
| `technologies` | `intelligence_scores` | One-to-many, optional |
| `agent_runs` | `technologies` | One-to-many, optional |
| `agent_runs` | `intent_signals` | One-to-many, optional |
| `agent_runs` | `intelligence_scores` | One-to-many, optional |
| `agent_runs` | `outreach_messages` | One-to-many, optional |
| `agent_runs` | `evidence_records` | One-to-many, optional |
| `intelligence_scores` | `outreach_messages` | One-to-many, optional |

## Recommended Query Patterns

### Account Intelligence View

Fetch one company with:

- Contacts.
- Websites.
- Latest detected technologies.
- Recent intent signals.
- Latest intelligence score.
- Latest outreach messages.
- Recent agent runs.

Key indexes:

- `companies.domain`
- `contacts.company_id`
- `websites.company_id`
- `technologies.company_id`
- `intent_signals.company_id`
- `intelligence_scores.company_id`
- `outreach_messages.company_id`
- `agent_runs.company_id`

### Prioritized Lead List

Sort contacts or companies by latest total score.

Key indexes:

- `intelligence_scores.total_score`
- `intelligence_scores.scored_at`
- `intelligence_scores.company_id`
- `intelligence_scores.contact_id`

### Intent Monitoring

Find recent high-strength signals.

Key indexes:

- `intent_signals.observed_at`
- `intent_signals.strength`
- `intent_signals.signal_type`
- Composite index on `company_id`, `signal_type`, `observed_at`.

### Agent Observability

Find failed or slow agent runs.

Key indexes:

- `agent_runs.agent_name`
- `agent_runs.workflow_name`
- `agent_runs.status`
- `agent_runs.started_at`
- `agent_runs.finished_at`

## Data Integrity Rules

- `companies.domain` should be unique after normalization.
- `contacts.email` should be unique when present.
- `websites.normalized_url` should be unique.
- `technologies` should be unique per company by `company_id`, `name`, and `category`.
- Scores should be append-only and versioned by `score_version`.
- Outreach messages should reference the score used to generate them when available.
- Agent runs should never be deleted if they produced persisted intelligence.
- Timestamps should be stored in UTC.
- Confidence values are constrained between `0.0` and `1.0`.
- Intent signal strength is constrained between `0.0` and `1.0`.
- Score values are constrained between `0.0` and `100.0`.
- Stable status fields are constrained to documented values.

## Check Constraints

Implemented check constraints:

| Table | Constraint |
| --- | --- |
| `companies` | `status` must be `active`, `needs_review`, or `archived`. |
| `contacts` | `status` must be `active`, `unverified`, `qualified`, `disqualified`, or `archived`. |
| `agent_runs` | `status` must be `pending`, `running`, `succeeded`, `failed`, or `cancelled`. |
| `technologies` | `confidence` must be between `0.0` and `1.0`. |
| `intent_signals` | `strength` and `confidence` must be between `0.0` and `1.0`. |
| `intelligence_scores` | score components must be between `0.0` and `100.0`; `confidence` must be between `0.0` and `1.0`. |
| `outreach_messages` | `status` must be `draft`, `ready_for_review`, `approved`, `sent`, or `archived`; `confidence` must be between `0.0` and `1.0`. |
| `evidence_records` | `evidence_type` must be `html_snippet`, `text_excerpt`, `url_match`, `signature_match`, `computed_metric`, or `agent_summary`; `relationship_type` must be `supports`, `contradicts`, `contributes_to`, or `generates`; `confidence` must be between `0.0` and `1.0`. |

## Migration Path to PostgreSQL

The schema should be designed so the application can move from:

```text
sqlite:///data/irtiqa.db
```

to:

```text
postgresql+psycopg://user:password@host:5432/irtiqa
```

without changing domain logic.

Migration considerations:

- Keep SQLAlchemy models database-agnostic.
- Use Alembic migrations from the beginning.
- Avoid raw SQL in repositories unless isolated by dialect.
- Avoid SQLite-only column behavior.
- Keep UUID handling centralized.
- Keep JSON/text metadata validation in the application layer until PostgreSQL JSONB is introduced.
- Take a verified SQLite backup immediately before any PostgreSQL migration attempt.
- Record the SQLite Alembic revision and apply the same migration head to PostgreSQL before loading data.
- Prefer an explicit export/import or ETL process that validates row counts, foreign keys, timestamps, UUID formats, and constrained enum-like values.
- Validate migrated PostgreSQL data with application-level read checks and repository integration tests before switching writes.
- Keep the SQLite database in read-only archival storage until PostgreSQL production behavior has been verified.

## PostgreSQL Compatibility

PostgreSQL compatibility has been verified against PostgreSQL 18.x. The following compatibility points were confirmed:

### Verified Behavior

- All 5 Alembic migrations (initial schema, database hardening, website content columns, jobs table, evidence records) apply cleanly to PostgreSQL.
- All 5 migrations downgrade and re-apply cleanly (full round-trip).
- Alembic `check` reports no new upgrade operations on PostgreSQL.
- All 10 application tables are created with correct columns matching model metadata.
- All check constraints are created and enforced on PostgreSQL.
- SQLAlchemy dialect-default pool classes are correct: `NullPool` for SQLite, `QueuePool` for PostgreSQL.
- Engine-level SQLite PRAGMAs (`check_same_thread`, `foreign_keys`, `WAL`, `busy_timeout`) are correctly gated behind `is_sqlite`.
- 24 dedicated PostgreSQL verification tests pass.
- Existing 284 SQLite tests all pass with no regressions.

### Changes Applied

Two migration files were modified to fix PostgreSQL compatibility issues found during verification:

1. **`database/migrations/versions/20260531_0002_database_hardening.py`**: Changed `recreate="always"` to `recreate="auto"` in all `batch_alter_table` calls. The `always` option forced table recreation on PostgreSQL, which failed when trying to drop primary key constraints with dependent foreign keys. The `auto` option lets PostgreSQL use direct `ALTER TABLE ADD CONSTRAINT` instead.

2. **`database/migrations/versions/20260609_0003_add_jobs_table.py`**: Added `op.f()` wrapper to all check constraint names in `batch_alter_table`. Without `op.f()`, Alembic batch mode prefixed constraint names with the table name, producing `ck_jobs_ck_jobs_status` instead of `ck_jobs_status`.

### Known Behavioral Differences

| Behavior | SQLite | PostgreSQL |
| --- | --- | --- |
| Check constraint enforcement | Check constraints are enforced | Check constraints are enforced identically |
| Naive datetimes | Accepted (stored as text) | Accepted (psycopg 3 converts to session timezone) |
| UUID storage | `String(36)` text column | `String(36)` text column |
| Unique constraint violation | `IntegrityError` | `IntegrityError` |
| Foreign key violation | `IntegrityError` | `IntegrityError` |
| Connection pooling | `NullPool` (no pooling) | `QueuePool` (size=5, overflow=10) |

### Running PostgreSQL Verification Tests

```bash
# Install PostgreSQL driver
pip install "psycopg[binary]>=3.2.0"

# Create a PostgreSQL database for verification
createdb irtiqa_verify

# Run migrations
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify alembic upgrade head

# Run verification tests (will be skipped without DATABASE_URL)
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest tests/integration/test_postgresql_compatibility.py

# Run full test suite against PostgreSQL
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest
```

## Recommended Creation Order

1. `companies`
2. `contacts`
3. `websites`
4. `agent_runs`
5. `technologies`
6. `intent_signals`
7. `intelligence_scores`
8. `outreach_messages`
