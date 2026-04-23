# argos-db-mcp

MCP server custom Postgres pentru argos-db. Inlocuieste
`@modelcontextprotocol/server-postgres` oficial cu logica specifica ARGOS:
masking pe `system_credentials`, approval flow pentru DML/DDL non-`cc_*`,
refuz direct pe writes catre `system_credentials`.

## Tools expose

- `schema()` — lista tabele + coloane (read-only)
- `query(sql)` — SELECT, masking automat pe `system_credentials`
- `execute(sql, confirm?)` — DML/DDL cu gating:
  - `cc_*` → pass-through
  - Alt tabel → approval via `/api/claude-code/request-approval` (kind=cc_sql)
  - Write pe `system_credentials` → refuz instant

## Install (venv)

```sh
cd ~/.argos/argos-core/mcp_servers/argos_db_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pip freeze > requirements.txt
cp .env.example .env
# editeaza .env cu DB_PASSWORD real
```

## Run standalone (pentru test)

```sh
source .venv/bin/activate
python server.py
```

## Use din Claude Code (dupa Pas 4)

Wrapper `~/bin/argos-db-mcp` + settings.json `mcpServers.argos-db.command`.

## Test

```sh
source .venv/bin/activate
pytest tests/ -v
```

## Referinte

- Task: Vikunja #152 Faza B Pas 3
- Parinte: Vikunja #143 Claude Code workhorse
