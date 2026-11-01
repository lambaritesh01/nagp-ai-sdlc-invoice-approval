# Setup Decisions

Confirmed foundational decisions for the independent NAGP AI-SDLC invoice
approval project. This file records **only** decisions that have been explicitly
confirmed during setup. Items needing further confirmation are marked
`UNVERIFIED`.

> Provenance note: the points below are reconstructed from the verified setup
> steps performed in this project's environment-preparation phase. They describe
> configuration decisions, not fabricated AI interaction events. No application
> implementation has started.

## Confirmed decisions

1. **Independent project from scratch** — This is a new, independently developed
   NAGP AI-SDLC project, not derived from another participant's work.

2. **Python runtime** — Python **3.13.14** selected as the project interpreter
   (chosen over 3.13-alternatives/3.14 for tooling maturity). **FastAPI** is the
   candidate web framework.

3. **GitHub account** — Personal GitHub account **`lambaritesh01`** is the active
   GitHub CLI account for this project. The corporate account
   (`Kumar-Ritesh_bcgprod`) remains authenticated but inactive and was **not**
   used to create project resources.

4. **AI tooling** — Claude Code is used via a **BCG-managed Claude subscription
   (OAuth)**. No standalone API key is used for this work.
   - UNVERIFIED: whether BCG policy explicitly permits this assignment's use of
     the managed subscription + a personal GitHub account on this device. Confirm
     with the appropriate owner if required by the assignment.

5. **Workspace location** — The project lives in the approved NAGP workspace
   under OneDrive:
   `.../Documents/NAGP/nagp-ai-sdlc-invoice-approval`.
   - Note: OneDrive sync can occasionally lock `.git`/`.venv` files; this is an
     accepted, flagged risk, not a blocker.

6. **Repository and Git identity** — A separate local Git repository was
   initialized on branch `main` with a **repository-local** identity
   (`user.name = lambaritesh01`,
   `user.email = 67891429+lambaritesh01@users.noreply.github.com`). The global
   corporate Git identity was left unchanged. A **private** GitHub repository
   `lambaritesh01/nagp-ai-sdlc-invoice-approval` was created and connected as
   `origin` over HTTPS. No commits exist yet.

7. **Spec-driven tooling** — GitHub **Spec Kit 1.2.5** was installed as a
   user-level `uv` tool and initialized in the project for the Claude
   integration (skills-based), generating `.specify/` and `.claude/skills/`.

8. **Existing NAGP projects protected** — Other projects in the NAGP workspace
   (e.g. `AWS/`, the `recipe-finder-*` folders) were not modified or accessed
   for changes at any point.

9. **No implementation started** — No invoice-approval specifications,
   application source code, or tests have been created. Development tooling
   (FastAPI, pytest, Playwright, pytest-gremlins, Ruff) is installed in the
   project `.venv` but unused so far.

## Open items (UNVERIFIED)

- Final confirmation of corporate-policy approval for the tooling/account
  combination (see decision 4).
- Whether `.claude/` should be partially git-ignored for credential safety once
  agent configuration begins (Spec Kit prints a security advisory to that
  effect).
