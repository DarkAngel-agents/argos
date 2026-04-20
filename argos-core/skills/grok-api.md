# grok-api
version: 2026
os: any
loaded_when: Grok API, xAI, web search cu Grok

## Modele disponibile (2026)
- grok-4.20-0309-reasoning — cel mai capabil, cu reasoning
- grok-4.20-0309-non-reasoning — rapid, fara reasoning
- grok-4-1-fast-reasoning / non-reasoning — mai ieftin
- grok-3-mini — vechi, ieftin, cu reasoning

## Chat Completions (fara web search)
```python
curl -X POST "https://api.x.ai/v1/chat/completions"
-H "Authorization: Bearer $GROK_API_KEY"
-d '{"model":"grok-4-1-fast-non-reasoning",
     "messages":[{"role":"user","content":"..."}],
     "max_tokens":1000}'
```

## Responses API (CU web search)
```python
curl -X POST "https://api.x.ai/v1/responses"
-H "Authorization: Bearer $GROK_API_KEY"
-d '{"model":"grok-4.20-0309-non-reasoning",
     "input":[{"role":"user","content":"..."}],
     "tools":[{"type":"web_search"}],
     "max_output_tokens":1000}'
```

## Parametri web_search
- allowed_domains: ["proxmox.com"] — cauta doar pe domenii specifice
- excluded_domains: ["reddit.com"] — exclude domenii
- enable_image_understanding: true

## Parsare raspuns Responses API
```python
for item in d.get('output', []):
    if item.get('type') == 'message':
        for c in item.get('content', []):
            if c.get('type') == 'output_text':
                print(c['text'])
```

## Gotchas
- Live Search pe /v1/chat/completions = DEPRECATED (410)
- Web search DOAR pe /v1/responses
- tool_choice nu e suportat pe Responses API
- reasoning_content disponibil doar pe modele -reasoning
- Costuri: grok-4.20 $2/$6 per M tokens, grok-4-1-fast $0.20/$0.50
