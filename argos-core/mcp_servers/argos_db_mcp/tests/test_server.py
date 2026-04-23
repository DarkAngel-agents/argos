"""Sanity + smoke + schema + query + masking + execute tests pentru argos-db-mcp."""

import pytest


# ---- Sanity ----

def test_import_server():
    import server  # noqa: F401


def test_python_version():
    import sys
    assert sys.version_info >= (3, 10)


def test_load_config_ok():
    import server
    cfg = server.load_config()
    for k in ("db_host", "db_user", "db_password", "db_name"):
        assert cfg[k], f"{k} empty/missing"
    assert isinstance(cfg["db_port"], int)


def test_mcp_instance_registered():
    import server
    assert server.mcp.name == "argos-db"


# ---- Validation (sync, no DB needed) ----

def test_validate_select_ok():
    import server
    server._validate_read_only("SELECT 1")


def test_validate_cte_ok():
    import server
    server._validate_read_only(
        "WITH c AS (SELECT id FROM authorizations LIMIT 1) SELECT * FROM c"
    )


def test_validate_insert_rejected():
    import server
    with pytest.raises(ValueError, match="INSERT"):
        server._validate_read_only("INSERT INTO t (x) VALUES (1)")


def test_validate_update_rejected():
    import server
    with pytest.raises(ValueError, match="UPDATE"):
        server._validate_read_only("UPDATE t SET x=1 WHERE id=1")


def test_validate_ddl_rejected():
    import server
    with pytest.raises(ValueError, match="(CREATE|DROP|ALTER|TRUNCATE)"):
        server._validate_read_only("CREATE TABLE foo (x INT)")


def test_validate_multi_statement_rejected():
    import server
    with pytest.raises(ValueError, match="multiple"):
        server._validate_read_only("SELECT 1; SELECT 2")


def test_validate_empty_rejected():
    import server
    with pytest.raises(ValueError, match="empty"):
        server._validate_read_only("   ")


def test_validate_string_literal_not_falsely_flagged():
    import server
    server._validate_read_only("SELECT 'DROP TABLE foo' AS x")


# ---- Masking ----

def test_touches_direct():
    import server
    assert server._touches_system_credentials("SELECT * FROM system_credentials") is True


def test_touches_quoted():
    import server
    assert server._touches_system_credentials('SELECT * FROM "system_credentials"') is True


def test_touches_case_mixed():
    import server
    assert server._touches_system_credentials("SELECT * FROM System_Credentials") is True


def test_touches_schema_qualified():
    import server
    assert server._touches_system_credentials("SELECT * FROM public.system_credentials") is True


def test_touches_join():
    import server
    assert server._touches_system_credentials(
        "SELECT sp.name FROM system_profiles sp JOIN system_credentials sc ON sc.system_id = sp.id"
    ) is True


def test_touches_string_literal_not_flagged():
    import server
    assert server._touches_system_credentials("SELECT 'system_credentials'") is False


def test_touches_other_table_not_flagged():
    import server
    assert server._touches_system_credentials("SELECT * FROM system_credentials_backup") is False
    assert server._touches_system_credentials("SELECT * FROM authorizations") is False


def test_mask_row_whitelist_preserved():
    import server
    row = {
        "id": 1, "system_id": 5, "credential_type": "ssh", "label": "x",
        "active": True, "created_at": "2026-01-01",
        "username": "a", "value_hint": "b", "notes": "c",
    }
    masked = server._mask_row(row)
    assert masked["id"] == 1
    assert masked["username"] == server.MASKED_VALUE
    assert masked["value_hint"] == server.MASKED_VALUE
    assert masked["notes"] == server.MASKED_VALUE


def test_mask_row_unknown_columns_masked():
    import server
    masked = server._mask_row({"id": 1, "mystery_col": "leak"})
    assert masked["id"] == 1
    assert masked["mystery_col"] == server.MASKED_VALUE


