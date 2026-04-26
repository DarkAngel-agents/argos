# Contributing to ARGOS

Thanks for considering a contribution. ARGOS is alpha software written by one maintainer with strong opinions about scope, simplicity, and operational safety. The rules below exist to keep the project coherent — please read them before opening a PR.

## TL;DR — the workflow

**Issue first → discussion → code → tests → PR. No direct push to `main`.**

If you skip a step, your PR will likely be closed and asked to start over. Not personal; it keeps reviews fast.

## 1. Open an issue first

Before writing code, open a GitHub issue describing:
- **What you want to change and why**
- **What problem it solves** (with a concrete scenario, not a hypothetical)
- **Alternatives you considered**
- For bugs: reproduction steps, expected vs. actual behaviour, your environment (OS, Docker version, ARGOS commit SHA)
- For features: at least one paragraph on why this belongs in ARGOS rather than as a separate tool / skill / external service

For security issues, **do not open a public issue** — see [SECURITY.md](./SECURITY.md).

## 2. Wait for triage / discussion

The maintainer will respond and one of:
- **`accepted`** — go ahead and code; the issue stays open and the PR closes it
- **`needs-design`** — agree on approach in the issue thread before any code
- **`wontfix` / `out-of-scope`** — politely declined with a reason
- **`duplicate`** — link to the existing issue and continue there

Triage happens in batches, usually within a week. If your issue is sitting for more than two weeks without a label, ping it once.

Substantial PRs (more than ~200 lines, new endpoints, schema changes, new dependencies) require explicit `accepted` before code starts. Bug fixes, doc fixes, and small refactors can move faster.

## 3. Write the code

Branching:
- Fork the repo, then branch from `main` in your fork
- Branch name: `fix/<short-slug>`, `feat/<short-slug>`, or `docs/<short-slug>`
- One logical change per branch — do not bundle unrelated fixes

What to keep in mind:
- **Match existing code style.** Indentation, naming, error messages — copy what's already there. ARGOS has no formal `.editorconfig` yet; the existing code is the spec.
- **Python:** 4-space indent, type hints on public functions, async where the surrounding file is async. Use `os.getenv()` for any new configuration knob and document the variable in `env.example`.
- **Rust (hooks):** `cargo fmt` before commit. Stable Rust only.
- **Frontend:** Alpine.js + htmx in the v2 modules. No build step. No new framework dependencies without an issue first.
- **No new dependencies** without an issue. New packages go through license review (the project is Apache 2.0 — GPL-3 / AGPL deps are blocked).
- **No mock data** in production paths. If a feature needs stubs to demo, gate them behind a feature flag and document.
- **No new global state** in the FastAPI process unless necessary; the existing module-level caches are already on the cleanup list.

What ARGOS won't accept:
- Adding `eval()`, `exec()`, `os.system()`, or `subprocess(... shell=True)` anywhere reachable from an HTTP endpoint
- Catching `Exception` and silently passing
- f-string SQL or string concatenation for SQL — always parameterized
- Hardcoded secrets, IPs, or usernames in code (use env vars or DB tables)
- "Drive-by" reformatting of files unrelated to your change
- Auto-generated AI commits without human review

## 4. Tests

Every PR with a code change must include tests, or explain in the PR description why testing is impractical.

Existing test suites:
- **Rust hook:** `cd argos-core/hooks/argos-approval-hook && cargo test`
- **MCP server:** `cd argos-core/mcp_servers/argos_db_mcp && python -m pytest tests/ -q`

The FastAPI server in `argos-core/api/` does not yet have a test suite. Bug fixes there should add at least a regression test using `httpx.AsyncClient` against the FastAPI app — even a single one. Greenfield endpoints should ship with happy-path + auth-failure + bad-input tests.

Run the relevant suite locally before opening the PR:
```bash
# rust
cd argos-core/hooks/argos-approval-hook && cargo test

# mcp
cd argos-core/mcp_servers/argos_db_mcp && python -m pytest tests/ -q
```

If your change touches the database schema, include a forward migration in `argos-core/schema.sql` (or as a separate migration file) and verify it applies cleanly to a fresh DB.

## 5. Open the PR

PR title format: `<area>: <imperative summary>` — examples:
- `api: gate /api/exec behind X-Argos-Key header`
- `ui: wire approvals module to /api/claude-code/approvals`
- `docs: clarify standalone vs swarm in INSTALL.md`

PR body must include:
- **Closes #N** for the corresponding issue
- **What changed** — one paragraph
- **Why** — link to the discussion in the issue if anything was decided there
- **How tested** — concrete commands you ran, output if non-obvious
- **Risks / migration notes** — what could break, what operators need to do at upgrade

The maintainer will:
- Run CI (when CI exists; for now, manual)
- Review within ~one week (sooner for security or bug fixes)
- Either merge, request changes, or close with a reason

There is no merge button you can press yourself. `main` is protected.

## Commits

- Imperative present tense: `add X`, `fix Y`, not `Added X`
- One concept per commit when reasonable; squash before final review if the history is messy
- Reference the issue number in the commit body if it adds context (`Refs #42`)
- Do not amend commits after a reviewer has commented — push a follow-up commit so the diff is reviewable, then squash on merge

## License of contributions

By submitting a PR, you agree that your contribution is licensed under the project's [Apache License 2.0](../LICENSE) and that you have the right to license it under those terms. ARGOS does not require a separate CLA.

## Code of conduct

Be civil. Disagreements about technical decisions are fine; personal attacks, harassment, or bad-faith argument get you blocked. The maintainer is the final arbiter on what counts as bad faith.

## Questions

For anything that doesn't fit a bug or feature request — design questions, "why does X work this way" — open a GitHub Discussion (once enabled) or send an issue with the `question` label.
