# ollama-local
version: 2024+
os: nixos
loaded_when: Ollama, qwen, local LLM, modele locale

## Modele disponibile pe Beasty
- qwen3:14b — model principal Argos LOCAL
- alte modele: ollama list

## Request de baza
```python
curl http://localhost:11434/api/generate \
  -d '{"model":"qwen3:14b","prompt":"...","stream":false}'
```

## Chat format
```python
curl http://localhost:11434/api/chat \
  -d '{"model":"qwen3:14b",
       "messages":[{"role":"user","content":"..."}],
       "stream":false}'
```

## Parsare raspuns
```python
data = response.json()
content = data.get("response", "")  # pentru /generate
# sau
content = data["message"]["content"]  # pentru /chat
```

## Gotchas
- Nu are tool calls native
- Fara web search
- Stream=false pentru raspuns complet
- Timeout mare necesar: 300s pentru modele mari
- Port 11434 localhost doar
- qwen3:14b are reasoning (/think tags) — strip inainte de folosit
- Gratuit, fara cost per token
