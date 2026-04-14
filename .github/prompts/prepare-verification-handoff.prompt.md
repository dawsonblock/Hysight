---
name: "Prepare Verification Handoff"
description: "Prepare test_result.md before handing work to the backend or frontend verification agent."
argument-hint: "Describe what changed and which verification agent should receive the handoff."
agent: "agent"
tools: [read, search, edit]
---

Prepare the testing handoff for this repo before delegating verification.

Use these sources:

- [test_result.md](../../test_result.md)
- [Backend Verification](../agents/backend-verification.agent.md)
- [Frontend Verification](../agents/frontend-verification.agent.md)

Required workflow:

1. Read [test_result.md](../../test_result.md) and preserve the protocol block exactly.
2. Identify the implementation changes that need verification and map them to the existing `backend` or `frontend` task entries. If a required task entry does not exist yet, add one using the documented YAML structure.
3. Update `status_history` with implementation details, set `needs_retesting: true` for tasks that now require verification, and update `working` only when there is direct evidence.
4. Update `test_plan.current_focus` so it contains only the highest-priority tasks for the next verifier.
5. Append a concise `agent_communication` entry that tells the next verification agent what changed, what to focus on, and any required environment details.
6. Recommend the correct next verifier:
   - Use [Backend Verification](../agents/backend-verification.agent.md) for FastAPI, backend Python, Mongo, sidecar, contract, or runtime proof work.
   - Use [Frontend Verification](../agents/frontend-verification.agent.md) for React, Jest, lint, build, or API-client boundary proof work.
7. Return a short handoff summary that states which verification agent should be invoked next and why.

Do not run tests in this prompt unless the user explicitly asks for verification in the same request.
