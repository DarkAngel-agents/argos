"""
SSH host-key verification helper (audit N10).

asyncssh's `known_hosts=None` disables host-key verification entirely — same
class of vulnerability as `StrictHostKeyChecking=no` for the OpenSSH CLI. This
module centralises the host-key policy so every asyncssh.connect call across
the API uses the same logic:

  1. If ARGOS_SSH_VERIFY_HOSTS=0, return None (explicit operator opt-out).
  2. Else, prefer the user's ~/.ssh/known_hosts file. asyncssh will verify
     remote keys against it; unknown hosts cause the connection to fail.
  3. If known_hosts file is missing, fall back to None and log a one-time
     warning so the operator knows verification is degraded.

The tradeoff is operator-visible: to enable verification, run
    ssh-keyscan -H <host> >> ~/.ssh/known_hosts
once per fleet host (or use `ssh <host> exit` interactively to populate it).
"""
import os

_warned = False


def known_hosts():
    """Return the value to pass as `known_hosts=` to asyncssh.connect()."""
    global _warned
    if os.getenv("ARGOS_SSH_VERIFY_HOSTS", "1") == "0":
        return None
    kh = os.path.expanduser("~/.ssh/known_hosts")
    if os.path.exists(kh) and os.path.getsize(kh) > 0:
        return kh
    if not _warned:
        print(
            "[SEC N10] ~/.ssh/known_hosts missing or empty — host-key "
            "verification degraded to None. Populate with `ssh-keyscan -H "
            "<host> >> ~/.ssh/known_hosts` for each fleet host.",
            flush=True,
        )
        _warned = True
    return None
