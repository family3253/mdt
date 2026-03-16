#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple
from urllib.parse import urlparse, parse_qs

def maybe_update_aether(docker_compose_dir: str = "/home/chenyechao/Aether") -> dict:
    """Best-effort update for Aether container (app only).

    We avoid pulling docker.io base images due to network instability;
    only pull ghcr app image and recreate app container.
    """
    import subprocess, time
    result = {"attempted": True, "ok": False, "detail": ""}
    try:
        cmd = ["bash", "-lc", f"cd {docker_compose_dir} && docker compose pull app && docker compose up -d app"]
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        out = (cp.stdout or "") + "\n" + (cp.stderr or "")
        if cp.returncode != 0:
            result["detail"] = out.strip()[-1200:]
            return result
        # wait health a bit
        for _ in range(30):
            st = subprocess.run(["bash","-lc","docker inspect $(docker ps -qf name=aether-app) --format '{{.State.Health.Status}}'"],
                                capture_output=True,text=True).stdout.strip()
            if st == 'healthy':
                result["ok"] = True
                result["detail"] = "aether-app healthy"
                return result
            time.sleep(2)
        result["detail"] = "aether-app not healthy after wait"
        return result
    except Exception as e:
        result["detail"] = f"exception: {type(e).__name__}: {e}"
        return result



