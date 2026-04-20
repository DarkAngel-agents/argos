# claude-api
version: 2026
os: any
loaded_when: Claude API, Anthropic, tool use, system prompt

## Modele disponibile (2026)
- claude-sonnet-4-6 — model principal Argos
- claude-opus-4-6 — cel mai capabil, mai scump
- claude-haiku-4-5 — rapid si ieftin

## Request de baza
```python
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8096,
    system="...",
    messages=[{"role":"user","content":"..."}]
)
```

## Tool Use
```python
tools=[{
    "name": "execute_command",
    "defer_loading": False,  # frecvent
    "description": "...",
    "input_schema": {"type":"object","properties":{...},"required":[...]}
}]
```

## defer_loading
- False: tool incarcat mereu in context
- True: incarcat on-demand (85% reducere tokeni)
- Necesita Tool Search Tool activat

## Stop reasons
- end_turn: raspuns complet
- tool_use: vrea sa execute tool
- max_tokens: taiat

## Costuri aproximative (2026)
- Sonnet: ~$3/$15 per M tokens input/output
- Haiku: ~$0.25/$1.25 per M tokens

## Gotchas
- examples in tool schema = NOT PERMITTED (400 error)
- max_tokens obligatoriu
- system prompt separat de messages
- tool_result trebuie trimis inapoi ca user message
