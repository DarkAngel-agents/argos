# argos-ui-operations
version: 1.0
os: any
loaded_when: UI, interface, frontend, chats module, fleet module, jobs module, dashboard, browser

## Stack
- Alpine.js 3.14.1 (reactivity, x-data, x-show, x-for)
- htmx 2.0.4 (module loading via hx-get, hx-swap innerHTML)
- htmx-ext-sse 2.2.2 (live activity stream)
- Self-hosted, zero build pipeline, no npm

## File Structure
```
ui/
  index.html          # Shell: topbar, sidebar, central-slot, right column
  modules/
    dashboard.html    # Overview cards
    chats.html        # Split pane: conversation list + chat-view
    chat-view.html    # Loaded inside chats via fetch+DOM replace
    fleet.html        # System list with online/offline status
    jobs.html         # Job list with expand detail view
    health.html       # Heartbeat data per node
    reasoning.html    # Reasoning log per conversation
    settings.html     # Placeholder
  static/
    alpine.min.js
    htmx.min.js
    htmx-sse.min.js
    argos.css
    argos.js
```

## Serving
- main.py mounts: StaticFiles("/ui") at path "/ui"
- Root "/" returns ui/index.html via FileResponse
- Modules loaded via htmx: GET /ui/modules/chats.html -> innerHTML into #central-slot

## API Endpoints for UI
- GET /api/conversations - list chats
- POST /api/conversations - create new
- DELETE /api/conversations/{id} - delete (cleans FK tables)
- GET /api/conversations/{id}/messages - chat history
- POST /api/messages - send message (triggers LLM)
- GET /api/fleet - combined fleet list
- DELETE /api/fleet/known/{id} - deactivate system
- DELETE /api/fleet/nanite/{node_id} - remove nanite
- GET /api/jobs - job list
- GET /api/jobs/{id} - job detail with segments/results
- DELETE /api/jobs/{id} - delete job
- POST /api/jobs/{id}/execute - execute pending job
- GET /api/health/snapshot - heartbeat summary
- GET /api/stream/activity - SSE live feed

## CRITICAL: Browser Cache
- Modules are static HTML served without cache-control headers
- After code change + redeploy, browser keeps old JavaScript in memory
- Alpine.js functions from old module persist until full page reload
- ALWAYS test in incognito/private window after changes
- Known issue: cache-busting headers not yet implemented

## Alpine.js Pattern (modules)
Each module HTML has <script> with function returning Alpine data object.
Example: function chatsModule() { return { ... } }
htmx loads HTML, Alpine MutationObserver auto-inits the new x-data scope.
DO NOT call Alpine.initTree manually - causes duplicate scopes.

## Gotchas
- chat-view.html loaded via fetch+removeChild pattern (not htmx) to avoid scope conflicts
- Fleet install/talk: cannot navigate to chats module via Alpine (scope destroyed during DOM swap)
- Current workaround: alert("Conversatie creata. Mergi in Chats.")
- innerHTML + Alpine.initTree = BUG (duplicate scopes, double POST) - use removeChild+appendChild
