# Agent Orcha - Multi-Agent AI Framework

## SCOP

Agent Orcha is a declarative TypeScript framework for building, managing, and scaling multi-agent AI systems using YAML configuration. Combines model-agnostic LLM orchestration, MCP tool integration, SQLite-based vector knowledge stores with optional graph mapping, and a built-in web Studio with in-browser IDE. Suitable for internal AI tools, RAG systems, multi-step research workflows, and chatbot deployments.

GitHub: https://github.com/ddalcu/agent-orcha
Docker Hub: ddalcu/agent-orcha
NPM: agent-orcha
Status: ALPHA (must be deployed behind firewall, never directly exposed to internet)

## QUICK START

```bash
# Docker (one-liner, full setup)
mkdir my-project
docker run -p 3000:3000 \
    -e AUTH_PASSWORD=your-secret-password \
    -v ./my-project:/data \
    ddalcu/agent-orcha start

# Studio UI: http://localhost:3000
```

CLI alternative (requires Node >= 24):
```bash
npx agent-orcha init my-project
cd my-project
npx agent-orcha start
```

## DEPLOYMENT MODES

| Mode | Use case | Command |
|---|---|---|
| **CLI Tool** | Standalone projects, recommended for individual use | `npx agent-orcha init && npx agent-orcha start` |
| **Docker** | Containerized deploy, production-ish | `docker run ddalcu/agent-orcha start` |
| **Backend API Server** | Use as REST API for existing frontends | `npx agent-orcha start` then call `/api/agents/X/invoke` |
| **Library** | Embed in TypeScript/JavaScript apps | `import { Orchestrator } from 'agent-orcha'` |
| **Source** | Development on the framework itself | clone repo + `npm run dev` |

Requirements: Node.js >= 24.0.0 OR Docker

## PROJECT STRUCTURE

```
my-project/
├── agents/                     # Agent definitions (.agent.yaml)
├── workflows/                  # Workflow definitions (.workflow.yaml)
├── knowledge/                  # Knowledge store configs and SQLite data
│   └── .knowledge-data/        # SQLite databases per store
├── functions/                  # Custom JavaScript tools (.function.js)
├── public/                     # Web UI (Studio)
├── llm.json                    # LLM and embedding configs
├── mcp.json                    # MCP server configs
└── .env                        # Environment variables
```

## LLM CONFIGURATION (llm.json)

All LLM and embedding configs centralized in one file. Agents and knowledge stores reference by name. Treats all providers as OpenAI-compatible APIs (LM Studio, Ollama, OpenAI, Gemini, Anthropic).

```json
{
  "version": "1.0",
  "models": {
    "default": {
      "baseUrl": "http://localhost:1234/v1",
      "apiKey": "not-needed",
      "model": "qwen/qwen3-4b-2507",
      "temperature": 0.7
    },
    "openai": {
      "apiKey": "sk-your-openai-key",
      "model": "gpt-4o",
      "temperature": 0.7
    }
  },
  "embeddings": {
    "default": {
      "baseUrl": "http://localhost:1234/v1",
      "apiKey": "not-needed",
      "model": "text-embedding-nomic-embed-text-v1.5",
      "eosToken": " "
    }
  }
}
```

Local provider URLs:
- **LM Studio**: `http://localhost:1234/v1`
- **Ollama**: `http://localhost:11434/v1`
- **OpenAI**: omit baseUrl (uses default)

## AGENTS (YAML)

Agents are AI units with system prompts, LLM config, tools, and optional structured output. Each agent is one file in `agents/` directory.

Example minimal agent:
```yaml
# agents/researcher.agent.yaml
name: researcher
description: Researches topics using web fetch and knowledge search
version: "1.0.0"

llm:
  name: default
  temperature: 0.5

prompt:
  system: |
    You are a thorough researcher. Use available tools to gather
    information before responding.
  inputVariables:
    - topic
    - context

tools:
  - mcp:fetch
  - knowledge:transcripts

output:
  format: text

metadata:
  category: research
  tags: [research, web]
```

Agent capabilities (optional fields in YAML):
- **memory: true** - persistent conversation memory across sessions
- **integrations** - CollabNook chat, IMAP/SMTP email
- **triggers** - cron schedules or webhooks
- **publish: true** - exposes standalone chat page at `/chat/<agent-name>` (with optional per-agent password)
- **skills** - attach reusable skills from skills directory
- **output.format: structured** - enforces JSON schema validation on responses

## WORKFLOW TYPES - STEP-BASED vs REACT

Two distinct workflow models:

### Step-based workflows
Explicit sequential/parallel agent orchestration. You define each step. Best for known pipelines (research → summarize → write).

```yaml
# workflows/research-paper.workflow.yaml
name: research-paper
type: steps  # default

input:
  schema:
    topic:
      type: string
      required: true

steps:
  - id: research
    agent: researcher
    input:
      topic: "{{input.topic}}"
  
  - id: write
    agent: writer
    input:
      research: "{{steps.research.output}}"

output:
  paper: "{{steps.write.output}}"
```

