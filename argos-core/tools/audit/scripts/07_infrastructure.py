"""
TASK 07 - Infrastructure investigation

Read-only. Runs ON HOST Beasty (NOT in container), uses local subprocess for:
- Docker swarm health (services, tasks, replicas)
- PostgreSQL + replication status
- HAProxy config + status
- Systemd services (argos-*, postgresql, docker)
- Ollama instances (11434, 11435)
- Hermes connectivity + heartbeat investigation
- File system mounts + disk usage
- Network connectivity to nodes

Some queries also hit DB via docker exec (because asyncpg only in container).
"""
import os
import re
import subprocess
import sys
import json
from collections import defaultdict


def run(cmd, timeout=15, shell=False):
    """Run command, return (returncode, stdout, stderr). Never raises."""
    try:
        if shell:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def header(title):
    print()
    print("=" * 70)
    print(" " + title)
    print("=" * 70)


def section(title):
    print()
    print("--- " + title + " ---")


def truncate(s, n=100):
    if s is None:
        return "None"
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n-3] + "..."


def section_01_node_identity():
    section("7.1 Node identity")
    rc, out, err = run(["hostname"])
    print("  hostname: " + out.strip())

    rc, out, err = run(["uname", "-a"])
    print("  uname:    " + truncate(out.strip(), 100))

    rc, out, err = run(["whoami"])
    print("  user:     " + out.strip())

    rc, out, err = run(["uptime"])
    print("  uptime:   " + truncate(out.strip(), 100))


def section_02_docker_basics():
    section("7.2 Docker basics on this node")
    rc, out, err = run(["docker", "version", "--format", "{{.Server.Version}}"])
    print("  docker server: " + (out.strip() if rc == 0 else "ERR " + err[:80]))

    rc, out, err = run(["docker", "info", "--format", "{{.Swarm.LocalNodeState}} | {{.Swarm.NodeID}}"])
    print("  swarm state:   " + (out.strip() if rc == 0 else "ERR " + err[:80]))

    rc, out, err = run(["docker", "node", "ls"])
    if rc == 0:
        print("  node ls:")
        for line in out.strip().splitlines():
            print("    " + line)
    else:
        print("  node ls: ERR (this is worker, run on manager)")


def section_03_argos_containers_local():
    section("7.3 Argos containers running on THIS node")
    rc, out, err = run(["docker", "ps", "--filter", "name=argos", "--format",
                        "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}"])
    if rc != 0:
        print("  ERR: " + err[:200])
        return

    for line in out.strip().splitlines():
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            cid, name, status, image, ports = parts[0], parts[1], parts[2], parts[3], parts[4]
            print("  " + cid[:12] + "  " + truncate(name, 40))
            print("    status: " + status)
            print("    image:  " + truncate(image, 80))
            print("    ports:  " + truncate(ports, 80))


def section_04_swarm_services_via_hermes():
    section("7.4 Swarm services (via Hermes manager)")
    # Try ssh root@hermes
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98", "docker service ls"], timeout=20)
    if rc == 0:
        print("  [SSH OK to root@11.11.11.98]")
        for line in out.strip().splitlines():
            print("  " + line)
    else:
        print("  [SSH FAIL] returncode=" + str(rc))
        print("  stderr: " + truncate(err, 200))


def section_05_swarm_tasks_argos():
    section("7.5 Swarm tasks for argos service")
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98",
                        "docker service ps argos-swarm_argos --no-trunc --format '{{.Name}} | {{.Node}} | {{.CurrentState}} | {{.Error}}' | head -20"],
                       timeout=20)
    if rc == 0:
        for line in out.strip().splitlines():
            print("  " + line)
    else:
        print("  [SSH FAIL] " + truncate(err, 200))


def section_06_swarm_service_inspect():
    section("7.6 Swarm service constraints + image")
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98",
                        "docker service inspect argos-swarm_argos --format '{{json .Spec.TaskTemplate.Placement}} {{.Spec.TaskTemplate.ContainerSpec.Image}}'"],
                       timeout=20)
    if rc == 0:
        print("  " + truncate(out.strip(), 300))
    else:
        print("  [SSH FAIL]")


def section_07_postgres_local():
    section("7.7 PostgreSQL on Beasty (local container)")
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-c", "SELECT version();"])
    if rc == 0:
        for line in out.strip().splitlines():
            print("  " + line)
    else:
        print("  [ERR] cannot exec argos-db: " + truncate(err, 200))

    # DB size + activity
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-tA", "-c",
                        "SELECT pg_size_pretty(pg_database_size('claudedb')) || ' | ' || (SELECT COUNT(*) FROM pg_stat_activity WHERE datname='claudedb')"])
    if rc == 0:
        print("  size | active conns: " + out.strip())


