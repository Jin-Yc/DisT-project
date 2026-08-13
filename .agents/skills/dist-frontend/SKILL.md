---
name: dist-frontend
description: Safely change DisT static HTML, JavaScript, CSS, localStorage, and role-aware navigation.
---

# DisT Frontend Skill

Use for page markup, `assets/app.js`, `assets/new-project.js`, or shared styles.

1. Locate page markup and every JavaScript selector/data attribute.
2. Identify browser-local versus API-provided state.
3. Reuse existing API/action helpers.
4. Escape dynamic strings before `innerHTML`.
5. Preserve role restrictions and shared asset references.
6. Update UI contract tests only for intentional shared-contract changes.

Example: add a role-review action across markup, listener, server validation, and workflow test; never add a visual-only button.
