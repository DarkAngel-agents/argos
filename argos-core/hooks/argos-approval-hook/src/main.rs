//! ARGOS Approval Hook for Claude Code PreToolUse
//!
//! Reads JSON from stdin (Claude Code hook format), maps tool to ARGOS kind,
//! posts approval request to ARGOS API, polls status, exits 0 (allow) or 2 (deny).
//!
//! Stdin format (from Claude Code 2.1.25, captured live):
//! {
//!   "session_id": "uuid",
//!   "transcript_path": "...",
//!   "cwd": "...",
//!   "permission_mode": "default|bypassPermissions|...",
//!   "hook_event_name": "PreToolUse",
//!   "tool_name": "Bash|Read|Write|Edit|...",
//!   "tool_input": { ... tool-specific ... },
//!   "tool_use_id": "toolu_..."
//! }
//!
//! Exit codes:
//!   0 = allow (tool runs)
//!   2 = deny (tool blocked, stderr shown to user)
//!
//! Environment:
//!   ARGOS_HOOK_URL      - override ARGOS base URL (default http://127.0.0.1:666)
//!   ARGOS_HOOK_DEBUG    - if set to "1", log to ARGOS_HOOK_LOG
//!   ARGOS_HOOK_LOG      - debug log file path (default /tmp/argos_hook.log)
//!   ARGOS_HOOK_TIMEOUT  - override approval timeout in seconds (default 1800)
//!
//! Part of Vikunja #152 Faza B Pas 2.

use std::env;
use std::fs::OpenOptions;
use std::io::{self, Read, Write};
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::Value;

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_ARGOS_URL: &str = "http://127.0.0.1:666";
const CONNECT_TIMEOUT: Duration = Duration::from_secs(5);
const READ_TIMEOUT: Duration = Duration::from_secs(10);
const POLL_INTERVAL: Duration = Duration::from_secs(2);
const POLL_GRACE_SECS: u64 = 15; // extra over server timeout before we give up
const DEFAULT_TIMEOUT_SECS: u64 = 1800;

/// Tools that skip approval entirely (read-only / metadata / agent-internal).
/// Task sub-agents go through the hook recursively anyway.
const SKIP_TOOLS: &[&str] = &[
    "Read",
    "Grep",
    "Glob",
    "LS",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "TodoRead",
    "Task",
    "NotebookRead",
    "BashOutput",
    "KillShell",
    "ExitPlanMode",
];

// ============================================================================
// I/O types
// ============================================================================

#[derive(Deserialize, Debug)]
struct HookInput {
    #[serde(default)]
    session_id: String,
    #[serde(default)]
    cwd: String,
    #[serde(default)]
    permission_mode: String,
    #[serde(default)]
    #[allow(dead_code)]
    hook_event_name: String,
    tool_name: String,
    #[serde(default)]
    tool_input: Value,
    #[serde(default)]
    tool_use_id: String,
}

#[derive(Serialize)]
struct ApprovalRequest {
    kind: String,
    intent_text: String,
    intent_json: Value,
    timeout_seconds: u64,
}

#[derive(Deserialize)]
struct ApprovalCreatedResponse {
    approval_id: i64,
    #[serde(default)]
    #[allow(dead_code)]
    risk_level: String,
    #[serde(default)]
    #[allow(dead_code)]
    status: String,
}

#[derive(Deserialize)]
struct ApprovalStatusResponse {
    status: String,
    #[serde(default)]
    decision_reason: Option<String>,
    #[serde(default)]
    risk_level: String,
}

// ============================================================================
// Debug logging (env-gated, no-op if ARGOS_HOOK_DEBUG not set)
// ============================================================================

fn debug_log(msg: &str) {
    if env::var("ARGOS_HOOK_DEBUG").unwrap_or_default() != "1" {
        return;
    }
    let path = env::var("ARGOS_HOOK_LOG").unwrap_or_else(|_| "/tmp/argos_hook.log".to_string());
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
        let _ = writeln!(f, "[{}] {}", ts, msg);
    }
}

// ============================================================================
// Tool name -> ARGOS kind mapping
// ============================================================================

/// Returns Some(kind) if the tool needs approval, None to skip.
fn map_tool_to_kind(tool_name: &str) -> Option<&'static str> {
    if SKIP_TOOLS.contains(&tool_name) {
        return None;
    }
    match tool_name {
        "Bash" => Some("cc_bash"),
        "Write" | "Edit" | "MultiEdit" | "NotebookEdit" => Some("cc_file"),
        _ => Some("cc_tool"), // fallback for any unknown tool (e.g. MCP tools)
    }
}

