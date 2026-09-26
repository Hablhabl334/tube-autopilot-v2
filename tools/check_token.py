#!/usr/bin/env python3
"""Verify YouTube API credentials — the "does my token work?" tool.

For the shared setup and/or each channel this tool:
  1. exchanges the refresh token for a fresh access token  (costs 0 quota units)
  2. calls channels.list(mine=True)                         (costs 1 quota unit)
  3. prints the channel it unlocked: name, subscribers, videos, total views

Exit codes (used by the verify-token GitHub workflow):
  0   every present credential verified OK (or none found — nothing to check)
  1   at least one present credential FAILED (bad secret, revoked token, quota)

Usage:
  python tools/check_token.py                     # check shared + all 4 channels
  python tools/check_token.py --channel mindset   # check one channel only
  python tools/check_token.py --shared            # check the shared setup only
  python tools/check_token.py --json              # machine-readable output

Reads credentials from the environment and from factory.env / .env in the
repo root (same rules as src/config.py: real environment variables win).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests   (or: pip install -r requirements.txt)")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_IDS = ["mindset", "facts", "tech", "money"]
TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def load_env_files() -> None:
    """Merge factory.env / .env (repo root) into os.environ — values already
    present in the environment win (identical logic to src/config.py)."""
    for name in ("factory.env", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if key and not os.environ.get(key):
                    os.environ[key] = val
        except Exception:
            pass


def credential_sets(only: str | None) -> list[dict]:
    """Build the list of credential sets to verify.

    Shared set uses the global YT_CLIENT_ID / YT_CLIENT_SECRET /
    YT_REFRESH_TOKEN. Per-channel sets use YT_CLIENT_ID_<CH> /
    YT_CLIENT_SECRET_<CH> / YT_REFRESH_TOKEN_<CH>, falling back to the global
    client id/secret (same fallback rules as src/youtube.py).
    """
    sets: list[dict] = []
    g_id = os.environ.get("YT_CLIENT_ID", "").strip()
    g_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
    g_refresh = os.environ.get("YT_REFRESH_TOKEN", "").strip()

    want_channels = CHANNEL_IDS if only in (None, "all") else [only]

    if only in (None, "all", "shared") and g_refresh:
        sets.append({
            "name": "shared",
            "client_id": g_id,
            "client_secret": g_secret,
            "refresh_token": g_refresh,
        })

    if want_channels:
        for ch in want_channels:
            c = ch.upper()
            cid = os.environ.get(f"YT_CLIENT_ID_{c}", "").strip() or g_id
            csec = os.environ.get(f"YT_CLIENT_SECRET_{c}", "").strip() or g_secret
            rt = os.environ.get(f"YT_REFRESH_TOKEN_{c}", "").strip()
            if rt:
                sets.append({
                    "name": ch,
                    "client_id": cid,
                    "client_secret": csec,
                    "refresh_token": rt,
                })
    return sets


def verify(cred: dict) -> tuple[bool, str, dict | None]:
    """One credential set → (ok, human message, channel info)."""
    if not cred["client_id"] or not cred["client_secret"]:
        return False, "missing YT_CLIENT_ID / YT_CLIENT_SECRET for this set", None

    # step 1 — refresh token → access token (0 quota units)
    try:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": cred["refresh_token"],
            "client_id": cred["client_id"],
            "client_secret": cred["client_secret"],
        }, timeout=30)
    except requests.RequestException as e:
        return False, f"network error talking to Google: {e}", None

    if r.status_code != 200:
        try:
            err = r.json().get("error", "")
        except Exception:
            err = r.text[:200]
        if err == "invalid_client":
            return False, "invalid_client — the client ID/secret is wrong " \
                          "(copy them again from the client_secret JSON)", None
        if err == "invalid_grant":
            return False, "invalid_grant — refresh token revoked or expired. " \
                          "Most common cause: the OAuth consent screen is in " \
                          "TESTING status (tokens die after 7 days). Fix: " \
                          "Google Cloud → OAuth consent screen → PUBLISH APP, " \
                          "then re-run tools/auth.py to mint a new token.", None
        return False, f"token endpoint returned {r.status_code}: {err}", None

    access_token = r.json().get("access_token")

    # step 2 — channels.list(mine=True) (1 quota unit)
    try:
        api = requests.get(CHANNELS_URL,
                           params={"part": "snippet,statistics", "mine": "true"},
                           headers={"Authorization": f"Bearer {access_token}"},
                           timeout=30)
    except requests.RequestException as e:
        return False, f"network error talking to the YouTube API: {e}", None

    if api.status_code == 403 and "quota" in api.text.lower():
        return False, "daily quota exceeded — refreshes at midnight Pacific", None
    if api.status_code == 401:
        return False, "access token rejected (401) — re-run tools/auth.py", None
    if api.status_code != 200:
        return False, f"YouTube API returned {api.status_code}: {api.text[:200]}", None

    items = api.json().get("items", [])
    if not items:
        return False, "token works, but this Google account has no YouTube " \
                      "channel (channels.list came back empty)", None
    it = items[0]
    s = it.get("statistics", {})
    info = {
        "channel": it.get("snippet", {}).get("title", "?"),
        "subscribers": s.get("subscriberCount", "?"),
        "videos": s.get("videoCount", "?"),
        "views": s.get("viewCount", "?"),
    }
    return True, "verified", info


def main() -> int:
    ap = argparse.ArgumentParser(description="verify YouTube API credentials")
    ap.add_argument("--channel", choices=CHANNEL_IDS + ["all"],
                    help="check only this channel (default: all + shared)")
    ap.add_argument("--shared", action="store_true",
                    help="check only the shared YT_CLIENT_ID/SECRET/REFRESH_TOKEN set")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print machine-readable JSON")
    args = ap.parse_args()

    load_env_files()
    only = "shared" if args.shared else args.channel
    sets = credential_sets(only)

    results = []
    if not sets:
        msg = ("no YouTube credentials found (no YT_* env vars, no .env) — "
               "nothing to verify yet. Add GitHub secrets, then re-run.")
        print(msg)
        results.append({"name": "-", "ok": True, "message": msg, "info": None})
    else:
        for cred in sets:
            ok, message, info = verify(cred)
            results.append({"name": cred["name"], "ok": ok,
                            "message": message, "info": info})
            if args.as_json:
                continue
            mark = "✅" if ok else "❌"
            print(f"{mark} {cred['name']:>8}: {message}")
            if ok and info:
                print(f"           channel: {info['channel']}  "
                      f"subs: {info['subscribers']}  videos: {info['videos']}  "
                      f"views: {info['views']}")

    if args.as_json:
        print(json.dumps(results, indent=2))

    failed = [r for r in results if not r["ok"]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
