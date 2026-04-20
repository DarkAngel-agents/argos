# agent-orca
version: latest (Docker: ddalcu/agent-orcha)
category: AGENT ORCA
source: https://agentorcha.com/documentation.html
loaded_when: any task related to agent-orca, multi-agent AI, orchestration, agent workflows, YAML agents, MCP integration

## What Is Agent Orcha
Multi-agent AI orchestration framework. Runs as Docker container.
Agents defined in YAML. REST API for all operations.
Studio (web UI) at port 3000. Supports: OpenAI, Anthropic, Gemini, local LLMs (Ollama, LM Studio, built-in Omni engine).
Key capabilities: ReAct workflows, knowledge stores (RAG + graph), MCP servers, skills (prompt injection), triggers (cron + webhook), P2P network (Hyperswarm), browser sandbox, persistent memory, structured output.

## Quick Start (Docker)
```bash
mkdir my-project
docker run -p 3000:3000 -e AUTH_PASSWORD=mypass -v ./my-project:/data ddalcu/agent-orcha start
# Studio: http://localhost:3000
```

## Docker Compose
```yaml
services:
  agent-orcha:
    image: ddalcu/agent-orcha
    ports:
      - "3000:3000"
    volumes:
      - ./my-agent-orcha-project:/data
    environment:
      AUTH_PASSWORD: mypass
```

## Environment Variables
| Variable            | Default   | Description                                      |
|---------------------|-----------|--------------------------------------------------|
| WORKSPACE           | /data     | Base dir inside container                        |
| PORT                | 3000      | Listening port                                   |
| AUTH_PASSWORD       | unset     | If set, all /api/* routes require password       |
| CORS_ORIGIN         | unset     | * = allow all, or specific URL                   |
| BROWSER_SANDBOX     | true      | Chromium+Xvfb+VNC for browser tools             |
| LOG_LEVEL           | info      | debug / info / warn / error                     |
| P2P_ENABLED         | true      | Set false to disable P2P                         |
| P2P_PEER_NAME       | hostname  | Display name on P2P network                      |
| P2P_SHARE_LLMS      | false     | Share all active LLMs automatically              |

## Auto-scaffolded on First Run
- agents/         - example agent YAML configs
- workflows/      - example workflow definitions
- functions/      - custom JS functions
- knowledge/      - knowledge store configs + data
- models.yaml     - LLM provider settings
- mcp.json        - MCP server configuration

## models.yaml (LLM Config)
```yaml
version: "1.0"
llm:
  default: omni           # pointer to named config
  omni:
    provider: omni        # built-in local inference
    model: Qwen3.5-4B-IQ4_NL
    reasoningBudget: 0
    contextSize: 32768
    active: true
    share: true           # share on P2P network
  anthropic:
    provider: anthropic
    apiKey: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4-6
    thinkingBudget: 5000
    active: false
  openai:
    provider: openai
    apiKey: ${OPENAI_API_KEY}
    model: gpt-4o
    temperature: 0.7
    active: false
embeddings:
  default: omni
  omni:
    provider: omni
    model: nomic-embed-text-v1.5.Q4_K_M
```

## Agent YAML (Minimal)
```yaml
name: myagent
description: My first AI agent
version: "1.0.0"
model:
  name: default
  temperature: 0.7
prompt:
  system: |
    You are a helpful assistant.
  inputVariables:
    - query
output:
  format: text
```

## Agent YAML (P2P Shared)
```yaml
name: my-agent
model: default
prompt:
  system: You are helpful.
  inputVariables:
    - query
p2p:
  share: true
```

## REST API Reference

### Health
```
GET /health
Response: { "status": "ok", "timestamp": "..." }
```

### Authentication (when AUTH_PASSWORD set)
```
POST /api/auth/login
Body: { "password": "your-secret-password" }
Response: { "authenticated": true }  + sets HttpOnly session cookie

GET /api/auth/check
Response: { "authenticated": false, "required": true }

POST /api/auth/logout
```

### Agents API
```
GET    /api/agents                         # list all agents
GET    /api/agents/:name                   # get agent details
POST   /api/agents/:name/invoke            # run agent (sync)
POST   /api/agents/:name/stream            # stream response (SSE)
GET    /api/agents/sessions/stats          # session statistics
GET    /api/agents/sessions/:sessionId     # session details
DELETE /api/agents/sessions/:sessionId     # clear session
```

#### Invoke Agent
```bash
curl -X POST http://HOST:3000/api/agents/myagent/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"query": "Hello?"}, "sessionId": "optional-id"}'

# Response:
{
  "output": "Agent response text",
  "metadata": {
    "tokensUsed": 150,
    "toolCalls": [],
    "duration": 1234,
    "sessionId": "optional-id",
    "messagesInSession": 4
  }
}
```

### Workflows API
```
GET  /api/workflows                        # list
GET  /api/workflows/:name                  # details
POST /api/workflows/:name/run              # execute
POST /api/workflows/:name/stream           # stream (SSE)
POST /api/workflows/:name/resume           # resume paused (human-in-the-loop)
```

### Knowledge API
```
GET  /api/knowledge                        # list stores
POST /api/knowledge/:name/search           # semantic search
POST /api/knowledge/:name/query            # direct SQL
```

### Other APIs
```
GET/POST /api/functions/:name              # custom JS functions
GET/POST /api/skills                       # skills management
GET/POST /api/tasks                        # async tasks
GET/POST /api/mcp                          # MCP server tools
POST     /api/files                        # file upload
POST     /api/llm/chat                     # direct LLM chat
GET/POST /api/graph                        # knowledge graph
GET      /api/logs                         # execution logs
GET/POST /api/p2p                          # P2P network
GET/POST /api/organizations                # orgs management
```

## Triggers (Cron + Webhook)
```yaml
# Cron trigger
triggers:
  - type: cron
    schedule: "0 9 * * *"
    input:
      task: "Generate the daily report"

# Webhook trigger (registers POST /api/triggers/webhooks/:agent-name)
triggers:
  - type: webhook
    path: /api/triggers/webhooks/webhook-handler
    input:
      data: "default context"
```

## MCP Servers (mcp.json)
```json
{
  "version": "1.0.0",
  "servers": {
    "fetch": {
      "transport": "streamable-http",
      "url": "https://remote.mcpservers.org/fetch/mcp",
      "timeout": 30000,
      "enabled": true
    },
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  },
  "globalOptions": {
    "throwOnLoadError": false,
    "prefixToolNameWithServerName": true,
    "defaultToolTimeout": 30000
  }
}
```

## Skills (Prompt Injection)
Skills are Markdown files injected into agent system prompt at runtime.
Not executable — pure knowledge/instruction bundles.
```
skills/
  my-skill/
    SKILL.md     # YAML frontmatter + Markdown content
```
```markdown
---
name: pii-guard
description: PII filtering rules
---
# PII Guard
Never include SSN, tax IDs, salaries, home addresses in responses.
```

## P2P Network (Hyperswarm)
```yaml
# Share LLM in models.yaml:
omni:
  provider: omni
  model: Qwen3.5-4B-IQ4_NL
  active: true
  share: true

# Use remote LLM in agent:
model: "p2p"              # auto-select first available
model: "p2p:model-name"   # specific remote model
```
Three P2P modes:
1. Direct LLM chat — raw inference on remote peer
2. Remote agent invocation — agent runs on host peer, you receive output
3. Local agent + remote LLM — agent/tools/memory local, only LLM inference remote

## GitHub / NPM
- GitHub: https://github.com/ddalcu/agent-orcha
- NPM:    https://www.npmjs.com/package/agent-orcha
- Docker: ddalcu/agent-orcha
