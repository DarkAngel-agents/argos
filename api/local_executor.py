import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

OLLAMA_URL = "http://172.17.0.1:11435"
OLLAMA_MODEL = "qwen3:14b"


class LocalTask(BaseModel):
    steps: List[str]
    target: str
    context: Optional[str] = None


@router.post("/local-exec")
async def local_exec(req: LocalTask):
    from api.executor import _exec_ssh_by_name
    results = []
    for i, step in enumerate(req.steps):
        result = await _exec_ssh_by_name(req.target, step)
        results.append({
            "step": i,
            "command": step[:80],
            "returncode": result["returncode"],
            "output": result["stdout"][:500] if result["stdout"] else result["stderr"][:200],
            "ok": result["returncode"] == 0
        })
        if result["returncode"] != 0:
            break
    all_ok = all(r["ok"] for r in results)
    return {"status": "ok" if all_ok else "failed", "steps_executed": len(results), "results": results}


@router.post("/mistral-analyze")
async def mistral_analyze(task: str, context: Optional[str] = None):
    prompt = f"""Esti un asistent tehnic expert in Linux, NixOS si Proxmox.
Analizeaza urmatoarea situatie si raspunde DOAR in JSON cu structura:
{{"assessment": "descriere scurta", "risk": "low|medium|high|critical", "recommended_steps": ["pas1", "pas2"], "warnings": []}}

Situatie: {task}
{f'Context: {context}' if context else ''}

Raspunde DOAR cu JSON valid, fara alte texte."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            )
            data = resp.json()
            text = data.get("response", "").strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            return {"status": "ok", "analysis": parsed}
    except json.JSONDecodeError:
        return {"status": "ok", "analysis": {"assessment": text, "risk": "unknown", "recommended_steps": [], "warnings": []}}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/ollama-status")
async def ollama_status():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {
                "status": "ok",
                "models": models,
                "active_model": OLLAMA_MODEL,
                "model_available": OLLAMA_MODEL in models
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