// ============================================================================
// Build intent payload from Claude Code tool_input
// ============================================================================

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let cut: String = s.chars().take(max).collect();
        format!("{}...", cut)
    }
}

fn build_intent(kind: &str, input: &HookInput) -> (String, Value) {
    // Common trace fields - ARGOS endpoint stores these verbatim in intent_json
    let mut intent_json = serde_json::json!({
        "cc_session_uuid": input.session_id,
        "cc_tool_name": input.tool_name,
        "cc_tool_use_id": input.tool_use_id,
        "cc_permission_mode": input.permission_mode,
        "cc_cwd": input.cwd,
    });

    let intent_text = match kind {
        "cc_bash" => {
            let command = input
                .tool_input
                .get("command")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let description = input
                .tool_input
                .get("description")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            intent_json["command"] = Value::String(command.to_string());
            intent_json["target"] = Value::String("local".to_string());
            if !description.is_empty() {
                intent_json["description"] = Value::String(description.to_string());
            }
            format!("cc_bash: {}", truncate(command, 80))
        }
        "cc_file" => {
            let path = input
                .tool_input
                .get("file_path")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let operation = match input.tool_name.as_str() {
                "Write" => "write",
                "Edit" => "edit",
                "MultiEdit" => "edit",
                "NotebookEdit" => "notebook_edit",
                _ => "write",
            };
            intent_json["path"] = Value::String(path.to_string());
            intent_json["operation"] = Value::String(operation.to_string());
            // size hint for Write (content present)
            if let Some(content) = input.tool_input.get("content").and_then(|v| v.as_str()) {
                intent_json["size"] = Value::Number(content.len().into());
            }
            // preserve original tool_input for full traceability
            intent_json["cc_tool_input"] = input.tool_input.clone();
            format!("cc_file {}: {}", operation, truncate(path, 80))
        }
        _ => {
            // cc_tool generic fallback
            intent_json["tool"] = Value::String(input.tool_name.clone());
            intent_json["args"] = input.tool_input.clone();
            format!("cc_tool: {}", input.tool_name)
        }
    };

    (intent_text, intent_json)
}

// ============================================================================
// ARGOS API calls
// ============================================================================

fn argos_url() -> String {
    env::var("ARGOS_HOOK_URL").unwrap_or_else(|_| DEFAULT_ARGOS_URL.to_string())
}

fn timeout_seconds() -> u64 {
    env::var("ARGOS_HOOK_TIMEOUT")
        .ok()
        .and_then(|v| v.parse::<u64>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(DEFAULT_TIMEOUT_SECS)
}

fn build_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(CONNECT_TIMEOUT)
        .timeout_read(READ_TIMEOUT)
        .timeout_write(READ_TIMEOUT)
        .build()
}

fn request_approval(
    agent: &ureq::Agent,
    kind: &str,
    intent_text: &str,
    intent_json: Value,
    timeout: u64,
) -> Result<i64, String> {
    let url = format!("{}/api/claude-code/request-approval", argos_url());
    let payload = ApprovalRequest {
        kind: kind.to_string(),
        intent_text: intent_text.to_string(),
        intent_json,
        timeout_seconds: timeout,
    };

    let resp = agent
        .post(&url)
        .set("Content-Type", "application/json")
        .send_json(serde_json::to_value(&payload).map_err(|e| format!("serialize: {}", e))?)
        .map_err(|e| format!("POST {}: {}", url, e))?;

    let parsed: ApprovalCreatedResponse = resp
        .into_json()
        .map_err(|e| format!("parse approval response: {}", e))?;
    Ok(parsed.approval_id)
}

enum Decision {
    Approved,
    Denied(String),
    Timeout,
    Error(String),
}

