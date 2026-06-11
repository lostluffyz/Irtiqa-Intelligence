# Tasks Document Audit: docs/ci_cd_pipeline_tasks.md vs docs/ci_cd_pipeline_design.md

## 1. Line-by-Line Issues

### Phase 1: Workflow Foundation

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 29 | "Do not add service containers or run steps in this phase." Creates job stubs without the PostgreSQL service container that the design's YAML skeleton includes in the `test` job from the start. The design's YAML skeleton has the container inline; Phase 1 omits it and adds it later (Phase 3/4). | **Low** | Add a note that Phase 1 is an intermediate state and the service container will be added in Phase 3. The design does not require a single-commit implementation, so iterative addition is acceptable, but the mismatch should be acknowledged to prevent confusion. |
| 35 | "Confirm the pull request triggers both jobs to appear in the GitHub Actions checks list with 'Waiting' or 'Queued' status." At this stage both jobs have no steps defined. GitHub Actions renders jobs with no steps as "skipped" rather than "waiting" or "queued." The success criterion is misleading. | **Low** | Change the expected status description: "Confirm both job stubs appear in the Actions tab (they may show as skipped or have no steps)." |
| Phase 1 success criteria | No success criterion verifies that the `services:` block is absent in Phase 1 (since it will be added later). This is fine because Phase 3/4 will add it, but the absence creates a brief state where the workflow file does not match the design. | **Low** | No change needed. Documented for awareness. |

### Phase 2: Validate Job

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 70 | "Pip caching: optional (add if the workflow runtime approaches 7 minutes due to dependency install)." The design's 7-minute target applies to the full pipeline runtime, not per-job. This is fine. No contradiction. | — | No correction needed. |
| 94-99 | Success criteria match the design's validate job description. ✓ | — | No correction needed. |

### Phase 3: Test Job

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 117 | "Add a `services:` block to the `test` job with the PostgreSQL 18 service container (see Phase 4 for detailed configuration)." This is a forward reference — Phase 3 instructs adding the service container but defers the configuration details to Phase 4. An implementer following phases sequentially would have incomplete information at this point. | **Medium** | Either inline the full container configuration here and make Phase 4 a "verify" step, or remove the service container from Phase 3 entirely and add it in Phase 4 only. The current split creates a dependency on reading ahead. |
| 146 | "If `python -m alembic check` fails in CI (fresh checkout with no database file), investigate the `alembic.ini` `sqlalchemy.url` setting. If the URL references a file that does not exist in CI (e.g., `sqlite:///database/irtiqa.db`), override `DATABASE_URL` at the job level or adjust `alembic.ini` to use a non-file-based URL for the check command." **Suggests setting `DATABASE_URL` at the job level.** The design explicitly requires per-step `env:` scoping for `DATABASE_URL` (see design Section 5: "per-step env:"). Setting it at the job level would leak the connection string into all steps and contradicts the design's scoping requirement. While the PostgreSQL steps use per-step `env:` overrides (which would take precedence), the design's intent is clearly per-step scoping, not job-level defaults. | **Medium** | Remove "override `DATABASE_URL` at the job level" as an option. Keep only "adjust `alembic.ini`" as the fix. If a URL override is truly needed, add it as a per-step `env:` on only the `alembic check` step, not at the job level. |
| 142 | "Expected result: 284 passed." Matches design. ✓ | — | No correction needed. |
| 141 | "PostgreSQL-specific tests are automatically skipped via the `postgresql_required` marker." Correct, but there is no explicit task to verify this skip behavior before moving to Phase 4. If the marker fails to skip (e.g., due to an environment variable leak or marker misconfiguration), Phase 3 would report 308 tests found with 24 failures, not 284 passed. | **Medium** | Add a sub-task: "Before concluding Phase 3, verify the SQLite pytest step explicitly reports 284 tests selected and 0 skipped, confirming the `postgresql_required` marker correctly filters out the 24 PostgreSQL tests." |
| 154 | "'test' job with SQLite steps completes within 5 minutes." The design's overall pipeline target is 7 minutes. Having a 5-minute sub-target for just the SQLite portion (excluding PostgreSQL steps which add ~2 minutes) is consistent. No contradiction. | — | No correction needed. |

### Phase 4: PostgreSQL Verification

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 162 | "Add the PostgreSQL 18 service container (if not already added in Phase 3) and the PostgreSQL-specific steps." The "if not already added" guard duplicates responsibility with Phase 3, which already instructs adding the container. If an implementer follows phases strictly, Phase 3 already added it, making Phase 4.1 a no-op. If they skip Phase 3, Phase 4 catches it. This dual-path creates a state machine that is unnecessary for a linear implementation checklist. | **Low** | Remove the "if not already done" condition since Phase 3 already creates the container. Make Phase 4 purely about adding the PostgreSQL-specific run steps and verifying the container works with them. |
| 172-179 | Service container configuration matches the design exactly (image: postgres:18, DB: irtiqa_ci, user/pass: postgres/postgres, port 5432, pg_isready health check with correct intervals). ✓ | — | No correction needed. |
| 193 | "Verify that `DATABASE_URL` is scoped per-step (using `env:` under the step, not a global job-level environment variable)." This explicitly rejects the job-level approach suggested in Phase 3.4. **Internal contradiction within the tasks document.** | **Medium** | Phase 3.4 and Phase 4.3 give contradictory advice on DATABASE_URL scoping. Resolve by removing the job-level option from Phase 3.4 as recommended above. |
| 202 | "Full pipeline reports 308 total tests passed (284 SQLite + 24 PostgreSQL)." Matches design. ✓ | — | No correction needed. |