def section_08_postgres_replication():
    section("7.8 PostgreSQL replication status")
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-c", "SELECT * FROM pg_stat_replication"])
    if rc == 0:
        if "(0 rows)" in out:
            print("  [INFO] No replication slots active")
        for line in out.strip().splitlines():
            print("  " + line)
    else:
        print("  [ERR] " + truncate(err, 200))

    # Check WAL settings
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-tA", "-c",
                        "SELECT name || '=' || setting FROM pg_settings WHERE name IN ('wal_level','max_wal_senders','max_replication_slots','hot_standby')"])
    if rc == 0:
        print()
        print("  WAL config:")
        for line in out.strip().splitlines():
            print("    " + line)


def section_09_haproxy_check():
    section("7.9 HAProxy on Hermes")
    # Check haproxy status via ssh
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98", "systemctl is-active haproxy"],
                       timeout=15)
    print("  haproxy active: " + (out.strip() if rc == 0 else "ERR"))

    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98", "ss -tlnp 2>/dev/null | grep -E ':5433|:6666|:666' | head -10"],
                       timeout=15)
    print()
    print("  HAProxy listening ports:")
    if rc == 0:
        for line in out.strip().splitlines():
            print("    " + line)


def section_10_ollama_local():
    section("7.10 Ollama instances")
    # Native ollama on port 11435
    rc, out, err = run(["curl", "-s", "--max-time", "5", "http://localhost:11435/api/tags"])
    if rc == 0 and out:
        try:
            data = json.loads(out)
            models = data.get("models", [])
            print("  Native Ollama (11435): " + str(len(models)) + " models")
            for m in models[:10]:
                name = m.get("name", "?")
                size = m.get("size", 0)
                size_gb = round(size / (1024**3), 1)
                print("    " + name.ljust(40) + " " + str(size_gb) + " GB")
        except:
            print("  Native Ollama (11435): non-json response")
    else:
        print("  Native Ollama (11435): UNREACHABLE")

    # Container ollama on 11434 (or whatever port)
    rc, out, err = run(["curl", "-s", "--max-time", "5", "http://localhost:11434/api/tags"])
    if rc == 0 and out:
        try:
            data = json.loads(out)
            models = data.get("models", [])
            print()
            print("  Container Ollama (11434): " + str(len(models)) + " models")
            for m in models[:10]:
                name = m.get("name", "?")
                size = m.get("size", 0)
                size_gb = round(size / (1024**3), 1)
                print("    " + name.ljust(40) + " " + str(size_gb) + " GB")
        except:
            print("  Container Ollama (11434): non-json")
    else:
        print("  Container Ollama (11434): UNREACHABLE")


def section_11_hermes_connectivity():
    section("7.11 Hermes connectivity tests")
    # Ping
    rc, out, err = run(["ping", "-c", "2", "-W", "2", "11.11.11.98"], timeout=10)
    if rc == 0:
        last_line = [l for l in out.splitlines() if "received" in l]
        print("  ping: " + (last_line[0] if last_line else "OK"))
    else:
        print("  ping: FAIL")

    # SSH basic
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98", "echo PONG && hostname && uptime"],
                       timeout=15)
    if rc == 0:
        print()
        print("  ssh root@11.11.11.98:")
        for line in out.strip().splitlines():
            print("    " + line)
    else:
        print("  ssh FAIL: " + truncate(err, 200))


def section_12_hermes_heartbeat_investigation():
    section("7.12 Hermes heartbeat investigation (CRITICAL)")
    print("  Goal: determine why heartbeat_log shows last entry from 2026-04-08")
    print()

    # Check if argos-heartbeat.service exists on hermes
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98",
                        "systemctl status argos-heartbeat.service 2>&1 | head -15"],
                       timeout=15)
    print("  systemctl status argos-heartbeat.service on Hermes:")
    if rc == 0:
        for line in out.strip().splitlines():
            print("    " + line)
    else:
        print("    [SSH FAIL] " + truncate(err, 200))

    print()
    # is-active
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98",
                        "systemctl is-active argos-heartbeat.service && systemctl is-enabled argos-heartbeat.service"],
                       timeout=15)
    print("  is-active / is-enabled:")
    if rc == 0:
        for line in out.strip().splitlines():
            print("    " + line)
    else:
        print("    [FAIL or service not present]")

    print()
    # Last journal entries
    rc, out, err = run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                        "root@11.11.11.98",
                        "journalctl -u argos-heartbeat.service -n 20 --no-pager 2>&1 | tail -25"],
                       timeout=20)
    print("  journalctl -u argos-heartbeat.service (last 20):")
    if rc == 0:
        for line in out.strip().splitlines():
            print("    " + truncate(line, 130))
    else:
        print("    [FAIL] " + truncate(err, 200))


def section_13_local_heartbeat_check():
    section("7.13 Beasty heartbeat (for comparison)")
    rc, out, err = run(["systemctl", "is-active", "argos-heartbeat.service"])
    print("  argos-heartbeat.service active: " + (out.strip() if rc == 0 else "FAIL"))

    rc, out, err = run(["systemctl", "is-enabled", "argos-heartbeat.service"])
    print("  argos-heartbeat.service enabled: " + (out.strip() if rc == 0 else "FAIL"))

    rc, out, err = run(["journalctl", "-u", "argos-heartbeat.service", "-n", "10", "--no-pager"], timeout=15)
    print()
    print("  Last 10 journal lines (Beasty):")
    if rc == 0:
        for line in out.strip().splitlines()[-10:]:
            print("    " + truncate(line, 130))
    else:
        print("    [FAIL] " + truncate(err, 150))