fn poll_status(agent: &ureq::Agent, approval_id: i64, max_wait_secs: u64) -> Decision {
    let url = format!(
        "{}/api/claude-code/approval-status/{}",
        argos_url(),
        approval_id
    );
    let start = Instant::now();
    let max_wait = Duration::from_secs(max_wait_secs);
    let mut consecutive_errors = 0u32;

    loop {
        if start.elapsed() > max_wait {
            return Decision::Timeout;
        }

        match agent.get(&url).call() {
            Ok(resp) => match resp.into_json::<ApprovalStatusResponse>() {
                Ok(s) => {
                    consecutive_errors = 0;
                    debug_log(&format!(
                        "poll approval_id={} status={} risk={}",
                        approval_id, s.status, s.risk_level
                    ));
                    match s.status.as_str() {
                        "approved" => return Decision::Approved,
                        "denied" => {
                            return Decision::Denied(
                                s.decision_reason.unwrap_or_else(|| "denied".to_string()),
                            );
                        }
                        "timeout" => return Decision::Timeout,
                        "pending" => { /* keep polling */ }
                        other => {
                            return Decision::Error(format!("unknown status: {}", other));
                        }
                    }
                }
                Err(e) => {
                    consecutive_errors += 1;
                    debug_log(&format!(
                        "parse status error (consec={}): {}",
                        consecutive_errors, e
                    ));
                    if consecutive_errors >= 30 {
                        return Decision::Error(format!("parse failures: {}", e));
                    }
                }
            },
            Err(e) => {
                consecutive_errors += 1;
                debug_log(&format!(
                    "poll HTTP error (consec={}): {}",
                    consecutive_errors, e
                ));
                // 30 consecutive errors at 2s = 60s of downtime -> bail
                if consecutive_errors >= 30 {
                    return Decision::Error(format!("ARGOS unreachable too long: {}", e));
                }
            }
        }

        thread::sleep(POLL_INTERVAL);
    }
}

// ============================================================================
// Main
// ============================================================================

fn main() -> ExitCode {
    // Read full stdin
    let mut buf = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut buf) {
        eprintln!("argos-approval-hook: read stdin: {}", e);
        debug_log(&format!("stdin read error: {}", e));
        return ExitCode::from(2);
    }
    debug_log(&format!("stdin: {}", truncate(&buf, 2000)));

    let input: HookInput = match serde_json::from_str(&buf) {
        Ok(x) => x,
        Err(e) => {
            eprintln!("argos-approval-hook: parse stdin JSON: {}", e);
            debug_log(&format!("json parse error: {}", e));
            return ExitCode::from(2);
        }
    };

    // Skip non-intercept tools
    let kind = match map_tool_to_kind(&input.tool_name) {
        None => {
            debug_log(&format!("skip tool: {}", input.tool_name));
            return ExitCode::from(0);
        }
        Some(k) => k,
    };

    let (intent_text, intent_json) = build_intent(kind, &input);
    debug_log(&format!(
        "request kind={} intent={}",
        kind,
        truncate(&intent_text, 200)
    ));

    let agent = build_agent();
    let timeout = timeout_seconds();

    // Step 1: request approval
    let approval_id = match request_approval(&agent, kind, &intent_text, intent_json, timeout) {
        Ok(id) => id,
        Err(e) => {
            eprintln!("argos-approval-hook: ARGOS request-approval failed: {}", e);
            debug_log(&format!("request error: {}", e));
            // ARGOS unreachable -> DENY (fail-safe)
            return ExitCode::from(2);
        }
    };
    debug_log(&format!("approval_id={}", approval_id));

    // Step 2: poll until decision
    let max_wait = timeout + POLL_GRACE_SECS;
    match poll_status(&agent, approval_id, max_wait) {
        Decision::Approved => {
            debug_log(&format!("APPROVED approval_id={}", approval_id));
            let out = serde_json::json!({
                "hookSpecificOutput": {
                    "hookEventName": &input.hook_event_name,
                    "permissionDecision": "allow",
                    "permissionDecisionReason": format!("argos approved auth_id={}", approval_id)
                }
            });
            println!("{}", out);
            ExitCode::from(0)
        }
        Decision::Denied(reason) => {
            eprintln!("argos-approval-hook: DENIED by ARGOS: {}", reason);
            debug_log(&format!(
                "DENIED approval_id={} reason={}",
                approval_id, reason
            ));
            ExitCode::from(2)
        }
        Decision::Timeout => {
            eprintln!(
                "argos-approval-hook: TIMEOUT waiting for approval (id={})",
                approval_id
            );
            debug_log(&format!("TIMEOUT approval_id={}", approval_id));
            ExitCode::from(2)
        }
        Decision::Error(e) => {
            eprintln!("argos-approval-hook: ERROR (id={}): {}", approval_id, e);
            debug_log(&format!("ERROR approval_id={} {}", approval_id, e));
            ExitCode::from(2)
        }
    }
}

