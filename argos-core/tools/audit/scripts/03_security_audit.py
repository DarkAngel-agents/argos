"""
TASK 03 - Security & credentials audit

Read-only. Scan for:
- Hardcoded credentials in code (passwords, API keys, tokens)
- File permissions on sensitive files (.env, .key, .pgpass)
- SSH keys exposure
- Secrets in git history (if .git exists)
- Print statements that could leak credentials
- World-readable credential files
- Permissions on config/.env

NEVER prints actual credential values. Always masks.
"""
import ast
import os
import re
import stat
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import header, section, truncate, ARGOS_CORE

ARGOS_ROOT = "/home/darkangel/.argos"
CODE_SUBDIRS = ["agent", "api", "llm", "tools"]

# Suspicious key patterns - we detect presence, never value
CREDENTIAL_PATTERNS = [
    (r'[\'"]sk-ant-[a-zA-Z0-9_\-]{10,}', "Anthropic API key"),
    (r'[\'"]sk-proj-[a-zA-Z0-9_\-]{10,}', "OpenAI API key"),
    (r'[\'"]xai-[a-zA-Z0-9]{10,}', "xAI/Grok API key"),
    (r'[\'"]ghp_[a-zA-Z0-9]{20,}', "GitHub personal token"),
    (r'[\'"]gho_[a-zA-Z0-9]{20,}', "GitHub OAuth token"),
    (r'[\'"]glpat-[a-zA-Z0-9_\-]{10,}', "GitLab token"),
    (r'[\'"]xox[bp]-[a-zA-Z0-9\-]{10,}', "Slack token"),
    (r'AWS_SECRET_ACCESS_KEY\s*=\s*[\'"][^\'"]{20,}', "AWS secret"),
    (r'["\']AKIA[0-9A-Z]{16}["\']', "AWS access key"),
    (r'-----BEGIN [A-Z ]*PRIVATE KEY-----', "Private key in file"),
    (r'Haunc@?\d*', "Known password pattern"),
]

# Patterns for hardcoded passwords in code
PASSWORD_ASSIGN_PATTERNS = [
    re.compile(r'(password|passwd|pwd|secret)\s*=\s*["\'][^"\'\s]{4,}["\']', re.IGNORECASE),
    re.compile(r'(api_key|apikey|token|auth_token)\s*=\s*["\'][^"\'\s]{10,}["\']', re.IGNORECASE),
]

# Files names that commonly hold secrets
SENSITIVE_FILE_PATTERNS = [
    ".env", ".env.local", ".env.prod", ".env.production",
    ".pgpass", ".netrc", ".npmrc",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    "credentials", "credentials.json", "service-account.json",
    "secrets.yml", "secrets.yaml", "secret.key",
]


def find_py_files(base):
    out = []
    for root, dirs, files in os.walk(base):
        if "__pycache__" in root or "/audit/" in root or "/.git/" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return sorted(out)


def read_file(path):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except:
        return ""


def mask_match(text, max_show=10):
    """Mask a credential match - show only length and first/last chars."""
    if len(text) <= 6:
        return "***"
    return text[:3] + "..." + text[-3:] + " (len=" + str(len(text)) + ")"


def scan_credentials_in_file(content, path):
    """Scan file content for credential patterns. Returns findings without actual values."""
    findings = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for pattern_re, pattern_name in CREDENTIAL_PATTERNS:
            if re.search(pattern_re, line):
                findings.append((i, pattern_name, truncate(stripped[:40], 40)))
                break
    return findings


def scan_password_assigns(content):
    """Scan for hardcoded password=X assignments in code."""
    findings = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Skip getenv patterns (those are fine)
        if "getenv" in line or "environ" in line or "os.environ" in line:
            continue
        for pattern in PASSWORD_ASSIGN_PATTERNS:
            m = pattern.search(line)
            if m:
                key = m.group(1)
                # Mask the value portion
                masked_line = re.sub(
                    r'(["\'])[^"\']+(["\'])',
                    lambda x: x.group(1) + "***MASKED***" + x.group(2),
                    line
                )
                findings.append((i, key, truncate(masked_line.strip(), 90)))
                break
    return findings[:20]


