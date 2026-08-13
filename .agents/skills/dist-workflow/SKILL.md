---
name: dist-workflow
description: Safely change DisT Flask APIs, SQLite payloads, and readiness-gated review workflows.
---

# DisT Workflow Skill

Use for `app.py`, workflow APIs, SQLite state, Issue handling, or project confirmation.

1. Identify the affected state shape in `INITIAL_STATE`, PL-project payloads, or iteration fixtures.
2. Trace route preconditions, mutation, persistence, and public response shape.
3. Verify the consuming frontend in `assets/app.js` or `assets/new-project.js`.
4. Preserve valid team roles, submitter-owned Issue closure, role-level Issue completion before conclusions, readiness gates, and confirmed-project visibility.
5. Add API tests for accepted and rejected flows.

Example: a new review field must be persisted, exposed through `public_pl_project` or `public_state`, rendered by the consuming frontend, and tested. Do not only update the SQLite payload.