Template syntax: `{{input.X}}`, `{{steps.id.output}}`, `{{steps.id.metadata.duration}}`. Supports parallel blocks, conditional steps, retry config.

### ReAct workflows
Autonomous prompt-driven workflows. The agent decides which tools/agents to call based on system prompt. Best for open-ended tasks.

```yaml
# workflows/react-research.workflow.yaml
name: react-research
type: react

prompt:
  system: |
    You are a research assistant with access to tools and agents.
    Identify what you need, call tools in parallel, synthesize results.
  goal: "Research and analyze: {{input.topic}}"

graph:
  model: default
  executionMode: react  # or single-turn
  tools:
    mode: all
    sources: [mcp, knowledge, function, builtin]
  agents:
    mode: all
  maxIterations: 10
  timeout: 300000

output:
  analysis: "{{state.messages[-1].content}}"
```

Execution modes:
- **single-turn**: tool calls once, returns. For research/data gathering.
- **react**: multiple rounds of tool calls + analysis. For complex problems.

## KNOWLEDGE STORES

Built-in SQLite-based vector store with optional graph mapping. Persists to `.knowledge-data/{name}.db`. On restart, source hashes are compared - unchanged data restores instantly without re-indexing.

Supported source types:
- **directory** - load files matching pattern
- **file** - single file
- **database** - SQL query against PostgreSQL/MySQL/etc, contentColumn for text
- **web** - HTML (Cheerio + selector), JSON API (jsonPath), or raw text

Example with graph mapping:
```yaml
# knowledge/blog-posts.knowledge.yaml
name: blog-posts

source:
  type: database
  connectionString: postgresql://user:pass@localhost:5432/blog
  query: SELECT id, title, content, author_email FROM posts WHERE status='published'
  contentColumn: content
  metadataColumns: [id, title, author_email]

splitter:
  type: recursive
  chunkSize: 2000
  chunkOverlap: 300

embedding: default

graph:
  directMapping:
    entities:
      - type: Post
        idColumn: id
        nameColumn: title
        properties: [title, content]
      - type: Author
        idColumn: author_email
        properties: [author_email]
    relationships:
      - type: WROTE
        source: Author
        target: Post
        sourceIdColumn: author_email
        targetIdColumn: id
```

When `graph.directMapping` is defined, agents automatically gain extra graph tools: `traverse`, `entity_lookup`, `graph_schema`.

## TOOL ECOSYSTEM

Agents reference tools in their `tools:` array with prefix indicating type:

| Prefix | Source | Example |
|---|---|---|
| `mcp:<server>` | MCP servers from mcp.json | `mcp:fetch`, `mcp:filesystem` |
| `knowledge:<store>` | Semantic search on knowledge stores | `knowledge:docs` |
| `function:<name>` | Custom JS in functions/ | `function:fibonacci` |
| `builtin:<tool>` | Framework built-ins | `builtin:ask_user`, `builtin:memory_save` |
| `sandbox:<tool>` | Sandboxed exec/shell/browser | `sandbox:exec`, `sandbox:browser_navigate` |
| `project:<op>` | Workspace file access | `project:read`, `project:write` |

### Sandbox tools (notable for ARGOS)

Run as non-root sandbox user inside Docker container:
- `sandbox:exec` - execute JavaScript in sandboxed VM
- `sandbox:shell` - execute shell commands
- `sandbox:web_fetch` - fetch URLs
- `sandbox:web_search` - web search
- `sandbox:browser_navigate` - navigate browser to URL
- `sandbox:browser_observe` - text snapshot of current page
- `sandbox:browser_click` - click element by CSS selector
- `sandbox:browser_type` - type into element
- `sandbox:browser_screenshot` - multimodal image
- `sandbox:browser_evaluate` - execute JS in browser page

Browser tools require Chromium inside Docker (`BROWSER_SANDBOX=true`, default enabled). noVNC viewer at `http://localhost:6080` for visual debugging.

### Custom functions (JavaScript)

Drop a `.function.js` file in `functions/` directory:
```javascript
// functions/fibonacci.function.js
export default {
  name: 'fibonacci',
  description: 'Returns the nth Fibonacci number',
  parameters: {
    n: { type: 'number', description: 'Index (0-based, max 100)' }
  },
  execute: async ({ n }) => {
    if (n === 0) return 'Fibonacci(0) = 0';
    let prev = 0, curr = 1;
    for (let i = 2; i <= n; i++) [prev, curr] = [curr, prev + curr];
    return `Fibonacci(${n}) = ${curr}`;
  }
};
```

Reference in agent: `tools: [function:fibonacci]`. Zero boilerplate.

## MCP SERVERS

Configure in `mcp.json`. Supports stdio, streamable-http, sse transports.