def scan_print_credentials(content):
    """Scan for print statements that might leak credentials."""
    findings = []
    suspicious_keywords = ["password", "secret", "token", "api_key", "credential", "passwd", "pwd"]
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "print(" in stripped or "logger." in stripped:
            for kw in suspicious_keywords:
                if kw in stripped.lower():
                    findings.append((i, kw, truncate(stripped, 90)))
                    break
    return findings[:15]


def check_file_permissions(path):
    """Return mode in octal + world-readable flag."""
    try:
        st = os.stat(path)
        mode = oct(st.st_mode & 0o777)
        world_readable = bool(st.st_mode & stat.S_IROTH)
        world_writable = bool(st.st_mode & stat.S_IWOTH)
        return mode, world_readable, world_writable
    except:
        return None, None, None


def find_sensitive_files(base):
    """Find files that commonly hold secrets."""
    found = []
    try:
        for root, dirs, files in os.walk(base):
            if "/.git/" in root or "__pycache__" in root:
                continue
            for f in files:
                # Exact match or suffix match
                for pat in SENSITIVE_FILE_PATTERNS:
                    if f == pat or f.startswith(pat + ".") or f.endswith("." + pat):
                        full = os.path.join(root, f)
                        found.append(full)
                        break
    except:
        pass
    return sorted(set(found))