def section_14_systemd_argos_units():
    section("7.14 All argos-* systemd units on Beasty")
    rc, out, err = run(["systemctl", "list-units", "--all", "--no-pager", "--no-legend",
                        "argos-*"], timeout=15)
    if rc == 0:
        for line in out.strip().splitlines():
            print("  " + line)
    else:
        print("  [ERR] " + truncate(err, 150))


def section_15_disk_usage():
    section("7.15 Disk usage critical paths")
    rc, out, err = run(["df", "-h"], timeout=10)
    if rc == 0:
        for line in out.strip().splitlines()[:15]:
            print("  " + line)
    print()

    paths = [
        "/home/darkangel/.argos",
        "/var/lib/docker",
        "/var/lib/postgresql",
        "/var/log",
        "/8tb",
    ]
    print("  du -sh per critical path:")
    for p in paths:
        if os.path.exists(p):
            rc, out, err = run(["du", "-sh", p], timeout=20)
            if rc == 0:
                print("    " + out.strip())
            else:
                print("    " + p + " [ERR or perm denied]")


def section_16_network_connectivity():
    section("7.16 Network connectivity to other nodes")
    nodes = [
        ("Beasty (self)", "11.11.11.111"),
        ("Hermes",        "11.11.11.98"),
        ("Zeus",          "11.11.11.11"),
        ("HA primary",    "11.11.11.201"),
        ("Vikunja",       "11.11.11.53"),
        ("n8n",           "11.11.11.95"),
        ("LightRAG",      "11.11.11.74"),
    ]
    for name, ip in nodes:
        rc, out, err = run(["ping", "-c", "1", "-W", "2", ip], timeout=5)
        marker = "OK" if rc == 0 else "FAIL"
        print("  " + name.ljust(20) + " " + ip.ljust(15) + " " + marker)


def section_17_listening_ports():
    section("7.17 Listening ports on Beasty")
    rc, out, err = run(["ss", "-tlnp"], timeout=10)
    if rc != 0:
        print("  [ERR] " + truncate(err, 150))
        return

    relevant_ports = ["666", "5433", "5432", "8000", "8765", "11434", "11435", "5000", "3000", "8080"]
    print("  Relevant ports:")
    for line in out.strip().splitlines():
        for p in relevant_ports:
            if ":" + p + " " in line or ":" + p + "\t" in line:
                print("  " + truncate(line, 130))
                break


def section_18_db_heartbeat_age():
    section("7.18 DB heartbeat_log age check (cross-ref with 04)")
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-tA", "-c",
                        "SELECT node, MAX(ts) as last_seen, NOW() - MAX(ts) as age FROM heartbeat_log GROUP BY node ORDER BY last_seen DESC"])
    if rc == 0:
        print("  Per-node last heartbeat:")
        for line in out.strip().splitlines():
            print("    " + line)
    else:
        print("  [ERR] " + truncate(err, 200))


def section_19_recent_log_activity():
    section("7.19 Recent error patterns in journalctl (last 1h)")
    rc, out, err = run(["journalctl", "--since", "1 hour ago", "-p", "err", "--no-pager"], timeout=20)
    if rc == 0:
        lines = out.strip().splitlines()
        if not lines or "No entries" in out:
            print("  [INFO] No errors in last hour")
        else:
            print("  " + str(len(lines)) + " error lines in last hour")
            for line in lines[:15]:
                print("    " + truncate(line, 130))
    else:
        print("  [ERR] " + truncate(err, 150))


def section_20_argos_state_settings():
    section("7.20 Argos state from settings (cross-ref task 04)")
    rc, out, err = run(["docker", "exec", "argos-db", "psql", "-U", "claude", "-d", "claudedb",
                        "-tA", "-c",
                        "SELECT key || '=' || value FROM settings WHERE key LIKE 'argos_%' ORDER BY key"])
    if rc == 0:
        for line in out.strip().splitlines():
            print("  " + line)


def main():
    header("TASK 07 - Infrastructure investigation")

    section_01_node_identity()
    section_02_docker_basics()
    section_03_argos_containers_local()
    section_04_swarm_services_via_hermes()
    section_05_swarm_tasks_argos()
    section_06_swarm_service_inspect()
    section_07_postgres_local()
    section_08_postgres_replication()
    section_09_haproxy_check()
    section_10_ollama_local()
    section_11_hermes_connectivity()
    section_12_hermes_heartbeat_investigation()
    section_13_local_heartbeat_check()
    section_14_systemd_argos_units()
    section_15_disk_usage()
    section_16_network_connectivity()
    section_17_listening_ports()
    section_18_db_heartbeat_age()
    section_19_recent_log_activity()
    section_20_argos_state_settings()

    print()
    print("=" * 70)
    print(" END TASK 07 RECON")
    print("=" * 70)


main()
