"""
Helper comun pentru toate scripturile de audit.
Conexiune DB, constante, utility functions.
"""
import asyncio
import asyncpg
import os
import sys

# Config DB (verificat din skills_tree - hardcoded ca sa nu depinda de env)
DB_HOST = "11.11.11.111"
DB_PORT = 5433
DB_USER = "claude"
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = "claudedb"

# Paths
ARGOS_CORE = "/home/darkangel/.argos/argos-core"
AUDIT_DIR = ARGOS_CORE + "/tools/audit"
REPORTS_DIR = AUDIT_DIR + "/reports"
SCRIPTS_DIR = AUDIT_DIR + "/scripts"

async def connect_db():
    """Conectare standard la claudedb."""
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )

def header(title):
    """Print un header vizual in output."""
    print()
    print("=" * 70)
    print(" " + title)
    print("=" * 70)

def section(title):
    """Print un section header."""
    print()
    print("--- " + title + " ---")

def truncate(s, n=80):
    """Truncate string pentru display."""
    if s is None:
        return "None"
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n-3] + "..."
