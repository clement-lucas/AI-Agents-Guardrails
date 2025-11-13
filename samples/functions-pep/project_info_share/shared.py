import os, json, jwt, requests
from typing import Tuple

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")

def _caller_app_from_authz(authz: str) -> str:
    if not authz or not authz.startswith("Bearer "):
        raise ValueError("Missing Authorization header")
    token = authz.split(" ",1)[1].strip()
    claims = jwt.decode(token, options={"verify_signature": False})
    return claims.get("appid") or claims.get("azp") or ""

def evaluate_policy(tool: str, purpose: str, caller_app_id: str, action: str, resource_type: str) -> Tuple[bool, dict]:
    payload = {
        "input": {
            "action": action,
            "resource": {"type": resource_type},
            "context": {
                "tool": tool,
                "purpose": purpose,
                "caller_app_id": caller_app_id
            }
        }
    }
    r = requests.post(f"{OPA_URL}/v1/data/pdp", json=payload, timeout=5)
    r.raise_for_status()
    result = r.json().get("result", {})
    allow = bool(result.get("allow"))
    # Rego example exposed optional fields like reason / redactions
    meta = {
        "reason": result.get("reason", ""),
        "redactions": result.get("redactions", [])
    }
    return allow, meta