```json
{
  "servers": {
    "fetch": {
      "transport": "streamable-http",
      "url": "https://remote.mcpservers.org/fetch/mcp",
      "timeout": 30000
    },
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```

Reference in agents: `tools: [mcp:fetch]` (loads ALL tools from that server).

## STUDIO UI

Built-in web dashboard at `http://localhost:3000`. Tabs:

| Tab | Purpose |
|---|---|
| **Agents** | Browse, invoke, stream responses, manage sessions |
| **Knowledge** | Browse stores, search, view graph entities |
| **MCP** | Browse servers, view tools, call directly |
| **Workflows** | Browse, execute, stream progress |
| **Skills** | Browse and inspect available skills |
| **Monitor** | LLM call logs with token estimates and duration |
| **IDE** | In-browser file editor with YAML/JSON/JS syntax highlighting and hot-reload |

The IDE is the killer feature - edit YAML configs in browser, save, files reload without container restart.

## API REFERENCE (KEY ENDPOINTS)

All require `Authorization` header when `AUTH_PASSWORD` is set. `/health` is always public.

### Agents
- `POST /api/agents/:name/invoke` - run agent, returns full response
- `POST /api/agents/:name/stream` - stream response via SSE
- `GET /api/agents/sessions/:sessionId` - get session state
- `DELETE /api/agents/sessions/:sessionId` - clear session

Invoke request:
```json
{
  "input": { "topic": "AI trends" },
  "sessionId": "optional-for-conversation-memory"
}
```

### Workflows
- `POST /api/workflows/:name/run` - execute workflow
- `POST /api/workflows/:name/stream` - stream execution

### Knowledge
- `POST /api/knowledge/:name/search` - semantic search
- `POST /api/knowledge/:name/refresh` - reload documents
- `GET /api/knowledge/:name/entities` - list graph entities

### Published Chat (standalone)
- `GET /chat/:agentName` - serve standalone chat page
- `POST /api/chat/:agentName/stream` - stream chat response

## CONVERSATION MEMORY

Session-based memory for multi-turn dialogues. Pass `sessionId` to invoke calls:

```bash
# First message
curl -X POST http://localhost:3000/api/agents/chatbot/invoke \
  -d '{"input": {"message": "My name is Alice"}, "sessionId": "user-123"}'

# Second message - agent remembers context
curl -X POST http://localhost:3000/api/agents/chatbot/invoke \
  -d '{"input": {"message": "What is my name?"}, "sessionId": "user-123"}'
```

In-memory session storage with FIFO message limit (default 50 per session) and TTL cleanup (default 1 hour).

## STRUCTURED OUTPUT

Force JSON schema validation on agent responses:

```yaml
output:
  format: structured
  schema:
    type: object
    properties:
      sentiment:
        type: string
        enum: [positive, negative, neutral]
      confidence:
        type: number
        minimum: 0
        maximum: 1
    required: [sentiment, confidence]
```

Response automatically validated against schema, `metadata.structuredOutputValid: true` confirms.

## AUTHENTICATION MODEL

Two layers, independent:

1. **Global `AUTH_PASSWORD`** environment variable - protects all `/api/*` routes and Studio UI. Session cookie based.
2. **Per-agent `publish.password`** - protects individual published chat pages at `/chat/<name>`. Independent of global auth.

When `AUTH_PASSWORD` is unset, all routes are open (suitable only for local development behind firewall).

## WHY INTERESTING FOR ARGOS

- **Declarative YAML approach** - similar philosophy to ARGOS skills_tree (config as data, not code)
- **MCP integration** - aligns with ARGOS direction for tool ecosystem
- **Sandbox tools with browser automation** - Chromium in Docker with noVNC viewer, useful for ARGOS scraping/automation tasks
- **ReAct workflow engine** - alternative reference implementation to compare with ARGOS-Commander agent loop design
- **In-browser IDE** - inspiration for ARGOS Studio if/when we build a web UI for skills/configs editing
- **SQLite vector store** - lightweight alternative to ChromaDB for ARGOS knowledge if PostgreSQL isn't enough

Trade-offs vs ARGOS-Commander:
- Agent Orcha is **TypeScript/Node** (we are Python)
- Agent Orcha is **declarative-only** (we mix declarative skills with imperative agent loop)
- Agent Orcha has **NO autonomy gating** comparable to our autonomy_rules + verification_rules system - safety relies on sandbox isolation
- Agent Orcha **NO HA story** - single-node by design

Worth studying for design ideas, NOT a drop-in replacement.

## LICENSE

MIT

## VEZI SI

- `argos-agent/argos-agent-loop-architecture` (#92) - our agent loop design for comparison
- `argos-agent/verification-chain-design` - our verification approach (Agent Orcha has nothing equivalent)
- Vikunja #214 - ARGOS-Commander MVP design (the Python equivalent we're building)
