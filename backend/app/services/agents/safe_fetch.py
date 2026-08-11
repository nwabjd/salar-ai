"""DNS-validated, redirect-safe public web fetching.

The default transport resolves once, rejects the entire DNS answer set when any
address is non-public, then pins the TCP connection to one validated address.
httpcore still receives the original URL origin, so it supplies the original
Host header and uses the original hostname for HTTPS SNI and certificate checks.
"""

import re
import socket
import ssl
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlsplit

import httpcore
from bs4 import BeautifulSoup

from .urls import canonical_public_url, is_public_ip


class PinnedNetworkBackend:
    def __init__(self, pinned_ip: str, backend: Optional[Any] = None) -> None:
        self.pinned_ip = pinned_ip
        self.backend = backend or httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> Any:
        return self.backend.connect_tcp(
            self.pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def connect_unix_socket(self, path: str, timeout: Optional[float] = None) -> Any:
        return self.backend.connect_unix_socket(path, timeout=timeout)

    def sleep(self, seconds: float) -> None:
        self.backend.sleep(seconds)


def _default_resolver(hostname: str, port: int) -> List[str]:
    return list(
        dict.fromkeys(
            item[4][0]
            for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        )
    )


def _default_transport(url: str, pinned_ip: str, timeout: float) -> Dict[str, Any]:
    pool = httpcore.ConnectionPool(
        ssl_context=ssl.create_default_context(),
        network_backend=PinnedNetworkBackend(pinned_ip),
        retries=0,
        max_connections=1,
        max_keepalive_connections=0,
    )
    try:
        response = pool.request(
            "GET",
            url,
            headers={"User-Agent": "SALAR-Research/1.0", "Accept": "text/html,text/plain"},
            extensions={
                "timeout": {
                    "connect": timeout,
                    "read": timeout,
                    "write": timeout,
                    "pool": timeout,
                }
            },
        )
        return {
            "status": response.status,
            "headers": {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in response.headers
            },
            "content": response.content,
        }
    finally:
        pool.close()


class SafePublicFetcher:
    def __init__(
        self,
        resolver: Optional[Callable[[str, int], Iterable[str]]] = None,
        transport: Optional[Callable[[str, str, float], Dict[str, Any]]] = None,
        max_redirects: int = 3,
        timeout: float = 8.0,
    ) -> None:
        self.resolver = resolver or _default_resolver
        self.transport = transport or _default_transport
        self.max_redirects = max(0, min(int(max_redirects), 3))
        self.timeout = max(0.1, float(timeout))

    def fetch_page(self, url: str) -> Dict[str, Any]:
        current = canonical_public_url(url)
        if current is None:
            return {"url": str(url), "error": "URL is not a valid public HTTP(S) target."}

        redirects = 0
        while True:
            parsed = urlsplit(current)
            hostname = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            try:
                socket.inet_pton(socket.AF_INET, hostname)
                addresses = [hostname]
            except OSError:
                try:
                    socket.inet_pton(socket.AF_INET6, hostname)
                    addresses = [hostname]
                except OSError:
                    try:
                        addresses = list(dict.fromkeys(self.resolver(hostname, port)))
                    except Exception as exc:
                        return {"url": current, "error": f"DNS resolution failed: {str(exc) or exc.__class__.__name__}"}

            if not addresses or any(not is_public_ip(address) for address in addresses):
                return {"url": current, "error": "DNS target is not entirely public."}

            try:
                response = self.transport(current, addresses[0], self.timeout)
                status = int(response.get("status", 0))
                headers = {
                    str(key).lower(): str(value)
                    for key, value in dict(response.get("headers") or {}).items()
                }
            except Exception as exc:
                return {"url": current, "error": f"Page fetch failed: {str(exc) or exc.__class__.__name__}"}

            if status in {301, 302, 303, 307, 308} and headers.get("location"):
                if redirects >= self.max_redirects:
                    return {"url": current, "error": "Redirect limit exceeded."}
                redirected = canonical_public_url(urljoin(current, headers["location"]))
                if redirected is None:
                    return {"url": current, "error": "Redirect target is not a valid public URL."}
                redirects += 1
                current = redirected
                continue

            return self._page_result(current, status, headers, response.get("content", b""))

    @staticmethod
    def _page_result(url: str, status: int, headers: Dict[str, str], content: Any) -> Dict[str, Any]:
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8", errors="replace")
        content_type = headers.get("content-type", "text/html")
        if "text/html" not in content_type and not content_type.startswith("text/"):
            return {"url": url, "status": status, "error": f"Non-text content: {content_type}"}
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        return {"url": url, "status": status, "title": title, "text": text[:15000]}


__all__ = ["PinnedNetworkBackend", "SafePublicFetcher"]
