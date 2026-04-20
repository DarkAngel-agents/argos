# AUDIT REPORT 07 - Infrastructure Investigation

**Generated:** 2026-04-15 00:14 UTC
**Target:** Beasty + Hermes infrastructure
**Auditor:** Claude Code (read-only audit)
**Focus:** Hermes heartbeat investigation

---

## Section 1: Rezumat executiv

Swarm-ul ARGOS este **functional cu 2/2 replicas** active pe Beasty si Hermes. PostgreSQL si HAProxy sunt operationale. **VERDICT PRINCIPAL:** Hermes heartbeat daemon este **inactive (dead)** din cauza unui "dependency failed" la boot pe 11 aprilie, dupa ce serviciul a avut probleme de DB connectivity pe 8 aprilie. Settings indica `argos_heartbeat_daemon_hermes=true` dar realitatea e ca serviciul nu ruleaza - **CONFLICT CRITIC**. Disk usage sub 80% pe toate partitiile critice.

---

## Section 2: Node identity

```
hostname: Beasty
uname:    Linux Beasty 6.12.75 #1-NixOS SMP PREEMPT_DYNAMIC
user:     darkangel
uptime:   02:13:39 up 1 day 13:24, 1 user, load average: 2.69, 2.62, 2.34
```

---

## Section 3: Docker basics

| Metric | Value |
|--------|-------|
| Docker server | 28.5.2 |
| Swarm state | active |
| Node ID | k5xdx2a23fq0hpf79vdd6l89a |
| node ls | ERR (worker node, run on manager) |

**[INFO]** Swarm state active. Beasty este worker, Hermes este manager.

---

## Section 4: Argos containers local (Beasty)

| Container | Status | Image | Severity |
|-----------|--------|-------|----------|
| argos-swarm_argos.2 | Up 14 hours (healthy) | 11.11.11.111:5000/argos:latest | **[INFO]** |
| argos-db | Up 37 hours | postgres:17 | **[INFO]** |
| argos-registry | Up 37 hours | registry:2 | **[INFO]** |
| argos-ollama | Up 37 hours | ollama/ollama | **[INFO]** |

**[INFO]** Toate containerele healthy si up.

---

## Section 5: Swarm services via Hermes

```
[SSH OK to root@11.11.11.98]
ID             NAME                MODE         REPLICAS   IMAGE                            PORTS
qbir0hlzdpyt   argos-swarm_argos   replicated   2/2        11.11.11.111:5000/argos:latest   *:666->8000/tcp
```

**[INFO]** SSH la Hermes OK. Service argos-swarm_argos cu 2/2 replicas.

---

## Section 6: Swarm tasks for argos service

| Task | Node | State | Info |
|------|------|-------|------|
| argos-swarm_argos.1 | Hermes | Running 13h ago | **[INFO]** |
| argos-swarm_argos.1 | Beasty | Failed 13h ago | "unhealthy container" |
| argos-swarm_argos.1 | Beasty | Shutdown 14h ago | |
| argos-swarm_argos.2 | Beasty | Running 14h ago | **[INFO]** |
| argos-swarm_argos.2 | Hermes | Shutdown 14h ago | |

**[INFO]** Tasks Running pe ambele noduri. Un failure "unhealthy container" pe Beasty acum 13h dar recovered.

---

## Section 7: Service constraints

```json
{"Platforms":[{"Architecture":"amd64","OS":"linux"}]}
Image: 11.11.11.111:5000/argos:latest@sha256:4ba48e511513...
```

---

## Section 8: PostgreSQL local

| Metric | Value |
|--------|-------|
| Version | PostgreSQL 17.9 (Debian) |
| Size | 21 MB |
| Active connections | 17 |

**[INFO]** Connections normale (17 < 50).

---

## Section 9: PostgreSQL replication

| Metric | Value |
|--------|-------|
| Replication slots | 0 |
| pg_stat_replication | (0 rows) |
| wal_level | replica |
| max_wal_senders | 10 |
| max_replication_slots | 10 |
| hot_standby | on |

**[INFO]** WAL config e pregatita pentru replication (`wal_level=replica`) dar nu exista slots active. Consistent cu `argos_db_standby_active=false` din settings (task 04).

---

## Section 10: HAProxy

| Metric | Value |
|--------|-------|
| haproxy status | **active** |
| Listen port 5433 | YES |
| Listen port 666 | YES (dockerd) |

**[INFO]** HAProxy activ pe Hermes, listening pe 5433 pentru DB proxy. Consistent cu `argos_db_access_via=haproxy:5433`.

---

## Section 11: Ollama instances

