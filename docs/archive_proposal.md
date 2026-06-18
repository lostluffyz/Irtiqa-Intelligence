# Documentation Archive Proposal

This document proposes restructuring the `docs/` directory to separate current-state reference documents from historical design/audit/task documents.

## Problem

The `docs/` directory currently contains 40+ files (19,000+ lines). Completed design documents, audit reports, and task plans are mixed with active architecture references. This makes it difficult to find current information and creates staleness risk as documents are not updated after their work is complete.

## Current State

### Active Reference Documents (keep at top level)

| File | Purpose |
|------|---------|
| `project_state.md` | Current implementation status and inventory |
| `project_handoff.md` | Complete architecture and conventions reference |
| `codex_bootstrap.md` | Quick-start for new sessions |
| `database.md` | Database schema, migrations, and operations |
| `agents.md` | Agent architecture and responsibilities |
| `workflows.md` | Workflow architecture and implementations |
| `agent_interface_design.md` | Agent interface contracts |

### New Documents (keep at top level)

| File | Purpose |
|------|---------|
| `api_reference.md` | Complete endpoint inventory |
| `architecture_overview.md` | High-level system map |
| `authentication_architecture.md` | Auth system reference |
| `lead_retrieval_architecture.md` | Lead retrieval design |
| `entity_relationships.md` | Complete ERD and FK documentation |

### Historical Documents (move to `docs/archive/`)

All completed design, audit, and task documents should be moved to `docs/archive/` with a README explaining they are historical references.

**Design documents:**
- `authentication_multitenancy_design.md`
- `authentication_multitenancy_v2_design.md`
- `background_job_foundation_design.md`
- `ci_cd_pipeline_design.md`
- `deep_scraper_design.md`
- `evidence_records_system_design.md`
- `intelligence_pipeline_design.md`
- `intelligence_scoring_design.md`
- `intent_signal_agent_design.md`
- `multitenancy_phase1_design.md`
- `multitenancy_phase2_design.md`
- `multitenancy_phase3_design.md`
- `personalization_agent_design.md`
- `postgresql_compatibility_verification_design.md`
- `technographic_agent_design.md`

**Audit documents:**
- `authentication_multitenancy_audit.md`
- `ci_cd_pipeline_audit.md`
- `ci_cd_pipeline_audit_tasks.md`
- `ci_cd_pipeline_qualit_audit.md`
- `evidence_records_system_audit.md`
- `intelligence_pipeline_audit.md`
- `multitenancy_implementation_audit.md`
- `multitenancy_phase2_audit.md`
- `multitenancy_phase3_audit.md`

**Task documents:**
- `background_job_foundation_tasks.md`
- `ci_cd_pipeline_tasks.md`
- `evidence_records_system_tasks.md`
- `intelligence_pipeline_tasks.md`
- `intelligence_scoring_tasks.md`
- `multitenancy_phase1_tasks.md`
- `multitenancy_phase2b_tasks.md`
- `personalization_agent_tasks.md`
- `postgresql_compatibility_verification_tasks.md`

## Proposed Directory Structure

```text
docs/
├── project_state.md              # Current status
├── project_handoff.md            # Architecture reference
├── codex_bootstrap.md            # Quick start
├── database.md                   # Schema reference
├── agents.md                     # Agent architecture
├── workflows.md                  # Workflow architecture
├── agent_interface_design.md     # Agent contracts
├── api_reference.md              # Endpoint inventory
├── architecture_overview.md      # System map
├── authentication_architecture.md # Auth reference
├── lead_retrieval_architecture.md # Lead retrieval design
├── entity_relationships.md       # ERD documentation
├── archive/                      # Historical documents
│   ├── README.md                 # Explains archive purpose
│   ├── *_design.md               # Completed design docs
│   ├── *_audit.md                # Completed audit docs
│   └── *_tasks.md                # Completed task docs
```

## Benefits

1. **Reduced noise** — Top-level docs directory has ~15 focused files instead of 40+
2. **Clear signals** — New developers know which docs are current vs historical
3. **Reduced staleness** — Archive docs don't need updates; active docs do
4. **Easier navigation** — Fewer files to scan when looking for current state
5. **Preserved history** — Archive keeps all design decisions accessible for reference

## Implementation

1. Create `docs/archive/` directory
2. Create `docs/archive/README.md` explaining the archive
3. Move all 34 historical documents to `docs/archive/`
4. Update any cross-references in active documents