# ---- Target extraction (subset din exploratory, regression) ----

def test_extract_target_update():
    import server
    assert server._extract_target_table("UPDATE foo SET x=1") == "foo"


def test_extract_target_update_schema_qualified():
    import server
    assert server._extract_target_table("UPDATE public.authorizations SET x=1") == "authorizations"


def test_extract_target_delete_quoted_schema():
    import server
    assert server._extract_target_table(
        'DELETE FROM "public"."system_credentials"'
    ) == "system_credentials"


def test_extract_target_insert_select():
    import server
    assert server._extract_target_table(
        "INSERT INTO cc_log SELECT * FROM cc_log_staging"
    ) == "cc_log"


def test_extract_target_create_unlogged():
    import server
    assert server._extract_target_table("CREATE UNLOGGED TABLE fast1 (id INT)") == "fast1"


def test_extract_target_create_temp_table():
    import server
    assert server._extract_target_table("CREATE TEMP TABLE t (id INT)") == "t"


def test_extract_target_drop_if_exists():
    import server
    assert server._extract_target_table("DROP TABLE IF EXISTS foo") == "foo"


def test_extract_target_create_index_none():
    import server
    assert server._extract_target_table("CREATE INDEX idx ON bar(col)") is None


def test_extract_target_create_view_none():
    import server
    assert server._extract_target_table("CREATE VIEW v AS SELECT 1") is None


def test_extract_target_create_materialized_view_none():
    import server
    assert server._extract_target_table("CREATE MATERIALIZED VIEW mv AS SELECT 1") is None


def test_extract_target_cte_insert():
    import server
    assert server._extract_target_table(
        "WITH x AS (SELECT 1) INSERT INTO foo SELECT * FROM x"
    ) == "foo"


def test_extract_target_merge():
    import server
    assert server._extract_target_table(
        "MERGE INTO foo USING bar ON foo.id=bar.id WHEN MATCHED THEN UPDATE SET x=1"
    ) == "foo"


def test_extract_target_select_returns_none():
    import server
    assert server._extract_target_table("SELECT 1") is None


# ---- Parse rows affected ----

def test_parse_rows_affected_update():
    import server
    assert server._parse_rows_affected("UPDATE 5") == 5


def test_parse_rows_affected_delete():
    import server
    assert server._parse_rows_affected("DELETE 0") == 0
    assert server._parse_rows_affected("DELETE 2") == 2


def test_parse_rows_affected_insert():
    import server
    assert server._parse_rows_affected("INSERT 0 3") == 3


def test_parse_rows_affected_ddl_zero():
    import server
    assert server._parse_rows_affected("CREATE TABLE") == 0
    assert server._parse_rows_affected("DROP TABLE") == 0
    assert server._parse_rows_affected("TRUNCATE TABLE") == 0


def test_parse_rows_affected_empty():
    import server
    assert server._parse_rows_affected("") == 0
    assert server._parse_rows_affected(None) == 0


# ---- is_write_sql ----

def test_is_write_sql_select_false():
    import server
    assert server._is_write_sql("SELECT 1") is False


def test_is_write_sql_update_true():
    import server
    assert server._is_write_sql("UPDATE foo SET x=1") is True


def test_is_write_sql_cte_insert_true():
    import server
    assert server._is_write_sql("WITH x AS (SELECT 1) INSERT INTO foo SELECT * FROM x") is True


# ---- Live DB tests (query existent) ----

async def test_db_connect_live():
    import server
    pool = await server.get_pool()
    try:
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT 1") == 1
    finally:
        await server.close_pool()


async def test_list_schema_returns_tables():
    import server
    pool = await server.get_pool()
    try:
        grouped = await server.list_schema(pool)
        assert "authorizations" in grouped
        assert "system_credentials" in grouped
    finally:
        await server.close_pool()


