"""
ARGOS Agent - Tool execution wrapper.

Thin wrapper around api.executor._exec_ssh_by_name that:
1. Measures execution duration in milliseconds.
2. Returns a standardized dict shape ready for evidence.append_command.
3. Catches import failures gracefully (executor.py changes shouldn't crash
   the agent loop at import time - fail at first use instead).

Does NOT do autonomy check - caller (loop.py) runs check_session_autonomy
first and only calls exec_tool if allowed.

Does NOT do KB/command_scores/tool_scores updates - those are chat.py
concerns and Session 3+ may integrate them via a shared helper module.
For Session 2 MVP, evidence.commands JSONB is the single source of truth
for what the agent ran and what came out.
"""
import time
import traceback
from typing import Optional


# Import _exec_ssh_by_name lazily at first call to avoid crashing the agent
# loop at module import time if executor.py is being edited or has an issue.
# The agent runs as a long-lived process and a transient import error at
# startup should not kill the whole session.
_exec_ssh_by_name = None
_known_hosts = None


class ToolExecutionError(Exception):
    """Raised on fatal tool execution failure (import error, unknown tool)."""
    pass


def _lazy_import_executor():
    """
    Import executor helpers lazily. Cached after first successful import.

    Raises ToolExecutionError on import failure with a clear message.
    """
    global _exec_ssh_by_name, _known_hosts
    if _exec_ssh_by_name is not None:
        return
    try:
        from api.executor import _exec_ssh_by_name as exec_fn
        from api.executor import KNOWN_HOSTS as hosts
        _exec_ssh_by_name = exec_fn
        _known_hosts = hosts
    except ImportError as e:
        raise ToolExecutionError(
            f"Failed to import api.executor: {e}. "
            "Agent loop cannot execute tools without executor module."
        ) from e


async def exec_tool(
    machine: str,
    command: str,
    timeout_override: Optional[int] = None,
) -> dict:
    """
    Execute a shell command on a target machine via executor._exec_ssh_by_name.

    Args:
        machine: target machine name from KNOWN_HOSTS (beasty, hermes, zeus,
                 master, claw) or IP address. Case-insensitive.
        command: raw command string to execute.
        timeout_override: optional timeout in seconds. Currently ignored
                          because executor._get_timeout decides based on
                          command pattern. Reserved for future use when
                          executor supports explicit timeout param.

    Returns:
        Standardized dict matching evidence.append_command expectations:
        {
            "cmd": str,           # original command as passed
            "machine": str,       # target machine
            "exit_code": int,     # 0 on success, non-zero on failure,
                                  # 255 on SSH errors, 124 on timeout
            "stdout": str,        # captured stdout, stripped
            "stderr": str,        # captured stderr, stripped
            "duration_ms": int,   # wall-clock execution time in ms
        }

    Does NOT raise on command failure - non-zero exit_code is a valid
    result captured in the dict. Raises ToolExecutionError only on
    infrastructure failures (executor import, internal exceptions).

    The ts field expected by evidence.append_command is NOT added here -
    evidence.py adds it at append time so the timestamp reflects when the
    record is persisted, not when the command started. Use duration_ms
    together with evidence row ts to reconstruct start time if needed.
    """
    _lazy_import_executor()

    start = time.monotonic()
    try:
        result = await _exec_ssh_by_name(machine, command)
    except Exception as e:
        # Wrap unexpected exceptions from executor into a failure result.
        # This keeps the agent loop running - a broken tool call becomes
        # a recorded failure, not a crashed session.
        # Include short traceback (last 3 frames) for post-mortem debug
        # without polluting evidence with huge stack traces.
        duration_ms = int((time.monotonic() - start) * 1000)
        tb_short = traceback.format_exc(limit=3)
        return {
            "cmd": command,
            "machine": machine,
            "exit_code": 255,
            "stdout": "",
            "stderr": f"executor exception: {type(e).__name__}: {e}\n{tb_short}",
            "duration_ms": duration_ms,
        }

    duration_ms = int((time.monotonic() - start) * 1000)

    # executor._exec_ssh_by_name returns {stdout, stderr, returncode}.
    # Normalize to our standard shape with "exit_code" key name.
    return {
        "cmd": command,
        "machine": machine,
        "exit_code": int(result.get("returncode", 1)),
        "stdout": result.get("stdout", "") or "",
        "stderr": result.get("stderr", "") or "",
        "duration_ms": duration_ms,
    }


def list_known_machines() -> list:
    """
    Return the sorted list of machine names known to the executor.

    Used by loop.py / prompts.py to tell the LLM which machines it can target.
    Triggers lazy import if not already done. Sorted alphabetically for
    deterministic prompt output (important for prompt caching).
    """
    _lazy_import_executor()
    return sorted(_known_hosts.keys()) if _known_hosts else []