### Native Ollama (port 11435)
| Model | Size |
|-------|------|
| DeepSeek-R1-0528-Qwen3-8B-GGUF:Q4_K_M | 4.7 GB |
| nomic-embed-text:latest | 0.3 GB |
| qwen3:14b | 8.6 GB |

### Container Ollama (port 11434)
| Model | Size |
|-------|------|
| qwen3:14b | 8.6 GB |
| llama3.1:8b | 4.6 GB |
| qwen2.5:14b | 8.4 GB |

**[INFO]** Ambele instante Ollama raspund. qwen3:14b disponibil (conform CLAUDE.md).

---

## Section 12: Hermes connectivity

| Test | Result |
|------|--------|
| ping | 2/2 received, 0% loss |
| SSH root@11.11.11.98 | PONG, hostname=Hermes |
| uptime | 3 days, 9:17, load 0.06 |

**[INFO]** Hermes online si accesibil.

---

## Section 13: HERMES HEARTBEAT INVESTIGATION (CRITICAL)

### systemctl status argos-heartbeat.service on Hermes

```
○ argos-heartbeat.service - ARGOS Heartbeat Daemon
     Loaded: loaded (/etc/systemd/system/argos-heartbeat.service; enabled; preset: enabled)
     Active: inactive (dead)

Apr 11 10:57:17 Hermes systemd[1]: Dependency failed for argos-heartbeat.service
Apr 11 10:57:17 Hermes systemd[1]: argos-heartbeat.service: Job start failed with result 'dependency'
```

### is-active / is-enabled
- **is-active:** FAIL (inactive)
- **is-enabled:** enabled

### journalctl -u argos-heartbeat.service (last 20)

| Timestamp | Event |
|-----------|-------|
| Apr 08 05:43:25 | Stopped argos-heartbeat.service |
| Apr 08 06:01:40 | Started argos-heartbeat.service |
| Apr 08 06:01:46 | [HEARTBEAT] Starting on hermes |
| Apr 08 06:01:47 | [HEARTBEAT] DB connected |
| Apr 08 16:04:49 | **[HEARTBEAT] DB write failed** |
| Apr 08 16:04:59 | [HEARTBEAT] DB connected |
| Apr 08 16:05:06 | **[HEARTBEAT] DB write failed** |
| Apr 08 16:05:14 | [HEARTBEAT] DB connected |
| Apr 08 16:05:37 | **[HEARTBEAT] DB write failed** |
| Apr 08 16:06:39 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:07:41 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:08:43 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:09:31 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:09:33 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:09:35 | **[HEARTBEAT] HB002 DB unreachable** |
| Apr 08 16:09:37 | [HEARTBEAT] DB connected |
| Apr 08 17:35:49 | **[HEARTBEAT] DB write failed** |
| Apr 08 17:36:03 | [HEARTBEAT] DB connected |
| -- Boot -- | |
| Apr 11 10:57:17 | **Dependency failed for argos-heartbeat.service** |
| Apr 11 10:57:17 | **Job start failed with result 'dependency'** |

### Analiza

1. **Serviciul exista:** DA, in /etc/systemd/system/
2. **Este enabled:** DA (auto start dupa reboot)
3. **Este activ:** **NU - inactive (dead)**
4. **Ultima rulare:** 08 aprilie 2026, pana la ~17:36
5. **Eroare:** Pe 08 aprilie a avut probleme repetate de DB connectivity (HB002 DB unreachable). Dupa reboot pe 11 aprilie, serviciul nu a pornit din cauza "dependency failed".

### Root Cause
- Pe 8 aprilie, heartbeat daemon a avut probleme de conexiune la DB (probabil network glitch sau DB restart)
- Serviciul a continuat sa ruleze dar nu a mai putut scrie
- La reboot pe 11 aprilie, o dependenta a serviciului nu era disponibila
- Serviciul a ramas **inactive (dead)** de atunci
- **Nimeni nu a observat** ca Hermes heartbeat e mort de 6+ zile

**[CRITICAL]** Service enabled dar inactive/dead. Dependency failure la boot nerezolvat.

---

## Section 14: Beasty heartbeat (control)

| Metric | Value |
|--------|-------|
| is-active | **active** |
| is-enabled | **enabled** |

### Last 10 journal lines (Beasty)

| Timestamp | Event |
|-----------|-------|
| Apr 13 12:47:00 | Stopped ARGOS Heartbeat Daemon |
| Apr 13 12:49:29 | Started ARGOS Heartbeat Daemon |
| Apr 13 12:49:29 | [HEARTBEAT] Starting on beasty |
| Apr 13 12:49:29 | [HEARTBEAT] DB connected |
| Apr 13 12:49:29 | [HEARTBEAT] DB write failed: relation "heartbeat_log" does not exist |
| Apr 13 12:49:31 | [HEARTBEAT] DB connected |
| Apr 13 12:49:32 | [HEARTBEAT] DB write failed: relation "heartbeat_log" does not exist |

