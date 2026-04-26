# Security Policy

## Project status

ARGOS is **alpha** software. The current codebase contains known unauthenticated endpoints and is **not safe to expose to the public Internet** without a reverse proxy enforcing authentication. Self-hosting on a private network or behind a VPN/Tailscale is the intended deployment model.

If you operate ARGOS on a host reachable from the public Internet, treat any vulnerability disclosure as time-critical and apply the mitigations under "Hardening" below.

## Supported versions

The `main` branch receives security fixes. Tagged releases are not yet produced. Once tagged releases exist, only the latest minor will receive backports.

| Branch / Version | Supported |
|---|---|
| `main` | Yes |
| Older commits / forks | No |

## Reporting a vulnerability

Please report vulnerabilities **privately**. Do **not** file a public GitHub issue for security problems.

Preferred channel: email **darkangel@ladomotique.eu**

Include in the report:
- Affected component (file path, endpoint, or feature)
- Version / commit SHA you tested against
- Steps to reproduce, including the minimum payload that triggers the issue
- Impact assessment (RCE, info disclosure, DoS, auth bypass, etc.)
- Any suggested remediation
- Whether you intend to publish a write-up, and your preferred public credit name (or "anonymous")

You should receive an acknowledgement within **5 business days**. If you do not, assume the email was lost and please re-send.

## Disclosure timeline

ARGOS follows a **90-day coordinated disclosure window**, counted from the day the maintainer acknowledges the report:

| Day | Action |
|---|---|
| 0 | Maintainer acknowledges receipt |
| 0–7 | Triage: confirm reproduction, assign severity |
| 7–60 | Develop and test fix |
| 60–80 | Prepare public advisory; coordinate with reporter on disclosure timing |
| 90 | Public disclosure (advisory + patched release) |

If a fix is shipped earlier, public disclosure may be brought forward with the reporter's agreement. If active exploitation is observed in the wild, the maintainer reserves the right to disclose immediately to protect users.

If 90 days elapse without a fix and without an agreed extension, the reporter is free to publish their findings.

## Bounty program

ARGOS does **not** operate a paid bug bounty program. Reporters who follow this policy will be credited (with their permission) in:
- The release notes of the patched version
- A `SECURITY.md` "Hall of Thanks" section once it accumulates entries
- The CVE record, if one is filed

## Scope

In scope:
- The FastAPI server in `argos-core/api/`
- The Claude Code approval hook in `argos-core/hooks/argos-approval-hook/`
- The MCP server in `argos-core/mcp_servers/argos_db_mcp/`
- The agent loop and skill system in `argos-core/agent/`, `argos-core/llm/`, `argos-core/skills/`
- Database schema and seed scripts (`schema.sql`, `init_db.sql`)
- The frontend in `argos-core/ui/` and `argos-core/ui/v2/`
- The Docker compose / swarm files in `docker/`
- The setup script (`setup.sh`)

Out of scope:
- Issues that require local shell access on the ARGOS host (the threat model assumes the host is trusted)
- Issues in third-party dependencies — please report those upstream first; we will track and ship updates when patched releases land
- Social-engineering attacks against the maintainer
- Denial-of-service through resource exhaustion when no rate limit is configured (this is documented behaviour; mitigation is to put a reverse proxy with limits in front)
- Findings against forks that have diverged from `main`

## Hardening guidance for operators

Until the next signed release, operators should:
- Bind the API to `127.0.0.1` (or a private interface) — never `0.0.0.0` on a public host
- Place a reverse proxy (Caddy, nginx, Traefik) in front, enforcing HTTP basic auth, mTLS, or an SSO provider
- Set a strong `DB_PASSWORD` in `.argos.env` (default `changeme` is unsafe)
- Restrict outbound egress to the Anthropic and Grok API endpoints if you do not need general internet access
- Rotate all API keys (Anthropic, Grok) and the database password if you suspect filesystem compromise
- Keep the host OS and Docker engine patched

## License

This security policy is published under the same terms as the project (Apache License 2.0).