async def test_schema_system_credentials_locked():
    import server
    pool = await server.get_pool()
    try:
        grouped = await server.list_schema(pool)
        cols = {c["column"] for c in grouped["system_credentials"]}
        expected = {
            "id", "system_id", "credential_type", "label",
            "username", "value_hint", "notes", "active", "created_at",
        }
        assert cols == expected
    finally:
        await server.close_pool()


async def test_query_simple_not_masked():
    import server
    try:
        r = await server.run_query("SELECT 1 AS x")
        assert r["masked"] is False
        assert r["rows"] == [{"x": 1}]
    finally:
        await server.close_pool()


async def test_query_masks_system_credentials():
    import server
    try:
        r = await server.run_query("SELECT * FROM system_credentials LIMIT 1")
        assert r["masked"] is True
        if r["rows"]:
            row = r["rows"][0]
            assert row["username"] == server.MASKED_VALUE
            assert row["notes"] == server.MASKED_VALUE
    finally:
        await server.close_pool()


# ---- Live execute tests ----

async def test_execute_rejects_select():
    import server
    with pytest.raises(ValueError, match="(use query|write verb)"):
        await server.run_execute("SELECT 1")


async def test_execute_rejects_empty():
    import server
    with pytest.raises(ValueError):
        await server.run_execute("")


async def test_execute_rejects_multi_statement():
    import server
    with pytest.raises(ValueError, match="multiple"):
        await server.run_execute("INSERT INTO cc_x VALUES (1); INSERT INTO cc_y VALUES (2)")


async def test_execute_hard_refuse_system_credentials():
    import server
    try:
        r = await server.run_execute(
            "UPDATE system_credentials SET active=false WHERE id=-999"
        )
        assert r["success"] is False
        assert r["gating"] == "hard_refuse_system_credentials"
        assert r["target_table"] == "system_credentials"
        assert r["rows_affected"] == 0
    finally:
        await server.close_pool()


async def test_execute_hard_refuse_quoted():
    import server
    try:
        r = await server.run_execute(
            'UPDATE "system_credentials" SET active=false WHERE id=-999'
        )
        assert r["gating"] == "hard_refuse_system_credentials"
    finally:
        await server.close_pool()


async def test_execute_hard_refuse_delete():
    import server
    try:
        r = await server.run_execute("DELETE FROM system_credentials WHERE id=-999")
        assert r["gating"] == "hard_refuse_system_credentials"
    finally:
        await server.close_pool()


# NOTE: test_execute_approval_required_authorizations si
# test_execute_approval_required_none_target au fost sterse in Pas 3.10.
# Erau scrise pentru stub-ul gating=approval_required cu error "not implemented".
# Acum flow-ul e real: POST → poll → timeout/decide. Acoperit complet de
# tests mocked cu respx (approved/denied/timeout/400/network_error) +
# test_execute_approval_shape_probe_live pentru contract API real.


async def test_execute_cc_passthrough_e2e():
    """E2E pe cc_test_scratch: CREATE + INSERT + UPDATE + DELETE + DROP."""
    import server
    pool = await server.get_pool()

    # Cleanup din run anterior, daca a picat testul undeva
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS cc_test_scratch")

    try:
        r = await server.run_execute(
            "CREATE TABLE cc_test_scratch (id SERIAL PRIMARY KEY, name TEXT)"
        )
        assert r["success"] is True
        assert r["gating"] == "cc_passthrough"
        assert r["target_table"] == "cc_test_scratch"

        r = await server.run_execute(
            "INSERT INTO cc_test_scratch (name) VALUES ('a'), ('b'), ('c')"
        )
        assert r["success"] is True
        assert r["gating"] == "cc_passthrough"
        assert r["rows_affected"] == 3

        r = await server.run_execute(
            "UPDATE cc_test_scratch SET name='z' WHERE name='a'"
        )
        assert r["success"] is True
        assert r["rows_affected"] == 1

        r = await server.run_execute("DELETE FROM cc_test_scratch WHERE name='b'")
        assert r["success"] is True
        assert r["rows_affected"] == 1

        r = await server.run_execute("UPDATE cc_test_scratch SET name='skip' WHERE id=-1")
        assert r["success"] is True
        assert r["rows_affected"] == 0

        r = await server.run_execute("DROP TABLE cc_test_scratch")
        assert r["success"] is True
        assert r["gating"] == "cc_passthrough"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS cc_test_scratch")
        await server.close_pool()


