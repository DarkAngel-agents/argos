# Contributing to ARGOS

Thanks for being interested. Read this fully before you write code or open a PR.

## A note before the rules

I'm a nobody. I'm not a famous developer, I haven't built anything you've heard of, and I learned what I know by reading code from people who are genuinely good at this and adapting their ideas — usually in ways the original authors would not have done. I don't claim authority. I claim experience that has been mostly painful.

The rules in this document — issue-first, atomic commits, tests before PRs — exist because I've seen what happens without them. They're not me being arrogant; they're me trying to keep a project I can barely manage from collapsing entirely.

Before you propose code or send concrete implementation suggestions, I'd genuinely prefer that we talk first. Not because I think your idea is wrong, but because I might have context you don't, or you might have context I'm missing. A short conversation upfront saves both of us from work that lands in the wrong place.

If any of the rules below feel too rigid, open a discussion and tell me. I'd rather adjust than alienate someone whose contribution would have been valuable.

## The short version

1. **Open an issue first.** Talk before you code.
2. **Wait for feedback** on the issue before writing the implementation.
3. **Write tests.** All of them must pass before the PR.
4. **Atomic commits.** One commit per logical change.
5. **No bundled changes.** Don't fix three things in one PR.
6. **No force-pushes to main.** Ever.

If you don't read past this section, at least read the section on **issue-first workflow** — that's the one I care about most.

## Issue-first workflow (mandatory)

### Step 1 — Open an issue

Describe:
- **What you want to change** (one paragraph, plain language)
- **Why** (concrete problem you're solving, not "wouldn't it be nice if")
- **Your proposed approach** (rough — we'll refine together)
- **What you're explicitly NOT changing** (scope discipline)

If you're not sure how to phrase it, look at existing issues. Mimic the structure.

### Step 2 — Wait for response

I will respond with one of:
- **"Yes, this approach works"** → proceed to Step 3
- **"Here's a different approach"** → discuss in the issue, agree on direction
- **"Not now"** → I'll explain why; you can either argue your case or accept the deferral
- **"Out of scope"** → some things belong in a fork, not in ARGOS proper. I'll say so.

Do **not** start writing code before an issue conversation has converged on a direction. I will close PRs whose corresponding issues haven't been discussed.

### Step 3 — Write the code

- Branch from `main`. Name the branch after the issue: `fix/<issue-num>-short-description` or `feat/<issue-num>-short-description`.
- Atomic commits. If you're tempted to write "and also fixed X", that's a separate commit.
- Tests for new behavior. We use pytest for Python, standard FastAPI test client patterns.
- All existing tests must still pass. **Run them before pushing.**

### Step 4 — Open the PR

- Reference the issue: `Closes #N`
- Describe what changed, in your own words, even if the issue already does
- Confirm tests pass (paste output if it helps)
- Confirm you ran a smoke test against a running ARGOS instance if your change touches runtime code

### Step 5 — Review

- I will review. I may ask for changes. This is normal.
- I may take a few days. ARGOS is maintained part-time.
- I will not merge anything that hasn't been smoke-tested.

## Commit hygiene

### Atomic commits

One commit per logical change. Examples of **good**:

```
feat(rate-limit): redis backend for cross-replica counter
fix(ui): #269 add Dashboard nav-item in 7 modules
config(deploy): consolidate prod state into git
```

Examples of **bad** (I will ask you to split):

```
"various fixes"
"updates"
"feat: redis + fix ui + cleanup backups"
```

### Commit message format

```
<type>(<scope>): <short summary>

<optional longer body explaining why, not what>
```

Types we use: `feat`, `fix`, `refactor`, `config`, `docs`, `test`, `chore`, `security`.

Scope is optional but encouraged when it disambiguates: `(api)`, `(ui)`, `(deploy)`, `(rate-limit)`, etc.

### No commits with secrets

Run a quick grep before pushing:

```bash
git diff --cached | grep -iE 'sk-ant|api[_-]?key|password|token|secret' && echo "REVIEW THIS"
```

If you accidentally commit a secret: **do not push**. Reset, remove the secret, recommit. If you already pushed: open an issue immediately, we'll discuss whether to rotate or rewrite history.

## Testing requirements

- **Unit tests** for any new function with non-trivial logic
- **Integration tests** for endpoints (FastAPI test client)
- **Smoke test against a running instance** if your change affects runtime — describe the test you ran in the PR

We don't have a formal coverage threshold yet. Use judgment. New code without tests will be questioned.

## Code style

- **Python**: PEP 8, but pragmatic. Line length: ~100. Use type hints in new code.
- **Logs**: structured debug codes `[CATEGORY NNN]` (see `argos-core/CLAUDE.md` for the full convention)
- **Imports**: `os.getenv()` for environment variables. Never hardcode secrets, never hardcode IPs that should be env-configurable.
- **No `sed` for file editing in scripts** — use Python text-replace. We've broken too many things with sed.
- **No `docker restart` on Swarm services** — use `docker service update --force`. This is a learned lesson.

## Skills

If you're contributing a skill (a Markdown procedure file in `argos-core/skills/`):

- **Generic before specific.** Public skills should not reference your hostnames, IPs, or credentials. Use placeholders.
- **Format**: see existing skills for the structure (Trigger / Diagnose / Fix / Verify / Edge cases / Dependencies).
- **Tested**: you've actually run this skill against a real failure, not just imagined what it would do.

If your skill is too specific to your environment to generalize, that's fine — keep it in your private fork. Don't try to upstream homelab-specific procedures.

## What I will reject

Without further discussion, the following are auto-rejected:

- PRs without a corresponding issue
- PRs that bundle multiple unrelated changes
- PRs that add dependencies without explanation
- PRs that disable existing tests to make new code "pass"
- PRs that introduce hardcoded secrets, even if "temporary"
- Force-pushes to shared branches
- Commits without authorship clarity (anonymous email, unclear author)

## What I welcome

- Bug reports with reproduction steps
- Documentation improvements (the docs are sparse — help is genuinely useful)
- Generic skills that other operators could use
- Refactoring proposals for known debt (`chat.py` is the obvious one)
- Test coverage improvements
- Honest critique of architectural decisions

## A note on tone

I try to be direct without being rude. I expect the same. "This is wrong because X" is fine. "This is wrong, are you stupid" is not.

If a review feels harsh, assume good faith first. I'm often working under time pressure and brevity reads as harshness. Ask for clarification rather than escalating.

If a contributor's PR feels low-effort, I'll say so plainly and explain what would make it work. I won't ghost you.

## Questions

Open a discussion (not an issue) if you have a question about how to contribute, what's in scope, or how something works. I answer when I can.

Welcome aboard. Be patient with the project — alpha-stage things move in bursts.

---

_See `LICENSE` for legal terms. By contributing, you agree your contributions are licensed under Apache 2.0._
