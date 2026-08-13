# backend/app/api/dev_docs.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/dev", tags=["dev-docs"])


@router.get("/endpoints")
def list_endpoints(request: Request):
    routes = []
    for route in request.app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        if "GET" not in methods and "POST" not in methods:
            continue
        path = getattr(route, "path", "")
        if not path.startswith("/api") or "{" in path:
            continue
        routes.append({"path": path, "methods": sorted(methods - {"HEAD", "OPTIONS"})})
    routes.sort(key=lambda r: r["path"])
    return {"count": len(routes), "endpoints": routes}


@router.get("/summary")
def api_summary(request: Request):
    openapi = getattr(request.app, "openapi", None)
    schema = openapi() if openapi else {}
    paths = schema.get("paths", {})
    tags: dict = {}
    for path, operations in paths.items():
        for method, op in operations.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            for tag in op.get("tags", ["untagged"]):
                tags.setdefault(tag, []).append({"path": path, "method": method.upper(), "summary": op.get("summary", "")})
    return {"tags": sorted(tags.keys()), "groups": tags}
