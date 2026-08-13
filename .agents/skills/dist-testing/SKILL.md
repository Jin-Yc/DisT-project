---
name: dist-testing
description: Select focused DisT unittest checks and distinguish known Windows SQLite cleanup failures from regressions.
---

# DisT Testing Skill

Use whenever behavior, API, resource contracts, or workflow gates change.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_workflow.WorkflowApiTest -v
.\.venv\Scripts\python.exe -m unittest tests.test_ui_layout_contract.UiLayoutContractTest -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use `WorkflowApiTest` for routes, transitions, ownership, gates, and visibility; use `UiLayoutContractTest` for shared assets and explicit CSS contracts. The current full-suite SQLite cleanup `WinError 32` is a known Windows baseline, not a regression unless connection lifecycle changed.
