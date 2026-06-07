# Personalization Agent Design

## Purpose
The Personalization Agent is the final stage in the Irtiqa Intelligence pipeline. Its goal is to synthesize the extensive evidence collected by the Deep Scraper, Technographic, and Intent Signal Agents—and scored by the Intelligence Scoring Agent—into contextual, highly personalized outreach messages. Adhering strictly to the "no mock data" and "no external AI APIs" rules, the agent utilizes a deterministic template and prompt generation architecture. The output is a suite of ready-for-review `OutreachMessage` variants (e.g., multiple email and LinkedIn variants) to empower SDR workflow choices.

## Inputs
- **Context**: `AgentContext` containing `company_id` and an optional `contact_id`.
- **Dependencies**: `**services` dictionary injected through `BaseAgent`.

## Outputs
- **AgentRunOutput**: Returns a summary, execution stats, and the `output_ids` mapping all created outreach message variants (e.g., `{"outreach_messages": ["<uuid_email_a>", "<uuid_email_b>", "<uuid_linkedin>"]}`).

## Service Interactions
The agent interacts exclusively with the service layer to maintain clean architecture and transaction boundaries:
1. `CompanyService`: Fetch canonical company details.
2. `ContactService`: Fetch contact details if `contact_id` is provided.
3. `TechnologyService`: Fetch detected technologies to inject technographic angles.
4. `IntentSignalService`: Fetch intent signals to prioritize the messaging hook.
5. `IntelligenceScoreService`: Fetch the latest intelligence score to determine the strongest fit/intent angle.
6. `OutreachMessageService`: Persist the final generated templates.

## Database Interactions
No direct repository or database interaction. All persistence operations occur via `OutreachMessageService.create()`.

## Scoring and Intelligence Consumption
The agent consumes the latest `IntelligenceScore` for the company/contact to determine the optimal personalization strategy for the *primary* variant, while also generating supplementary variants:
- **Primary Angle**: If `intent_score` is highest, the primary email prioritizes intent signals. If `technographic_score` is highest, it prioritizes tech.
- **Variant Generation**: Instead of choosing just one, the agent generates multiple variants across channels (e.g., an intent-driven email, a tech-driven alternative email, and a concise LinkedIn variant). This supports modern SDR workflows where humans review and select the best draft.

## Prompt Generation Architecture
Given the "no external AI APIs" constraint, the "Prompt Generation" architecture acts as a sophisticated, deterministic text assembler. It builds structured textual prompts that can either be:
1. Consumed directly by a human Sales Development Representative (SDR) as a draft.
2. Used in the future as a zero-shot prompt payload if an LLM integration is later authorized.

The architecture consists of:
- **Context Builder**: Flattens the ORM models (Company, Contact, top Tech, top Intent) into a unified dictionary of string replacements.
- **Angle Selector**: Evaluates the `IntelligenceScore` to select the primary `personalization_angle` string (e.g., "intent_funding", "tech_competitor", "high_fit_cold").

## Template Architecture
Templates are defined in a local registry (e.g., `app/agents/personalization/templates.py`) utilizing Python's native `string.Template` or `str.format()`.
- **Channels**: The agent generates messages for both `email` and `linkedin` during a single run.
- **Structure**: Each template specifies a `subject` (for email, null for LinkedIn), a `message_body`, and a `call_to_action`.
- **Variants**: The agent generates a comprehensive suite for the SDR to review:
  - **Email Variant A (Primary Angle)**: Based on the highest component score (e.g., Intent).
  - **Email Variant B (Secondary Angle)**: Based on the second highest score or a generic high-fit angle.
  - **LinkedIn Variant**: A shorter, more direct variant tailored for social outreach.
- **Variables**: Templates expect strict variables like `{contact_first_name}`, `{company_name}`, `{intent_signal_summary}`, and `{technology_name}`.

## Edge Cases
1. **Missing Contact**: If `contact_id` is missing or the contact lacks a name, the agent falls back to generic company-level templates or "Team" salutations.
2. **Missing Intelligence Score**: The agent must compute a fallback angle (e.g., "general_fit") if no prior score exists.
3. **No Intent or Tech**: The template engine must gracefully fall back to default templates without leaving blank `{technology_name}` placeholders.
4. **Missing Values**: The Context Builder must provide safe default strings (e.g., "your recent initiatives") if a specific field is `None`.

## Testing Strategy
- **Unit Tests (`tests/unit/agents/personalization/test_agent.py`)**:
  - Test the Context Builder's ability to safely format text.
  - Test the Angle Selector's branch logic against mocked `IntelligenceScore`s.
  - Test `_run` execution to ensure `OutreachMessageCreate` is properly formed and passed to the service.
  - Test all edge cases (missing contact, missing intent, missing tech) to guarantee no `KeyError` or formatting exceptions occur.
- **Integration Tests**: Rely on existing workflow and service tests; agent tests should mock the services.