def main():
    header("TASK 03 - Security & credentials audit")

    # ============================================================
    # 3.1 Gather file list
    # ============================================================
    all_files = []
    for d in CODE_SUBDIRS:
        base = os.path.join(ARGOS_CORE, d)
        if os.path.exists(base):
            all_files.extend(find_py_files(base))

    section("3.1 Scope")
    print("  Python files scanned: " + str(len(all_files)))
    print("  Subdirs: " + ", ".join(CODE_SUBDIRS))
    print("  Argos root: " + ARGOS_ROOT)

    # ============================================================
    # 3.2 Credential patterns in source code
    # ============================================================
    section("3.2 Credential patterns detected in .py files")
    cred_findings = defaultdict(list)
    total_creds = 0
    for f in all_files:
        content = read_file(f)
        findings = scan_credentials_in_file(content, f)
        if findings:
            cred_findings[f] = findings
            total_creds += len(findings)

    print("  Total matches: " + str(total_creds))
    print()
    if cred_findings:
        for f, findings in sorted(cred_findings.items()):
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel + " (" + str(len(findings)) + ")")
            for line_no, pattern_name, preview in findings:
                print("    L" + str(line_no) + " [" + pattern_name + "]")
    else:
        print("  [NONE] No credential patterns detected in source code")

    # ============================================================
    # 3.3 Hardcoded password=X assignments
    # ============================================================
    section("3.3 Hardcoded password/secret assignments in code")
    pwd_count = 0
    pwd_findings = defaultdict(list)
    for f in all_files:
        content = read_file(f)
        findings = scan_password_assigns(content)
        if findings:
            pwd_findings[f] = findings
            pwd_count += len(findings)

    print("  Total hardcoded assignments (non-env): " + str(pwd_count))
    print()
    if pwd_findings:
        for f, findings in sorted(pwd_findings.items()):
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel + " (" + str(len(findings)) + ")")
            for line_no, key, text in findings:
                print("    L" + str(line_no) + " [" + key + "]: " + text)
    else:
        print("  [NONE] No hardcoded credential assignments detected")

    # ============================================================
    # 3.4 Prints / logs that might leak credentials
    # ============================================================
    section("3.4 Print / log statements near credential keywords")
    leak_count = 0
    leak_findings = defaultdict(list)
    for f in all_files:
        content = read_file(f)
        findings = scan_print_credentials(content)
        if findings:
            leak_findings[f] = findings
            leak_count += len(findings)

    print("  Total suspicious prints: " + str(leak_count))
    print()
    if leak_findings:
        for f, findings in sorted(leak_findings.items()):
            rel = f.replace(ARGOS_CORE + "/", "")
            print("  " + rel + " (" + str(len(findings)) + ")")
            for line_no, keyword, text in findings[:5]:
                print("    L" + str(line_no) + " [" + keyword + "]: " + text)
    else:
        print("  [NONE] No suspicious print/log statements")

    # ============================================================
    # 3.5 Sensitive files on disk + permissions
    # ============================================================
    section("3.5 Sensitive files on disk (under argos root)")
    sensitive = find_sensitive_files(ARGOS_ROOT)
    print("  Total found: " + str(len(sensitive)))
    print()
    for path in sensitive:
        mode, wr, ww = check_file_permissions(path)
        severity = ""
        if ww:
            severity = " [CRITICAL world-writable]"
        elif wr:
            severity = " [HIGH world-readable]"
        elif mode and mode not in ("0o600", "0o400"):
            severity = " [MEDIUM non-strict mode]"
        print("  " + path)
        print("    mode=" + str(mode) + severity)

    # ============================================================
    # 3.6 config/.env specific check
    # ============================================================
    section("3.6 config/.env permissions + content overview")
    env_path = ARGOS_CORE + "/config/.env"
    if os.path.exists(env_path):
        mode, wr, ww = check_file_permissions(env_path)
        print("  path: " + env_path)
        print("  mode: " + str(mode))
        print("  world-readable: " + str(wr))
        print("  world-writable: " + str(ww))
        if wr:
            print("  [CRITICAL] config/.env is world-readable!")
        if mode not in ("0o600", "0o400"):
            print("  [HIGH] config/.env should be 0600, currently " + str(mode))

        # Count lines and keys without showing values
        try:
            with open(env_path) as f:
                lines = f.readlines()
            keys = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k = line.split("=", 1)[0]
                    keys.append(k)
            print("  total lines: " + str(len(lines)))
            print("  keys defined: " + str(len(keys)))
            print("  keys: " + ", ".join(keys))
        except Exception as e:
            print("  read error: " + str(e))
    else:
        print("  [MISSING] config/.env does not exist!")

    # Check if there's a .env in argos-core root (should NOT exist, only config/.env)
    root_env = ARGOS_CORE + "/.env"
    if os.path.exists(root_env):
        mode, wr, ww = check_file_permissions(root_env)
        print()
        print("  [WARNING] Secondary .env found at " + root_env)
        print("    mode=" + str(mode))
        print("    This is duplicate or leftover - check if used anywhere")

    # ============================================================
    # 3.7 Backup files that might contain secrets
    # ============================================================
    section("3.7 Backup files (.bak, .backup, .old) that might leak secrets")
    backup_files = []
    try:
        result = subprocess.run(
            ["find", ARGOS_ROOT, "-type", "f", "(", 
             "-name", "*.bak", "-o", 
             "-name", "*.bak-*", "-o",
             "-name", "*.backup", "-o", 
             "-name", "*.old", 
             ")",
             "-not", "-path", "*/.git/*",
             "-not", "-path", "*__pycache__*"],
            capture_output=True, text=True, timeout=15
        )
        backup_files = [l for l in result.stdout.split("\n") if l.strip()]
    except Exception as e:
        print("  ERR: " + str(e))

    print("  Total backup files: " + str(len(backup_files)))
    print()
    env_backups = [f for f in backup_files if ".env" in f.lower()]
    if env_backups:
        print("  [HIGH] .env backups found (may contain credentials):")
        for f in env_backups:
            mode, wr, ww = check_file_permissions(f)
            marker = " [WORLD-READABLE]" if wr else ""
            print("    " + f + " mode=" + str(mode) + marker)
    other_backups = [f for f in backup_files if ".env" not in f.lower()]
    if other_backups:
        print()
        print("  Other backup files (first 10):")
        for f in other_backups[:10]:
            print("    " + f)
        if len(other_backups) > 10:
            print("    ... and " + str(len(other_backups) - 10) + " more")

    # ============================================================
    # 3.8 .ssh directory check
    # ============================================================
    section("3.8 SSH directory + keys")
    ssh_dir = "/home/darkangel/.ssh"
    if os.path.exists(ssh_dir):
        mode, wr, ww = check_file_permissions(ssh_dir)
        print("  " + ssh_dir + " mode=" + str(mode) + (" [HIGH world-readable]" if wr else ""))
        try:
            for f in sorted(os.listdir(ssh_dir)):
                full = os.path.join(ssh_dir, f)
                if os.path.isfile(full):
                    fmode, fwr, fww = check_file_permissions(full)
                    severity = ""
                    is_private = any(f.startswith(p) for p in ["id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"]) and not f.endswith(".pub")
                    if is_private and fmode not in ("0o600", "0o400"):
                        severity = " [CRITICAL private key mode should be 600]"
                    elif fwr and is_private:
                        severity = " [CRITICAL private key world-readable]"
                    print("    " + f + " mode=" + str(fmode) + severity)
        except Exception as e:
            print("  ERR listing: " + str(e))
    else:
        print("  [INFO] " + ssh_dir + " not accessible from container (normal, bind-mounted ro maybe)")

    # ============================================================
    # 3.9 Git history check (if .git exists)
    # ============================================================
    section("3.9 Git repo check")
    git_dir = ARGOS_CORE + "/.git"
    if os.path.exists(git_dir):
        print("  .git found at " + git_dir)
        try:
            # Check if there's a .gitignore and what it ignores
            gi = ARGOS_CORE + "/.gitignore"
            if os.path.exists(gi):
                with open(gi) as f:
                    content = f.read()
                print("  .gitignore present (" + str(len(content.splitlines())) + " lines)")
                # Check if .env is in gitignore
                if ".env" in content:
                    print("    [OK] .env listed in .gitignore")
                else:
                    print("    [CRITICAL] .env NOT listed in .gitignore!")
                if "*.key" in content or "id_rsa" in content:
                    print("    [OK] keys mentioned in .gitignore")
            else:
                print("  [HIGH] No .gitignore found")
        except Exception as e:
            print("  ERR: " + str(e))
    else:
        print("  [INFO] No .git directory (not a git repo or different location)")

    # Also check argos root
    git_dir2 = ARGOS_ROOT + "/.git"
    if os.path.exists(git_dir2):
        print()
        print("  .git also found at " + git_dir2)

    # ============================================================
    # 3.10 Dangerous subprocess patterns
    # ============================================================
    section("3.10 shell=True usage (potential command injection)")
    shell_count = 0
    for f in all_files:
        content = read_file(f)
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "shell=True" in line:
                rel = f.replace(ARGOS_CORE + "/", "")
                print("  " + rel + " L" + str(i) + ": " + truncate(stripped, 90))
                shell_count += 1
    if shell_count == 0:
        print("  [OK] No shell=True usage detected")

    # ============================================================
    # 3.11 eval / exec usage
    # ============================================================
    section("3.11 eval() / exec() usage (code execution risk)")
    eval_count = 0
    eval_pattern = re.compile(r"\b(eval|exec)\s*\(")
    for f in all_files:
        content = read_file(f)
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            m = eval_pattern.search(line)
            if m:
                rel = f.replace(ARGOS_CORE + "/", "")
                print("  " + rel + " L" + str(i) + " [" + m.group(1) + "]: " + truncate(stripped, 90))
                eval_count += 1
    if eval_count == 0:
        print("  [OK] No eval/exec usage detected")

    print()
    print("=" * 70)
    print(" END TASK 03 RECON")
    print("=" * 70)


main()
