# argos-chat-internals
version: 1.0
os: any
loaded_when: chat error, message error, tool_use, send_message, 500 error, API error

## send_message Flow (api/chat.py)
1. Save user message to DB (with dedup check, 30s window)
2. Update conversation.updated_at
3. Morning report check (first message of day)
4. Load tool scores from DB
5. Grok reasoning consult (if complex message)
6. Load relevant skills (BM25 selector + forced nixos-25.11)
7. Load compressed message history (_load_messages_compressed)
8. Call Claude API with system prompt + tools
9. Tool loop: if stop_reason=tool_use, execute tools, append results, call again
10. Save final response to DB

## Tool Execution Loop
```
Claude response -> stop_reason == "tool_use"?
  YES -> extract tool_uses from response.content
      -> append {"role":"assistant","content":response.content} to messages
      -> execute ALL tools in parallel (asyncio.gather)
      -> for EACH tool: save UI message + build tool_result
      -> append {"role":"user","content":[tool_results]} to messages
      -> call Claude again (back to top)
  NO -> save response, return
```

## CRITICAL: tool_use/tool_result Pairing
- Claude API REQUIRES: every tool_use block must have matching tool_result immediately after
- Messages must alternate: user -> assistant -> user -> assistant
- If ARGOS crashes mid-tool-call, DB has orphan assistant messages with tool_use
- _load_messages merges consecutive same-role messages to prevent API rejection
- Multiple assistant messages from UI logging (tool info + result) get merged into one

## _load_messages Sanitization
1. Load from DB ordered by created_at
2. Strip orphan tool_use at end (while loop)
3. Merge consecutive same-role messages (concatenate with newline)
4. Return clean alternating user/assistant list

## Model and Pricing
- Model: claude-sonnet-4-6 (SONNET constant)
- Input: 3.0 EUR/1M tokens (pre-tax)
- Output: 15.0 EUR/1M tokens (pre-tax)

## Tools Available
- execute_command: SSH command on any fleet machine
- read_file: read file via SSH
- nixos_rebuild: backup + rebuild NixOS config
- create_job: multi-step job with auth
- code_edit: Claude Code for code modifications
- build_iso: NixOS ISO builder
- github_push: git commit + push
- run_code: Python subprocess for complex batch ops
- tool_search_tool_bm25: internal skill search

## Error Handling
- 500 with 'tool_use ids without tool_result': orphan tool calls in history
  Fix: DELETE FROM messages WHERE conversation_id = X (clear and retry)
- 529 API overloaded: auto-retry 10x with 60s delay
- 409 duplicate_message: same content within 30s window

## Gotchas
- expanduser("~") in container = /home/argos, not /home/darkangel
- LOCAL_MACHINES must be [] - container cannot exec locally on host
- Skills loaded per conversation (cached in _loaded_skills dict)
- Grok consulted for complex messages via _should_consult_grok
- working_memory updated after each tool round (last 5 steps)