// ============================================================================
// Unit tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_input(tool_name: &str, tool_input: Value) -> HookInput {
        HookInput {
            session_id: "uuid-xxx".to_string(),
            cwd: "/home/darkangel".to_string(),
            permission_mode: "bypassPermissions".to_string(),
            hook_event_name: "PreToolUse".to_string(),
            tool_name: tool_name.to_string(),
            tool_input,
            tool_use_id: "toolu_abc".to_string(),
        }
    }

    #[test]
    fn test_skip_tools_return_none() {
        for t in SKIP_TOOLS {
            assert!(
                map_tool_to_kind(t).is_none(),
                "expected skip for tool: {}",
                t
            );
        }
    }

    #[test]
    fn test_bash_maps_to_cc_bash() {
        assert_eq!(map_tool_to_kind("Bash"), Some("cc_bash"));
    }

    #[test]
    fn test_write_variants_map_to_cc_file() {
        for t in &["Write", "Edit", "MultiEdit", "NotebookEdit"] {
            assert_eq!(map_tool_to_kind(t), Some("cc_file"));
        }
    }

    #[test]
    fn test_unknown_tool_falls_back_to_cc_tool() {
        assert_eq!(map_tool_to_kind("SomeMcpTool"), Some("cc_tool"));
    }

    #[test]
    fn test_build_intent_bash() {
        let input = mk_input(
            "Bash",
            serde_json::json!({
                "command": "echo hello",
                "description": "say hi"
            }),
        );
        let (text, j) = build_intent("cc_bash", &input);
        assert!(text.contains("cc_bash"));
        assert!(text.contains("echo hello"));
        assert_eq!(j["command"], "echo hello");
        assert_eq!(j["target"], "local");
        assert_eq!(j["description"], "say hi");
        assert_eq!(j["cc_session_uuid"], "uuid-xxx");
        assert_eq!(j["cc_tool_name"], "Bash");
    }

    #[test]
    fn test_build_intent_write() {
        let input = mk_input(
            "Write",
            serde_json::json!({
                "file_path": "/tmp/test.txt",
                "content": "hello world"
            }),
        );
        let (text, j) = build_intent("cc_file", &input);
        assert!(text.contains("cc_file write"));
        assert!(text.contains("/tmp/test.txt"));
        assert_eq!(j["path"], "/tmp/test.txt");
        assert_eq!(j["operation"], "write");
        assert_eq!(j["size"], 11); // len of "hello world"
    }

    #[test]
    fn test_build_intent_edit_operation() {
        let input = mk_input(
            "Edit",
            serde_json::json!({
                "file_path": "/etc/nixos/configuration.nix",
                "old_string": "foo",
                "new_string": "bar"
            }),
        );
        let (_text, j) = build_intent("cc_file", &input);
        assert_eq!(j["operation"], "edit");
        assert_eq!(j["path"], "/etc/nixos/configuration.nix");
        // size must be absent since Edit has no content field
        assert!(j.get("size").is_none() || j["size"].is_null());
    }

    #[test]
    fn test_build_intent_unknown_tool() {
        let input = mk_input(
            "WeirdMcp__tool",
            serde_json::json!({"arg1": "val1"}),
        );
        let (text, j) = build_intent("cc_tool", &input);
        assert_eq!(text, "cc_tool: WeirdMcp__tool");
        assert_eq!(j["tool"], "WeirdMcp__tool");
        assert_eq!(j["args"]["arg1"], "val1");
    }

    #[test]
    fn test_deserialize_real_stdin_bash() {
        // Exact JSON captured live from Claude Code 2.1.25
        let s = r#"{"session_id":"3b9a6dd0-f8a3-4db4-9d49-b1fb2c72f17a","transcript_path":"/home/darkangel/.claude/projects/-home-darkangel/3b9a6dd0.jsonl","cwd":"/home/darkangel","permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"echo hello_bash","description":"Print hello_bash"},"tool_use_id":"toolu_01UWgXCTyCq3hhZF93i6kvHb"}"#;
        let input: HookInput = serde_json::from_str(s).expect("deserialize live sample");
        assert_eq!(input.tool_name, "Bash");
        assert_eq!(input.tool_input["command"], "echo hello_bash");
        assert_eq!(input.permission_mode, "default");
    }

    #[test]
    fn test_deserialize_real_stdin_write() {
        let s = r#"{"session_id":"75d06a64-7b8c-4869-8c13-7df978e104f0","transcript_path":"/foo","cwd":"/home/darkangel","permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"/tmp/argos_write_test.txt","content":"content_write_test"},"tool_use_id":"toolu_01CPfAK3u3HYPwJDPruoqnKJ"}"#;
        let input: HookInput = serde_json::from_str(s).expect("deserialize live Write");
        assert_eq!(input.tool_name, "Write");
        assert_eq!(input.tool_input["file_path"], "/tmp/argos_write_test.txt");
        assert_eq!(input.tool_input["content"], "content_write_test");
    }

    #[test]
    fn test_truncate() {
        assert_eq!(truncate("abc", 10), "abc");
        assert_eq!(truncate("abcdefghij", 5), "abcde...");
        // unicode safe
        assert_eq!(truncate("aaaaaaaaaa", 3), "aaa...");
    }
}
