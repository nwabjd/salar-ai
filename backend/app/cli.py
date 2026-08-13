# backend/app/cli.py
"""SALAR CLI — quick access to common backend operations."""
import argparse
import asyncio
import json
import sys


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_ping(args):
    import httpx
    r = httpx.get(f"{args.base_url}/api/health")
    _print({"status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]})


def cmd_login(args):
    import httpx
    r = httpx.post(f"{args.base_url}/api/auth/login", json={"email": args.email, "password": args.password})
    if r.status_code != 200:
        _print({"error": f"login failed ({r.status_code})", "detail": r.text[:300]})
        sys.exit(1)
    data = r.json()
    token = data.get("access_token") or data.get("token")
    _print({"access_token": token, "token_type": data.get("token_type", "bearer")})


def cmd_search(args):
    import httpx
    token = args.token
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.get(f"{args.base_url}/api/search", params={"q": args.query, "limit": args.limit}, headers=headers)
    _print({"status": r.status_code, "results": r.json() if r.status_code == 200 else r.text[:300]})


def cmd_health(args):
    cmd_ping(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="salar", description="SALAR CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ping", "health"):
        p = sub.add_parser(name, help="check server health")
        p.add_argument("--base-url", default="http://localhost:8000")
    p = sub.add_parser("login", help="obtain an access token")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p = sub.add_parser("search", help="universal search")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--token")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=10)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    getattr(sys.modules[__name__], f"cmd_{args.command}")(args)


if __name__ == "__main__":
    main()