**Observatie:** Beasty heartbeat e activ dar a avut erori "relation heartbeat_log does not exist" pe 13 aprilie. Probabil tabela a fost recreata ulterior.

**Comparatie:** Beasty OK, Hermes DEAD. Problema este **DOAR pe Hermes**.

---

## Section 15: All argos systemd units on Beasty

| Unit | State | Status |
|------|-------|--------|
| argos-defcon.service | loaded active | running |
| argos-heartbeat.service | loaded active | running |
| argos-rsync.service | loaded inactive | dead (timer-driven) |
| argos-score-decay.service | loaded inactive | dead (timer-driven) |
| argos-watchdog.service | loaded active | running |
| argos-rsync.timer | loaded active | waiting |
| argos-score-decay.timer | loaded active | waiting |

**[INFO]** Toate unitatile active care ar trebui sa ruleze permanent sunt running.

---

## Section 16: Disk usage

| Filesystem | Size | Used | Avail | Use% | Mount | Severity |
|------------|------|------|-------|------|-------|----------|
| /dev/nvme0n1p2 | 1.8T | 1.1T | 621G | 65% | / | **[INFO]** |
| /dev/sdb1 | 3.6T | 2.7T | 752G | 79% | /movies | **[MEDIUM]** |
| /dev/sdc1 | 3.6T | 482G | 3.0T | 14% | /4t | **[INFO]** |
| /dev/sda1 | 7.3T | 538G | 6.4T | 8% | /run/media/... | **[INFO]** |
| /dev/nvme0n1p1 | 1022M | 39M | 984M | 4% | /boot | **[INFO]** |

**[MEDIUM]** /movies la 79% - monitorizare dar nu critic.

---

## Section 17: Network connectivity to nodes

| Node | IP | Status |
|------|-----|--------|
| Beasty (self) | 11.11.11.111 | **OK** |
| Hermes | 11.11.11.98 | **OK** |
| Zeus | 11.11.11.11 | **OK** |
| HA primary | 11.11.11.201 | **OK** |
| Vikunja | 11.11.11.53 | **OK** |
| n8n | 11.11.11.95 | **OK** |
| LightRAG | 11.11.11.74 | **OK** |

**[INFO]** Toate nodurile accesibile.

---

## Section 18: Listening ports

| Port | Service | Status |
|------|---------|--------|
| 666 | ARGOS UI | **OK** |
| 5432 | PostgreSQL direct | **OK** |
| 5433 | PostgreSQL via HAProxy | **OK** |
| 11434 | Ollama container | **OK** |
| 11435 | Ollama native | **OK** |
| 5000 | Registry | **OK** |
| 3000 | Open WebUI | **OK** |

**[INFO]** Toate porturile asteptate sunt prezente.

---

## Section 19: DB heartbeat age cross-ref

| Node | Last Heartbeat | Age |
|------|----------------|-----|
| beasty | 2026-04-15 00:13:42 | 0 seconds |
| hermes | 2026-04-08 21:35:24 | **6 days 02:38:18** |

**[CRITICAL]** Confirmare task 04: Hermes heartbeat e vechi de 6+ zile. Beasty e current.

---

## Section 20: Recent journalctl errors (last 1h)

**Lines matching "error\|fail\|crit":** 24

Toate sunt PostgreSQL checkpoint LOG entries (nu erori reale):
```
checkpoint starting: time
checkpoint complete: wrote 16 buffers
```

**[INFO]** Zero erori reale in ultima ora. Checkpoint-urile sunt normale.

---

## Section 21: Argos state settings cross-ref

| Setting | Value | Reality | Status |
|---------|-------|---------|--------|
| argos_beasty_active | true | Beasty has running task | **OK** |
| argos_hermes_active | true | Hermes has running task | **OK** |
| argos_heartbeat_daemon_beasty | true | Service active | **OK** |
| argos_heartbeat_daemon_hermes | true | **Service inactive!** | **[CRITICAL] CONFLICT** |
| argos_swarm_leader | hermes | SSH OK, services listed | **OK** |
| argos_swarm_mode | true | Swarm active, 2/2 replicas | **OK** |
| argos_swarm_replicas | 2 | 2/2 confirmed | **OK** |
| argos_db_standby_active | false | 0 replication slots | **OK** |
| argos_db_access_via | haproxy:5433 | HAProxy active pe 5433 | **OK** |

**[CRITICAL]** `argos_heartbeat_daemon_hermes=true` dar serviciul e inactive. Settings nu reflecta realitatea.

---

## Section 22: Top 15 findings cross-cutting

