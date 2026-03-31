# ARGOS Roadmap

## v1 — Current (Alpha)

- Docker Swarm 2-node deployment
- PostgreSQL 17 with streaming replication and automatic failover < 3 seconds
- HAProxy transparent failover
- DEFCON monitoring system with Home Assistant notifications
- Skills tree — 100+ verified procedures loaded dynamically per context
- Error pattern learning (activates codes after 10 occurrences)
- Ollama local GPU inference (qwen3:14b)
- Claude + Grok dual reasoning engine
- Auto-archive with local summarization
- setup.sh bootstrap tested on Fedora 42, Fedora 44, Debian 13
- Voice commands via Home Assistant ("Hey Jarvis tell ARGOS to...")
- ARGOS notifies you on mobile for approvals and alerts

---

## v2 — In Development (Radical Changes)

### Knowledge Architecture — "Bubble DB"
Complete redesign of how ARGOS stores and retrieves knowledge.
Instead of loading all skills into context, a dedicated index agent retrieves
only the relevant chunks into working memory per message.
Result: dramatically lower token usage, much faster responses, better accuracy.

### Security Compartmentalization
Data classified by sensitivity level.
Sensitive operations processed exclusively on local GPU — never sent to external APIs.
Encryption between Docker containers to prevent inter-service sniffing.
End-to-end HTTPS for all internal and external communication.

### Intelligent Self-Discovery
ARGOS automatically discovers and indexes new skill files from the filesystem.
No manual import needed — drop a .md file, ARGOS learns it.

### Skills Compactor
Automatic deduplication and scoring of the skills tree.
Removes redundant entries, consolidates similar skills, scores by usage and reliability.
Target: reduce current 129 entries to ~65 high-quality unique skills.

### Advanced Reasoning Engine
Restructured multi-step reasoning with explicit chain-of-thought.
Better decomposition of complex infrastructure problems before acting.

### PWA Mobile App
Progressive Web App for mobile — full ARGOS interface on your phone.
Voice input, approval buttons, real-time notifications.

### Database Restructure
Schema redesign aligned with new security compartmentalization model.
Migration tools included — no data loss from v1.

---

*This is a living, evolving autonomous system.*
*Made with love, spite, and pure determination.*