### Phase 5: README Integration

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 222-226 | Badge markdown matches the design exactly. ✓ | — | No correction needed. |
| 230-231 | "Before the first CI run on main, it will show 'no status' or 'unknown.'" Accurate. ✓ | — | No correction needed. |
| 236 | "Badge is placed directly below the project title." The design says "below the project title" (Section 5, Workflow Name and Badge). The tasks use "directly below" which is slightly more specific but consistent. | — | No correction needed. |

### Phase 6: Documentation Updates

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 256-261 | "Change 'No CI configuration exists yet' under Open Issues." Accuracy depends on the exact current wording in `docs/project_state.md`. If the phrasing has changed since the design document was written (e.g., after the audit updated the design), the text match may fail. The task is fragile. | **Low** | Replace text-match instructions with intent-based instructions: "Update the Open Issues section to remove the CI-related entry." |
| 262-268 | Same text-match fragility for `docs/project_handoff.md` (Sections 5, 7, 9). | **Low** | Replace text-match with intent: "Update all sections that reference 'no CI configuration' or 'no CI pipeline' to reflect that CI now exists." |
| 276 | "Do NOT modify `docs/ci_cd_pipeline_design.md` or `docs/ci_cd_pipeline_tasks.md`." Correct — the design document and tasks document should remain as-is after implementation. ✓ | — | No correction needed. |
| 280-285 | Success criteria check for specific text ("No CI configuration exists yet," "No CI pipeline exists yet," "CI" under "Not implemented"). Same text-match fragility. | **Low** | Change to intent-based criteria: "All three docs no longer reference CI as missing or unimplemented." |

### Phase 7: Validation and Testing

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 307-321 | Verification table covers all 13 steps (6 validate + 7 test) with correct expected results. ✓ | — | No correction needed. |
| 340 | "Set `DATABASE_URL` env var in the test job, or update `alembic.ini`." Same job-level DATABASE_URL issue as Phase 3.4. Recommending a job-level env var contradicts the design's per-step scoping. | **Medium** | Remove "Set `DATABASE_URL` env var in the test job" from the mitigation. Keep only "update `alembic.ini`" or "add a per-step `env:` on the `alembic check` step only." |
| 349 | "Pipeline completes within 7 minutes." Matches design. ✓ | — | No correction needed. |

### Expected Files (End Matter)

| Line(s) | Issue | Severity | Recommended Correction |
|---|---|---|---|
| 355-364 | **Files Created/Modified mismatch.** The design's "Files Expected to Be Modified" lists only `README.md`. The tasks document lists 4 files: `README.md`, `docs/project_state.md`, `docs/project_handoff.md`, `docs/codex_bootstrap.md`. The design's "Files Not Modified" table acknowledges these docs files with the note "will be updated during implementation," so the mismatch is anticipated, but a strict reading shows a count discrepancy. | **Low** | Either: (a) add a note to the tasks document explaining that the three docs files extend beyond the design's minimal deliverable list, or (b) accept the mismatch as the design anticipating follow-up work. No change may be needed — the design explicitly acknowledges these files will be updated during implementation. |
| 366-383 | Verification commands match the pipeline steps exactly. ✓ | — | No correction needed. |

---

## 2. Cross-Document Consistency Report