import requests


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def parse_any_ts(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = int(v)
        if x > 10_000_000_000:  # ms
            x //= 1000
        return x
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return parse_any_ts(float(s))
        except Exception:
            pass
        try:
            return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
        except Exception:
            return None
    return None


def load_protect_list(path: str) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    items = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        items.add(s)
    return items


def aether_login(base: str, email: str, password: str, token: str | None = None) -> str:
    if token:
        return token
    r = requests.post(f"{base}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def get_gpt_keys(aether_base: str, token: str, provider_id: str, page_size: int = 200) -> List[Dict]:
    h = {"Authorization": f"Bearer {token}"}
    out: List[Dict] = []
    page = 1
    while True:
        r = requests.get(
            f"{aether_base}/api/admin/pool/{provider_id}/keys",
            headers=h,
            params={"page": page, "page_size": page_size},
            timeout=60,
        )
        r.raise_for_status()
        obj = r.json() if isinstance(r.json(), dict) else {}
        arr = obj.get("keys", []) if isinstance(obj.get("keys", []), list) else []
        out.extend(arr)
        total = int(obj.get("total", len(out)))
        if len(out) >= total or not arr:
            break
        page += 1
    return out


def load_ban_list(path: str) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out


def append_ban_list(path: str, emails: List[str]) -> None:
    if not emails:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_ban_list(path)
    new = [e for e in emails if e and e not in existing]
    if not new:
        return
    with p.open("a", encoding="utf-8") as f:
        for e in new:
            f.write(e + "\n")


def list_cpa_codex_tokens(cpa_base: str, mgmt_key: str) -> List[Dict]:
    h = {"Authorization": f"Bearer {mgmt_key}"}
    r = requests.get(f"{cpa_base}/v0/management/auth-files", headers=h, timeout=60)
    r.raise_for_status()
    files = r.json().get("files", [])

    out: List[Dict] = []
    seen = set()
    now = now_ts()

    for f in files:
        if (f.get("provider") != "codex" and f.get("type") != "codex") or f.get("disabled"):
            continue
        # Skip clearly invalidated oauth tokens reported by CPA
        msg = str(f.get("status_message") or "")
        if "token_invalidated" in msg or "token invalidated" in msg or "token_invalid" in msg:
            continue
        p = f.get("path")
        if not p or not os.path.exists(p):
            continue
        try:
            obj = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue

        rt = (obj.get("refresh_token") or "").strip()
        email = (obj.get("email") or f.get("email") or f.get("account") or "").strip()
        if not rt or rt in seen:
            continue

        exp_ts = parse_any_ts(obj.get("expires") or obj.get("expired") or obj.get("oauth_expires_at"))
        if exp_ts is not None and exp_ts <= now + 600:
            continue

        seen.add(rt)
        out.append(
            {
                "email": email,
                "refresh_token": rt,
                "last_refresh": parse_any_ts(obj.get("last_refresh") or f.get("last_refresh")) or 0,
                "expires_at": exp_ts,
                "source": "cpa_existing",
            }
        )

    out.sort(key=lambda x: int(x.get("last_refresh") or 0), reverse=True)
    return out


def rand_local_part(n: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def create_candidate_email(domain: str) -> str:
    return f"{rand_local_part()}@{domain}"


def request_codex_oauth_url(cpa_base: str, mgmt_key: str) -> Dict:
    h = {"Authorization": f"Bearer {mgmt_key}"}
    r = requests.get(f"{cpa_base}/v0/management/codex-auth-url", headers=h, timeout=60)
    r.raise_for_status()
    obj = r.json() if isinstance(r.json(), dict) else {}
    return {"url": obj.get("url"), "state": obj.get("state")}


def wait_cpa_oauth_done(cpa_base: str, mgmt_key: str, state: str, timeout_sec: int = 300) -> Dict:
    h = {"Authorization": f"Bearer {mgmt_key}"}
    deadline = time.time() + timeout_sec
    last = {"status": "wait"}
    while time.time() < deadline:
        r = requests.get(f"{cpa_base}/v0/management/get-auth-status", headers=h, params={"state": state}, timeout=30)
        r.raise_for_status()
        obj = r.json() if isinstance(r.json(), dict) else {"status": "wait"}
        last = obj
        st = str(obj.get("status") or "").lower()
        if st in {"ok", "error"}:
            return obj
        time.sleep(2)
    return {"status": "error", "error": f"timeout waiting oauth state={state}", "last": last}


def pick_new_codex_auth_file(cpa_base: str, mgmt_key: str, before_paths: set[str], state: str | None = None) -> Dict | None:
    h = {"Authorization": f"Bearer {mgmt_key}"}
    r = requests.get(f"{cpa_base}/v0/management/auth-files", headers=h, timeout=60)
    r.raise_for_status()
    files = r.json().get("files", [])
    cands = []
    for f in files:
        if (f.get("provider") != "codex" and f.get("type") != "codex") or f.get("disabled"):
            continue
        p = f.get("path")
        if not p or p in before_paths or not os.path.exists(p):
            continue
        try:
            obj = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        rt = (obj.get("refresh_token") or "").strip()
        if not rt:
            continue
        cands.append(
            {
                "email": (obj.get("email") or f.get("email") or f.get("account") or "").strip(),
                "refresh_token": rt,
                "last_refresh": parse_any_ts(obj.get("last_refresh") or f.get("last_refresh")) or 0,
                "expires_at": parse_any_ts(obj.get("expires") or obj.get("expired") or obj.get("oauth_expires_at")),
                "path": p,
                "source": "cpa_new_oauth",
                "state": state,
            }
        )
    cands.sort(key=lambda x: int(x.get("last_refresh") or 0), reverse=True)
    return cands[0] if cands else None


def parse_callback_url(url: str) -> Dict[str, str]:
    q = parse_qs(urlparse(url).query)
    return {k: (v[0] if isinstance(v, list) and v else "") for k, v in q.items()}


def submit_oauth_callback(cpa_base: str, mgmt_key: str, callback_url: str) -> Dict:
    h = {"Authorization": f"Bearer {mgmt_key}"}
    payload = parse_callback_url(callback_url)
    payload["callback_url"] = callback_url
    r = requests.post(f"{cpa_base}/v0/management/oauth-callback", headers=h, json=payload, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    return {"status": r.status_code, "body": body}


def should_cleanup_401(key: Dict) -> bool:
    reason = str(key.get("oauth_invalid_reason") or "").lower()
    if key.get("oauth_invalid_at"):
        return True
    patterns = ["401", "unauthorized", "invalid_token", "invalid token", "token expired", "invalid_grant"]
    return any(p in reason for p in patterns)


def delete_keys_batch(aether_base: str, token: str, provider_id: str, key_ids: List[str]) -> Dict:
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{aether_base}/api/admin/pool/{provider_id}/keys/batch-action",
        headers=h,
        json={"key_ids": key_ids, "action": "delete"},
        timeout=60,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    return {"status": r.status_code, "body": body}


def batch_import(aether_base: str, token: str, provider_id: str, creds: List[Dict], proxy_node_id: str | None) -> Dict:
    h = {"Authorization": f"Bearer {token}"}
    payload = "\n".join([c["refresh_token"] for c in creds])
    req = {"credentials": payload}
    if proxy_node_id:
        req["proxy_node_id"] = proxy_node_id

    r = requests.post(
        f"{aether_base}/api/admin/provider-oauth/providers/{provider_id}/batch-import",
        headers=h,
        json=req,
        timeout=240,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:1000]}
    return {"status": r.status_code, "body": body}


def main():
    ap = argparse.ArgumentParser(description="Aether GPT provider maintenance")
    ap.add_argument("--cpa-base", default="http://127.0.0.1:8080")
    ap.add_argument("--cpa-mgmt-key", required=True)
    ap.add_argument("--aether-base", default="http://127.0.0.1:8084")
    ap.add_argument("--aether-email", required=True)
    ap.add_argument("--aether-password", required=False, default="")
    ap.add_argument("--aether-token", default="")
    ap.add_argument("--provider-id", required=True)
    ap.add_argument("--target-keys", type=int, default=30)
    ap.add_argument("--protect-list", default="/home/chenyechao/.openclaw/workspace/configs/aether-gpt-protect-list.txt")
    ap.add_argument("--ban-list", default="/home/chenyechao/.openclaw/workspace/configs/aether-gpt-ban-list.txt", help="Emails to skip when selecting CPA refresh tokens (e.g. refresh_token_reused).")
    ap.add_argument("--proxy-node-id", default="")
    ap.add_argument("--safe", action="store_true", help="safe mode: no deletion, capped import")
    ap.add_argument("--update-aether", action="store_true", help="Before maintenance, best-effort update Aether app container (pull ghcr app only).")
    ap.add_argument("--import-limit", type=int, default=20)
    ap.add_argument("--cleanup-limit", type=int, default=20)
    ap.add_argument("--oauth-callback-url", default="", help="manual callback url captured after browser oauth")
    ap.add_argument("--oauth-email-domain", default="cyc3253.org", help="virtual domain label for newly created candidates")
    ap.add_argument("--oauth-timeout-sec", type=int, default=300)
    ap.add_argument("--fallback-to-existing-cpa", action="store_true", help="fallback to existing CPA refresh tokens when no new oauth callback is provided")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log-file", default="/home/chenyechao/.openclaw/workspace/memory/aether-maintain-last.json")
    args = ap.parse_args()

    # Optional: update Aether app container before any maintenance work
    update_result = None
    if getattr(args, "update_aether", False) and not args.dry_run:
        update_result = maybe_update_aether()

    summary = {
        "time": now_iso(),
        "mode": {"dry_run": args.dry_run, "safe": args.safe},
        "provider_id": args.provider_id,
        "proxy_node_id": args.proxy_node_id or None,
        "aether_update": update_result,
    }

    token = aether_login(args.aether_base, args.aether_email, args.aether_password, args.aether_token or None)
    keys_before = get_gpt_keys(args.aether_base, token, args.provider_id)
    summary["before_key_count"] = len(keys_before)

    protect = load_protect_list(args.protect_list)
    summary["protect_count"] = len(protect)

    ban = load_ban_list(args.ban_list)
    summary["ban_count"] = len(ban)

    cleanup_candidates = []
    for k in keys_before:
        name = str(k.get("key_name") or k.get("name") or "").strip()
        if name in protect:
            continue
        if should_cleanup_401(k):
            cleanup_candidates.append({"id": k.get("key_id") or k.get("id"), "name": name})

    cleanup_candidates = [c for c in cleanup_candidates if c.get("id")][: args.cleanup_limit]
    summary["cleanup_candidates"] = len(cleanup_candidates)

    cleanup_done = 0
    if cleanup_candidates and not args.dry_run and not args.safe:
        ids = [c["id"] for c in cleanup_candidates]
        res = delete_keys_batch(args.aether_base, token, args.provider_id, ids)
        cleanup_done = int((res.get("body") or {}).get("affected") or 0)
        summary["cleanup_result"] = {"status": res.get("status"), "affected": cleanup_done}
    summary["cleanup_executed"] = cleanup_done

    keys_mid = get_gpt_keys(args.aether_base, token, args.provider_id)
    need = max(0, args.target_keys - len(keys_mid))
    if args.safe:
        need = min(need, args.import_limit)
    summary["refill_needed"] = need

    all_tokens = list_cpa_codex_tokens(args.cpa_base, args.cpa_mgmt_key)
    summary["cpa_codex_token_count"] = len(all_tokens)

    existing_names = {str(k.get("key_name") or k.get("name") or "").strip() for k in keys_mid}
    existing_emails = set()
    for n in existing_names:
        if "@" in n:
            existing_emails.add(n)
        if n.startswith("codex_") and "@" in n:
            existing_emails.add(n.replace("codex_", "", 1))

    selected = []
    oauth_flow = {
        "requested": False,
        "mode": None,
        "state": None,
        "candidate_email": None,
        "callback_submit": None,
        "status": None,
        "new_auth_file": None,
    }

    if need > 0:
        before_paths = {str(x.get("path") or "") for x in all_tokens if x.get("path")}
        callback_url = (args.oauth_callback_url or "").strip()
        if callback_url:
            oauth_flow["requested"] = True
            oauth_flow["mode"] = "manual_callback"
            oauth_req = request_codex_oauth_url(args.cpa_base, args.cpa_mgmt_key)
            oauth_flow["state"] = oauth_req.get("state")
            oauth_flow["candidate_email"] = create_candidate_email(args.oauth_email_domain)
            oauth_flow["callback_submit"] = submit_oauth_callback(args.cpa_base, args.cpa_mgmt_key, callback_url)
            oauth_flow["status"] = wait_cpa_oauth_done(args.cpa_base, args.cpa_mgmt_key, oauth_req.get("state") or "", args.oauth_timeout_sec)
            new_auth = pick_new_codex_auth_file(args.cpa_base, args.cpa_mgmt_key, before_paths, oauth_req.get("state"))
            oauth_flow["new_auth_file"] = {"email": new_auth.get("email"), "path": new_auth.get("path")} if new_auth else None
            if new_auth:
                selected.append(new_auth)
        elif args.fallback_to_existing_cpa:
            oauth_flow["requested"] = False
            oauth_flow["mode"] = "fallback_existing_cpa"

    if len(selected) < need and args.fallback_to_existing_cpa:
        for item in all_tokens:
            email = str(item.get("email") or "").strip()
            if email and (email in existing_emails or email in protect):
                continue
            if any(str(x.get("refresh_token") or "") == str(item.get("refresh_token") or "") for x in selected):
                continue
            selected.append(item)
            if len(selected) >= need:
                break

    summary["oauth_flow"] = oauth_flow
    summary["selected_for_import"] = len(selected)
    summary["selected_accounts_sample"] = [x.get("email") for x in selected[:10]]
    summary["selected_sources"] = [x.get("source") for x in selected[:10]]

    import_result = {"status": None, "total": 0, "success": 0, "failed": 0, "top_errors": []}
    if need > 0 and selected and not args.dry_run:
        r = batch_import(args.aether_base, token, args.provider_id, selected, args.proxy_node_id or None)
        body = r.get("body", {}) if isinstance(r.get("body", {}), dict) else {}
        errs = {}
        for item in body.get("results", []):
            if item.get("status") != "success":
                em = item.get("error", "unknown")
                errs[em] = errs.get(em, 0) + 1
        import_result = {
            "status": r.get("status"),
            "total": body.get("total", 0),
            "success": body.get("success", 0),
            "failed": body.get("failed", 0),
            "top_errors": sorted(errs.items(), key=lambda x: x[1], reverse=True)[:5],
        }
    summary["import"] = import_res

    # Auto-ban accounts whose refresh tokens are reported as reused.
    # This improves future success rate by skipping known-bad sources.
    try:
        reused = []
        results = (import_res.get('body') or {}).get('results') or []
        for it in results:
            if str(it.get('status')) != 'success' and 'refresh_token_reused' in str(it.get('error') or ''):
                i = int(it.get('index')) if str(it.get('index')).isdigit() else None
                if i is not None and 0 <= i < len(selected):
                    reused.append((selected[i].get('email') or '').strip())
        reused = [e for e in reused if e]
        if reused and not args.dry_run:
            append_ban_list(args.ban_list, reused)
        summary['ban_added_reused'] = len(reused)
    except Exception as e:
        summary['ban_added_reused_error'] = f"{type(e).__name__}: {e}"


    keys_after = get_gpt_keys(args.aether_base, token, args.provider_id)
    summary["after_key_count"] = len(keys_after)
    summary["delta_key_count"] = summary["after_key_count"] - summary["before_key_count"]

    h = {"Authorization": f"Bearer {token}"}
    mr = requests.get(f"{args.aether_base}/api/admin/providers/{args.provider_id}/models", headers=h, timeout=60)
    models = mr.json() if mr.ok and isinstance(mr.json(), list) else []
    summary["models"] = [m.get("provider_model_name") for m in models][:20]

    Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log_file).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