async def test_execute_cc_passthrough_syntax_error_handled():
    """Eroare SQL in cc_passthrough → success=False cu error msg, nu exception."""
    import server
    pool = await server.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS cc_test_scratch")

    try:
        # INSERT intr-un tabel cc_ inexistent (target OK, dar DB ramure eroare)
        r = await server.run_execute(
            "INSERT INTO cc_nonexistent_table VALUES (1)"
        )
        assert r["success"] is False
        assert r["gating"] == "cc_passthrough"
        assert r["target_table"] == "cc_nonexistent_table"
        assert r["error"] is not None
        assert "db error" in r["error"]
    finally:
        await server.close_pool()


# ---- Approval flow (Pas 3.10) — mocked cu respx ----

import httpx as _httpx_for_tests


async def test_execute_approval_approved_mocked():
    """POST returns approval_id, GET returns approved, SQL executes real pe scratch."""
    import server
    import respx

    cfg = server.get_cfg()
    pool = await server.get_pool()

    # Setup: cream scratch non-cc_ table direct via pool (bypass run_execute)
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS test_approval_scratch")
        await conn.execute(
            "CREATE TABLE test_approval_scratch (id INT PRIMARY KEY, name TEXT)"
        )
        await conn.execute("INSERT INTO test_approval_scratch VALUES (1, 'a')")

    try:
        api = cfg["argos_api_url"]
        with respx.mock(base_url=api) as rmock:
            rmock.post("/api/claude-code/request-approval").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99901,
                        "kind": "cc_sql",
                        "risk_level": "high",
                        "status": "pending",
                        "timeout_seconds": 1800,
                    },
                )
            )
            rmock.get("/api/claude-code/approval-status/99901").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99901,
                        "status": "approved",
                        "decision_reason": None,
                    },
                )
            )

            r = await server.run_execute(
                "UPDATE test_approval_scratch SET name='b' WHERE id=1"
            )
            assert r["success"] is True, r
            assert r["gating"] == "approval_required"
            assert r["target_table"] == "test_approval_scratch"
            assert r["approval_id"] == 99901
            assert r["risk_level"] == "high"
            assert r["rows_affected"] == 1

        # Verific SQL chiar a rulat pe DB
        async with pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT name FROM test_approval_scratch WHERE id=1"
            )
            assert val == "b"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS test_approval_scratch")
        await server.close_pool()
        await server.close_http()


async def test_execute_approval_denied_mocked():
    """Denied → no DB hit, error cu decision_reason."""
    import server
    import respx

    cfg = server.get_cfg()
    api = cfg["argos_api_url"]

    try:
        with respx.mock(base_url=api) as rmock:
            rmock.post("/api/claude-code/request-approval").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99902,
                        "kind": "cc_sql",
                        "risk_level": "critical",
                        "status": "pending",
                        "timeout_seconds": 1800,
                    },
                )
            )
            rmock.get("/api/claude-code/approval-status/99902").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99902,
                        "status": "denied",
                        "decision_reason": "user rejected via UI",
                    },
                )
            )
            # Target scratch care NU exista — daca SQL ar rula (bug), ar fi exception
            r = await server.run_execute("DROP TABLE nonexistent_test_table")
            assert r["success"] is False
            assert r["gating"] == "approval_required"
            assert r["approval_id"] == 99902
            assert r["risk_level"] == "critical"
            assert "denied" in r["error"]
            assert "user rejected via UI" in r["error"]
    finally:
        await server.close_pool()
        await server.close_http()


