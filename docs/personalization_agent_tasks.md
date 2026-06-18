> **Status: IMPLEMENTED**

# Personalization Agent Tasks

## 1. Setup & Foundations
- [ ] Read `docs/personalization_agent_design.md` for context.
- [ ] Create directory: `app/agents/personalization/`.
- [ ] Create `app/agents/personalization/__init__.py`.
- [ ] Export `PersonalizationAgent` from `app/agents/__init__.py`.

## 2. Template Architecture Implementation
- [ ] Create `app/agents/personalization/templates.py`.
- [ ] Define the `TemplateContext` TypedDict or dataclass.
- [ ] Implement `get_template_for_angle(angle: str, channel: str) -> dict` function.
- [ ] Define templates for `intent-driven`, `tech-driven`, and `fit-driven` angles.
- [ ] Provide safe default fallbacks for missing template parameters.

## 3. Agent Implementation
- [ ] Create `app/agents/personalization/agent.py`.
- [ ] Define `PersonalizationAgent` inheriting from `BaseAgent`.
- [ ] Set `name = "personalization_agent"` and `version = "1.0.0"`.
- [ ] Implement `_run(self, context: AgentContext)`.
- [ ] Resolve dependencies: `CompanyService`, `ContactService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `OutreachMessageService`.
- [ ] Fetch required records (Company, Contact, Top Technology, Top Intent Signal, Latest Intelligence Score).
- [ ] Implement `Angle Selector` logic to determine Primary and Secondary angles based on component scores.
- [ ] Map data to `TemplateContext`.
- [ ] Render templates for Email Variant A (Primary), Email Variant B (Secondary), and LinkedIn Variant.
- [ ] Create multiple `OutreachMessageCreate` schema payloads.
- [ ] Call `OutreachMessageService.create()` for each payload in a loop.
- [ ] Return `AgentRunOutput` with an array of `output_ids` for the variants.

## 4. Testing
- [ ] Create directory: `tests/unit/agents/personalization/`.
- [ ] Create `tests/unit/agents/personalization/__init__.py`.
- [ ] Create `tests/unit/agents/personalization/test_templates.py`.
  - [ ] Test template formatting edge cases.
  - [ ] Test angle selection logic.
- [ ] Create `tests/unit/agents/personalization/test_agent.py`.
  - [ ] Test `_run` with complete data (full context).
  - [ ] Test `_run` missing contact data (company-only context).
  - [ ] Test `_run` missing intent/tech/scores (fallback scenarios).
- [ ] Run `python -m pytest tests/unit/agents/personalization/` and verify 100% pass rate.
- [ ] Run full test suite `python -m pytest` and ensure everything remains green.

## 5. Documentation
- [ ] Update `docs/agents.md` with the new Personalization Agent details.
- [ ] Do NOT implement actual execution/job orchestration yet.