| Check Area | Result | Notes |
|---|---|---|
| Trigger configuration | ✅ Consistent | Both: push + pull_request to main |
| Job names | ✅ Consistent | Both: `validate` and `test` |
| Job dependency | ✅ Consistent | Both: `test: needs: validate` |
| Runner | ✅ Consistent | Both: `ubuntu-latest` |
| Python version | ✅ Consistent | Both: 3.11 |
| Validate job steps | ✅ Consistent | Both: checkout → setup python → pip install .[dev] → ruff → mypy → compileall |
| Test job base steps | ✅ Consistent | Both: checkout → setup python → pip install .[dev,postgres] → alembic check → pytest (SQLite) |
| PostgreSQL service container | ✅ Consistent | Both: postgres:18, irtiqa_ci, postgres/postgres, port 5432, pg_isready |
| PostgreSQL verification steps | ✅ Consistent | Both: alembic upgrade head → pytest PostgreSQL |
| DATABASE_URL scoping | ❌ Inconsistent | Design: per-step `env:` only. Tasks: Phase 3.4 and Phase 7 suggest job-level as a valid fix option. **Two locations contradict the design.** |
| Test counts | ✅ Consistent | Both: 284 SQLite + 24 PostgreSQL = 308 |
| Step ordering | ✅ Consistent | Both: validate (6 steps) → test (7 steps) in exact order |
| CI badge | ✅ Consistent | Both: same URL, same placement (below project title) |
| Files to create | ✅ Consistent | Both: `.github/workflows/ci.yml` |
| Files to modify | ⚠️ Partial | Design lists 1 file (README.md). Tasks lists 4 (adds 3 docs files). Design's "Files Not Modified" table anticipates this with "will be updated during implementation." |
| No-app-code-change rule | ✅ Consistent | Neither modifies `app/` or `tests/` Python files |
| No-deployment-infra rule | ✅ Consistent | Neither introduces Docker, K8s, AWS, Terraform |
| `postgresql_required` marker behavior | ✅ Consistent | Both describe the marker correctly: skips when DATABASE_URL is not PostgreSQL, runs when it is |
| PostgreSQL container health check | ✅ Consistent | Both: `pg_isready`, 10s interval, 5s timeout, 5 retries |
| Runtime target | ✅ Consistent | Both: ~7 minutes (with separate 5-minute SQLite sub-target in tasks) |

### Consistency Score: 15/16 checks consistent. 1 area has an active contradiction (DATABASE_URL scoping).

---

## 3. Unresolved Concerns

1. **DATABASE_URL scoping contradiction** — The design is explicit: per-step `env:` only. The tasks document suggests job-level as a fix in two places (Phase 3.4, Phase 7 risk table). If implemented as suggested, it would violate the design's scoping requirement. This is the only direct contradiction between the two documents.

2. **PostgreSQL test skip verification gap** — Phase 3 relies on the `postgresql_required` marker to correctly skip 24 tests during the SQLite step, but there is no explicit task to verify this skipping. If an environment variable leak or marker configuration error causes the PostgreSQL tests to run during the SQLite step, they would fail (no PostgreSQL service) and the pipeline would report an error. The fix would be confusing because the SQLite step would appear to depend on PostgreSQL.

3. `alembic.ini` **URL dependency** — Both documents flag this as a risk. The design mentions it as a risk to verify; the tasks document replicates this. If `alembic.ini` specifies `sqlite:///database/irtiqa.db` and that file doesn't exist in CI, `alembic check` fails. This is not a design error but an implementation risk that needs resolution before Phase 3 can complete.

4. **Service container split across phases** — The container is introduced in Phase 3 (as a shell), configured in Phase 4 (details), and verified in Phase 7 (runtime). This three-phase split means the container config is spread across the document rather than defined in one place. For an implementer reading forward, this is fine. For an implementer jumping to Phase 4 first, the container may already exist from Phase 3.

---

## 4. Final Verdict

**Needs revision before implementation.**

### Rationale

The tasks document is 90% consistent with the design. The step ordering, test counts, service container configuration, badge placement, and documentation scope all match correctly. However, one direct contradiction and one verification gap must be resolved before the tasks document can be safely implemented:

### Must-Fix Before Implementation

| # | Issue | Location | Fix |
|---|---|---|---|
| 1 | **DATABASE_URL scoping contradiction** | Phase 3 task 3.4, Phase 7 risk table | Remove "override DATABASE_URL at the job level" from both locations. Replace with "add a per-step `env:` on the `alembic check` step only, or adjust `alembic.ini`." |
| 2 | **PostgreSQL skip verification gap** | Phase 3 (no task exists) | Add a verification sub-task in Phase 3: verify the SQLite pytest step reports 284 tests selected, not 308. This confirms the marker correctly skips PostgreSQL tests before the SQLite step completes. |

### Recommend (Non-Blocking)

| # | Issue | Location | Suggestion |
|---|---|---|---|
| 3 | Service container split | Phase 3 task 3.1 | Either inline the full config in Phase 3 and remove from Phase 4, or remove from Phase 3 and add entirely in Phase 4. Avoid the forward reference. |
| 4 | Text-match fragility | Phase 6 tasks | Replace "Change 'No CI configuration exists yet' to..." with intent-based instructions (e.g., "Update Open Issues to remove the CI-related entry"). |
| 5 | Phase 1 status expectation | Phase 1 task 1.5 | Change "Waiting or Queued" to account for step-less jobs potentially showing as "skipped." |

### Implementation Readiness Summary

| Category | Status |
|---|---|
| Direct contradictions with design | **1 active** (DATABASE_URL scoping) |
| Missing tasks | **1** (PostgreSQL skip verification) |
| Test count errors | None |
| File reference errors | None |
| Step ordering errors | None |
| Environment variable leakage risk | **1** (if job-level DATABASE_URL is implemented) |
| Documentation update errors | None |
| Success criteria mismatches | None |
| **Readiness verdict** | **Needs revision** (2 must-fix items before implementation) |
