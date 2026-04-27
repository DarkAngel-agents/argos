# DISCLAIMER

ARGOS is **public alpha software**. Read this before you deploy it, fork it, or trust it with anything important.

## What "public alpha" means here

It does **not** mean "we ran a few tests and shipped it." It means:

- **The code runs in production** — but only on the author's homelab, with the author's eyes on it daily.
- **APIs and internal architecture will change** between releases without long deprecation cycles.
- **There are known issues** that have not been fixed yet because the priority was getting the architecture right first.
- **Security has been audited but not pen-tested.** We've done our homework on secrets, input validation, rate limiting, and credential storage. We have not paid an external firm to break it.

If your threshold for "production-ready" is "I can deploy this at a regulated company without a security review," ARGOS is not there yet.

## Known things in this repository

We believe in transparency over polish. The following are documented intentionally:

### 1. A revoked UniFi API key in git history

The string `sZua7nHgQoxenkyDrt-9vXRBx7_z-3e8` appears in early commits of this repository. It is:
- A UniFi controller API key from a development phase
- Revoked / non-functional — returns HTTP 401 on any UDM Pro local API call
- Documented as non-working in `argos-core/skills/unifi-os-4.md` (marked "API: SKIP")

We chose not to rewrite git history (`git filter-repo --replace-text`) because:
1. The key is dead. It cannot be exploited.
2. Rewriting history changes every commit SHA and breaks anyone who has cloned.
3. Honest history is more valuable than sterile history for an alpha project where mistakes are part of the learning record.

#### A note on this, since I know it'll come up

Yes, I know it's frustrating and embarrassing to leak something into git that shouldn't be there. I'm not going to pretend otherwise. But I have a simple question for the people who run secret-scanners and walk away: how do you expect to raise an intelligent kid who communicates well with you, if from morning until bedtime they only ever go to kindergarten — never allowed to make mistakes (even with your knowledge, even when you yourself slip up)? How will they "understand" that they were wrong, and what to do so they don't repeat it next time?

1-2% of this work needs human education, not auto-build. The dead UniFi key stays in history because the lesson stays with it. Sterilized history is a kindergarten environment. I'd rather raise something that learns.

If you're scanning this repo with a secrets detector, this key will trip it. That's the expected behavior. The key returns 401.

### 2. Backup files used to live in the repo

Until the cleanup commit on 2026-04-26, `argos-core/api/` contained `*.bak.*`, `*.backup.*`, and `*.bak-pre-*` files from various development checkpoints. These have been moved to a separate backup location and are no longer tracked. The git history still contains them — they were never secrets, just clutter.

### 3. `chat.py` is 1500+ lines

Yes, it needs decomposing. Yes, we know. It's tracked as technical debt. It works correctly; it's just unpleasant to read. Decomposition is post-public-alpha work.

### 4. Internal IP ranges

The codebase, skills, and examples reference IP addresses in the `11.11.11.0/24` and `10.0.10.0/24` ranges. These are **not** the author's real public IPs — they're internal homelab convention using DOD-reserved ranges for clarity. Treat them as you would any other documentation example: change them to fit your network.

### 5. The agent has shell access by design

ARGOS' executor runs subprocesses on the host. This is **the entire point** — an AI infrastructure agent that cannot execute commands cannot do infrastructure work. We've put guards around it (approval flows, autonomy levels, sandboxing where possible) but the fundamental capability is: **the LLM can run shell commands you let it run**.

If you deploy ARGOS, you are explicitly accepting this. Don't run it in environments where you wouldn't trust a junior sysadmin with sudo.

## What we're not claiming

- **We are not claiming production-readiness for regulated environments** (HIPAA, PCI-DSS, SOC2 — none of these have been verified).
- **We are not claiming the agent is safe to run unsupervised** at autonomy level high. Watch it. Use approval flows. Read the logs.
- **We are not claiming the LLM will always make correct decisions.** It won't. Build verification chains. Don't skip them.
- **We are not claiming this is the only way to do agent orchestration.** It's *an* approach. Others exist. Pick what works.

## What you take on by using this

- You audit the code. You don't trust it because it's public.
- You read the prompts the agent uses. You modify them for your context.
- You run it in environments where damage is recoverable until you're confident.
- You report issues you find — that's what alpha is for.
- You don't blame the maintainer when a bug bites you. Open an issue.

## License reminder

This software is provided under [Apache 2.0](LICENSE). That license includes a **disclaimer of warranty** clause. We mean it. The code is provided "as is." If it formats your homelab, the license says we're not liable. The license is correct.

## Reporting security issues

If you find an actual security issue (not "the disclosed UniFi key in git history" — see above), do not open a public issue. Email the maintainer privately. Contact details are in the repo's git history under recent commit author info.

## Final note

Software that pretends to be more polished than it is causes more harm than software that is honest about its state. ARGOS is alpha. Treat it that way and we'll all have a better time.

---

_Last updated: public alpha release._