1. **[CRITICAL]** Hermes heartbeat service inactive (dead) de 6+ zile - dependency failed la boot
2. **[CRITICAL]** CONFLICT: settings `argos_heartbeat_daemon_hermes=true` dar service e mort
3. **[CRITICAL]** Dependency failure pe Hermes nerezolvat din 11 aprilie
4. **[INFO]** Swarm healthy: 2/2 replicas running pe Beasty si Hermes
5. **[INFO]** PostgreSQL operational: 17 connections, 21 MB size
6. **[INFO]** HAProxy active pe Hermes, consistent cu settings
7. **[INFO]** Toate nodurile network accessible (Hermes, Zeus, HA, etc.)
8. **[INFO]** Beasty heartbeat active si writing to DB
9. **[INFO]** Ollama (both instances) operational cu qwen3:14b
10. **[INFO]** Toate porturile expected sunt listening
11. **[INFO]** Disk usage sub 80% pe partitii critice
12. **[INFO]** WAL config ready for replication (wal_level=replica)
13. **[INFO]** No replication slots - consistent cu argos_db_standby_active=false
14. **[INFO]** Zero erori reale in journalctl ultima ora
15. **[MEDIUM]** /movies la 79% usage - monitorizare

---

## Section 23: Observatii colaterale

- **[FOR-TASK-99 SYNTHESIS]** Pattern cross-cutting: settings DB nu reflecta realitatea infra. Hermes heartbeat e configurat "true" dar serviciul e mort. Necesita mechanism de sync sau health check care updateaza settings automat.

- **[FOR-TASK-99 SYNTHESIS]** Dependency failure la boot pe Hermes sugereaza ca systemd unit file are o dependenta care nu e intotdeauna disponibila la boot time. Posibil network.target sau docker.service ordering issue.

- **[FOR-TASK-05 AGENT LOOP]** Agent sessions 6-9 au failed in perioada 8-14 aprilie. Hermes heartbeat a murit pe 8 aprilie. Timing coincide dar cauzalitatea nu e directa (agent loop nu depinde de heartbeat pentru execution).

- **[FOR-TASK-04 DATABASE]** Beasty heartbeat a avut erori "relation heartbeat_log does not exist" pe 13 aprilie - probabil schema migration sau recreare tabela.

---

## Section 24: VERDICT FINAL ipoteza task 04+05

> "Este Hermes heartbeat dead cauza failure cluster sessions id 6-9 din task 05?"

### VERDICT: **PARTIALLY CONFIRMED**

### Evidence:

**PRO (Hermes heartbeat e mort):**
- Hermes heartbeat daemon e inactive din 8 aprilie 17:36
- A avut probleme de DB connectivity (HB002 DB unreachable) pe 8 aprilie
- Nu a restartat la boot pe 11 aprilie (dependency failed)
- Settings zice ca ar trebui sa ruleze (`argos_heartbeat_daemon_hermes=true`)

**CONTRA (nu e cauza directa a session failures):**
- Agent sessions ruleaza prin API (swarm service) nu prin heartbeat daemon
- Swarm-ul e healthy cu 2/2 replicas
- Agent loop nu depinde de heartbeat_log pentru decision making (bazat pe task 05)
- Sessions pot rula fara ca Hermes heartbeat sa scrie in DB

**CONCLUZIE:**
Hermes heartbeat mort este o **problema reala de infrastructure** dar **nu este cauza directa** a agent session failures. Session failures 6-9 sunt mai probabil cauzate de:
1. Bug in agent loop (vezi task 05: nested depth 9, 748 lines function)
2. Probleme in verification chain
3. API issues (session 9 failed in 3s la iteration 0)

Heartbeat-ul mort este un **simptom** al instabilitatii din 8 aprilie, nu cauza.

---

## Section 25: Recomandari prioritare

1. **FIX URGENT: Restart Hermes heartbeat** - `ssh root@hermes systemctl start argos-heartbeat.service` si investigheaza dependency failure

2. **Update settings** - seteaza `argos_heartbeat_daemon_hermes=false` temporar pana cand serviciul e fixat, pentru consistency

3. **Fix dependency in systemd unit** - verifica ce dependenta lipseste la boot (After=network-online.target? docker.service?)

4. **Add monitoring alert** - heartbeat_log fara entries > 5 min ar trebui sa trigger alert

5. **Investigate session 9 failure** - failed la iteration 0 in 3s, independent de heartbeat, probabil API/validation error

---

## Section 26: Metadata

- **Timp rulare:** ~8 secunde
- **Comanda:** `python3 /home/darkangel/.argos/argos-core/tools/audit/scripts/07_infrastructure.py`
- **Linii output:** ~200
- **Erori:** 0
- **SSH calls:** 4 (Hermes)
- **Comenzi adhoc:** 0
