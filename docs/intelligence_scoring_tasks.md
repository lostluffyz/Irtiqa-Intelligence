> **Status: IMPLEMENTED**

# Intelligence Scoring Agent Tasks

## 1. Agent Implementation
- [ ] Create `app/agents/intelligence_scoring/agent.py`.
- [ ] Implement `IntelligenceScoringAgent` extending `BaseAgent`.
- [ ] Implement `_run()` method to:
  - Fetch `Company` via `CompanyService`.
  - Fetch `Contact` (if `contact_id` exists) via `ContactService`.
  - Fetch `Technology` list via `TechnologyService`.
  - Fetch `IntentSignal` list via `IntentSignalService`.
  - Execute `DeterministicScoreRefreshPolicy`.
  - Save the resulting score via `IntelligenceScoreService`.
  - Return the mapped `output_ids`.
- [ ] Create `app/agents/intelligence_scoring/__init__.py`.
- [ ] Register `IntelligenceScoringAgent` in `app/agents/__init__.py`.

## 2. Testing
- [ ] Create `tests/unit/agents/intelligence_scoring/__init__.py`.
- [ ] Create `tests/unit/agents/intelligence_scoring/test_agent.py`.
- [ ] Add unit tests mocking all dependent services to test purely the orchestration layer of the Agent.
- [ ] Verify handling of `AgentContext` both with and without a `contact_id`.
- [ ] Run full project test suite (`python -m pytest`) to guarantee zero regressions.

## 3. Documentation
- [ ] Update `docs/project_state.md` to reflect the completion of the Intelligence Scoring Agent.
- [ ] Update `docs/project_handoff.md` to move Intelligence Scoring Agent to the completed agents phase.
- [ ] Update `docs/codex_bootstrap.md` to reflect current status.
- [ ] Create/Update walkthrough artifact for the user.
