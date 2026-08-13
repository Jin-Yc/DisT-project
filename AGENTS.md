# DisT Development Agents

## Project map

DisT is a Chinese-language local product-readiness prototype. `app.py` is a Flask app factory serving static pages and JSON APIs. Server workflow state is stored in SQLite; browser proposal drafts and role selection use `localStorage`.

- `app.py`: routes, API validation, state transitions, SQLite payloads, simulated AI and meeting-minutes analysis.
- `index.html`, `project-view.html`, `role-review.html`, `new-project.html`: static entry points.
- `assets/app.js`: shared role, overview, sidebar, iteration, O2O, and reviewer interactions.
- `assets/new-project.js`: PL-only proposal creation and confirmation flow.
- `tests/test_workflow.py`: workflow/API tests.
- `tests/test_ui_layout_contract.py`: shared asset and CSS contract tests.

## Invariants

- This is a local prototype; UI role selection is not authentication.
- Keep SQLite-backed review state separate from browser-local draft state.
- Only an Issue's submitting team role may confirm it closed after PL responds.
- Do not bypass stage readiness gates.
- Only confirmed PL projects appear in Overview and sidebar Projects.
- RI and Ecom are read-only iteration snapshots.
- AI output is advisory, never a confirmed decision.

## Change rules

- Trace frontend controls through their JavaScript handlers and matching API endpoints.
- Keep API error status and messages explicit; never silently bypass a gate.
- Preserve shared versioned UI asset references checked by `tests/test_ui_layout_contract.py`.
- Update targeted `unittest` coverage for behavior changes.
- Do not add tooling or dependencies unless the request requires them.

## Commands

```powershell
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest tests.test_workflow.WorkflowApiTest -v
.\.venv\Scripts\python.exe -m unittest tests.test_ui_layout_contract.UiLayoutContractTest -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Windows, some workflow tests currently fail only during temporary SQLite cleanup with `WinError 32`, because connections remain open. Report this known baseline separately from regressions unless a change affects connection lifecycle.

## Agent roles

- **Full-stack implementer**: focused backend, frontend, persistence, and test changes.
- **Workflow/API reviewer**: state transitions, persistence, gates, Issue ownership, and client/server contracts.
- **Frontend/UI reviewer**: DOM contracts, role navigation, `localStorage`, escaping, and shared UI assets.
- **Test agent**: targeted test coverage and precise baseline-versus-regression reporting.