async def test_execute_approval_timeout_mocked():
    """Timeout → no DB hit, error."""
    import server
    import respx

    cfg = server.get_cfg()
    api = cfg["argos_api_url"]

    try:
        with respx.mock(base_url=api) as rmock:
            rmock.post("/api/claude-code/request-approval").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99903,
                        "kind": "cc_sql",
                        "risk_level": "high",
                        "status": "pending",
                        "timeout_seconds": 1800,
                    },
                )
            )
            rmock.get("/api/claude-code/approval-status/99903").mock(
                return_value=_httpx_for_tests.Response(
                    200,
                    json={
                        "approval_id": 99903,
                        "status": "timeout",
                        "decision_reason": None,
                    },
                )
            )
            r = await server.run_execute("UPDATE some_table SET x=1 WHERE id=-999")
            assert r["success"] is False
            assert r["gating"] == "approval_required"
            assert r["approval_id"] == 99903
            assert "timeout" in r["error"]
    finally:
        await server.close_pool()
        await server.close_http()


async def test_execute_approval_api_http_400_mocked():
    """API returns 400 validation error → graceful error response, no exception."""
    import server
    import respx

    cfg = server.get_cfg()
    api = cfg["argos_api_url"]

    try:
        with respx.mock(base_url=api) as rmock:
            rmock.post("/api/claude-code/request-approval").mock(
                return_value=_httpx_for_tests.Response(
                    400, text="[CCAPI 002] intent_text must not be empty"
                )
            )
            r = await server.run_execute("UPDATE foo SET x=1")
            assert r["success"] is False
            assert r["gating"] == "approval_required"
            assert r["approval_id"] is None
            assert "HTTP 400" in r["error"]
    finally:
        await server.close_pool()
        await server.close_http()


async def test_execute_approval_network_error_mocked():
    """Network error pe POST → graceful error."""
    import server
    import respx

    cfg = server.get_cfg()
    api = cfg["argos_api_url"]

    try:
        with respx.mock(base_url=api) as rmock:
            rmock.post("/api/claude-code/request-approval").mock(
                side_effect=_httpx_for_tests.ConnectError("connection refused")
            )
            r = await server.run_execute("UPDATE foo SET x=1")
            assert r["success"] is False
            assert "network error" in r["error"]
            assert "ConnectError" in r["error"]
    finally:
        await server.close_pool()
        await server.close_http()


async def test_execute_approval_shape_probe_live():
    """LIVE: POST real catre API. Verify kind=cc_sql e acceptat, cleanup cu decide=denied.

    E singurul test care atinge API real — dovedeste ca shape-ul request-ului
    meu MCP match cu ApprovalRequest server-side (intent_json key 'query' etc.).
    """
    import server

    client = await server.get_http()
    try:
        resp = await client.post(
            "/api/claude-code/request-approval",
            json={
                "kind": "cc_sql",
                "intent_text": "LIVE shape probe from test_server.py (will be denied)",
                "intent_json": {"query": "UPDATE pg_settings SET setting='x' WHERE name='probe'"},
                "session_id": None,
                "timeout_seconds": 60,
            },
        )
        assert resp.status_code == 200, (
            f"API rejected shape: {resp.status_code} {resp.text[:300]}"
        )
        data = resp.json()
        assert "approval_id" in data
        assert data["kind"] == "cc_sql"
        assert data["status"] == "pending"
        assert "risk_level" in data
        approval_id = data["approval_id"]

        # Immediate cleanup: POST /decide denied
        cleanup = await client.post(
            f"/api/claude-code/approval/{approval_id}/decide",
            json={"decision": "denied", "reason": "test cleanup shape probe"},
        )
        assert cleanup.status_code == 200, (
            f"cleanup failed: {cleanup.status_code} {cleanup.text[:200]}"
        )
    finally:
        await server.close_http()
        await server.close_pool()
