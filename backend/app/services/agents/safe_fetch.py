"""Deadline-bound, DNS-validated, redirect-safe public web fetching.

The default transport resolves A and AAAA records within one total deadline,
rejects the entire answer set when any address is non-public, then pins TCP to a
validated address. httpcore retains the original URL origin, so the HTTP Host
header and HTTPS SNI/certificate hostname remain the original public hostname.
"""

import inspect
import re
import socket
import ssl
import time
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlsplit

import dns.exception
import dns.resolver
import httpcore
from bs4 import BeautifulSoup

from .urls import canonical_public_url, is_public_ip


class _DeadlineExceeded(Exception):
    pass


def _bounded_timeout(requested: Optional[float], remaining: float) -> float:
    if remaining <= 0:
        raise _DeadlineExceeded("Fetch deadline exceeded.")
    if requested is None:
        return remaining
    return min(float(requested), remaining)


class DeadlineNetworkStream:
    """Applies one absolute deadline to every socket and TLS operation."""

    def __init__(self, stream: Any, deadline: float, clock: Callable[[], float]) -> None:
        self.stream = stream
        self.deadline = deadline
        self.clock = clock

    def _timeout(self, timeout: Optional[float]) -> float:
        return _bounded_timeout(timeout, self.deadline - self.clock())

    def read(self, max_bytes: int, timeout: Optional[float] = None) -> bytes:
        return self.stream.read(max_bytes, timeout=self._timeout(timeout))

    def write(self, buffer: bytes, timeout: Optional[float] = None) -> None:
        self.stream.write(buffer, timeout=self._timeout(timeout))

    def close(self) -> None:
        self.stream.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> "DeadlineNetworkStream":
        secured = self.stream.start_tls(
            ssl_context,
            server_hostname=server_hostname,
            timeout=self._timeout(timeout),
        )
        return DeadlineNetworkStream(secured, self.deadline, self.clock)

    def get_extra_info(self, info: str) -> Any:
        return self.stream.get_extra_info(info)


class PinnedNetworkBackend:
    def __init__(
        self,
        pinned_ip: str,
        backend: Optional[Any] = None,
        deadline: Optional[float] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.pinned_ip = pinned_ip
        self.backend = backend or httpcore.SyncBackend()
        self.deadline = deadline
        self.clock = clock

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[Any]] = None,
    ) -> Any:
        if self.deadline is not None:
            timeout = _bounded_timeout(timeout, self.deadline - self.clock())
        stream = self.backend.connect_tcp(
            self.pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
        if self.deadline is None:
            return stream
        return DeadlineNetworkStream(stream, self.deadline, self.clock)

    def connect_unix_socket(self, path: str, timeout: Optional[float] = None) -> Any:
        if self.deadline is not None:
            timeout = _bounded_timeout(timeout, self.deadline - self.clock())
        stream = self.backend.connect_unix_socket(path, timeout=timeout)
        if self.deadline is None:
            return stream
        return DeadlineNetworkStream(stream, self.deadline, self.clock)

    def sleep(self, seconds: float) -> None:
        if self.deadline is not None:
            seconds = _bounded_timeout(seconds, self.deadline - self.clock())
        self.backend.sleep(seconds)


class DeadlineDNSResolver:
    """Resolve all A/AAAA answers, including CNAME chains, within one lifetime."""

    def __init__(self, resolver: Optional[Any] = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.resolver = resolver or dns.resolver.Resolver()
        self.clock = clock

    def __call__(self, hostname: str, port: int, lifetime: float) -> List[str]:
        del port
        deadline = self.clock() + max(0.001, float(lifetime))
        addresses: List[str] = []
        for record_type in ("A", "AAAA"):
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError("DNS resolution timeout.")
            try:
                answer = self.resolver.resolve(
                    hostname,
                    record_type,
                    lifetime=remaining,
                    search=False,
                    raise_on_no_answer=False,
                )
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                continue
            except (dns.exception.Timeout, dns.resolver.LifetimeTimeout) as exc:
                raise TimeoutError("DNS resolution timeout.") from exc
            if answer.rrset is None:
                continue
            addresses.extend(str(item.address) for item in answer)
        if not addresses:
            raise OSError("DNS returned no A or AAAA answers.")
        return list(dict.fromkeys(addresses))


class _HttpcoreStreamResponse:
    def __init__(self, pool: Any, context: Any, response: Any) -> None:
        self.pool = pool
        self.context = context
        self.response = response
        self.status = response.status
        self.headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in response.headers
        }
        self.closed = False

    def iter_bytes(self) -> Iterable[bytes]:
        return self.response.iter_stream()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.context.__exit__(None, None, None)
        finally:
            self.pool.close()


def _default_transport(
    url: str,
    pinned_ip: str,
    timeout: float,
    hostname: str,
    deadline: float,
    clock: Callable[[], float],
) -> _HttpcoreStreamResponse:
    del hostname  # The original hostname remains in url for Host, SNI, and certificate checks.
    pool = httpcore.ConnectionPool(
        ssl_context=ssl.create_default_context(),
        network_backend=PinnedNetworkBackend(pinned_ip, deadline=deadline, clock=clock),
        retries=0,
        max_connections=1,
        max_keepalive_connections=0,
    )
    context = pool.stream(
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
    try:
        response = context.__enter__()
    except Exception:
        pool.close()
        raise
    return _HttpcoreStreamResponse(pool, context, response)


def _accepts_arguments(callable_: Callable[..., Any], *args: Any) -> bool:
    try:
        inspect.signature(callable_).bind(*args)
    except (TypeError, ValueError):
        return False
    return True


class SafePublicFetcher:
    def __init__(
        self,
        resolver: Optional[Callable[..., Iterable[str]]] = None,
        transport: Optional[Callable[..., Any]] = None,
        max_redirects: int = 3,
        timeout: float = 8.0,
        max_response_bytes: int = 1_000_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.clock = clock
        self.resolver = resolver or DeadlineDNSResolver(clock=clock)
        self.transport = transport or _default_transport
        self.max_redirects = max(0, min(int(max_redirects), 3))
        self.timeout = max(0.001, float(timeout))
        self.max_response_bytes = max(1, int(max_response_bytes))

    def fetch_page(self, url: str) -> Dict[str, Any]:
        current = canonical_public_url(url)
        if current is None:
            return {"url": str(url), "error": "URL is not a valid public HTTP(S) target."}

        deadline = self.clock() + self.timeout
        redirects = 0
        while True:
            try:
                remaining = self._remaining(deadline)
            except _DeadlineExceeded as exc:
                return {"url": current, "error": str(exc)}
            parsed = urlsplit(current)
            hostname = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            addresses = self._literal_addresses(hostname)
            if addresses is None:
                try:
                    addresses = list(dict.fromkeys(self._resolve(hostname, port, remaining)))
                except TimeoutError:
                    return {"url": current, "error": "DNS resolution timeout."}
                except Exception as exc:
                    return {"url": current, "error": f"DNS resolution failed: {str(exc) or exc.__class__.__name__}"}

            if not addresses or any(not is_public_ip(address) for address in addresses):
                return {"url": current, "error": "DNS target is not entirely public."}

            response = None
            try:
                remaining = self._remaining(deadline)
                response = self._open_transport(current, addresses[0], remaining, hostname, deadline)
                status = self._status(response)
                headers = self._headers(response)
                if status in {301, 302, 303, 307, 308} and headers.get("location"):
                    if redirects >= self.max_redirects:
                        return {"url": current, "error": "Redirect limit exceeded."}
                    redirected = canonical_public_url(urljoin(current, headers["location"]))
                    if redirected is None:
                        return {"url": current, "error": "Redirect target is not a valid public URL."}
                    redirects += 1
                    current = redirected
                    continue

                raw = self._read_body(response, headers, deadline)
                return self._page_result(current, status, headers, raw)
            except _DeadlineExceeded as exc:
                return {"url": current, "error": str(exc)}
            except Exception as exc:
                return {"url": current, "error": f"Page fetch failed: {str(exc) or exc.__class__.__name__}"}
            finally:
                self._close_response(response)

    def _resolve(self, hostname: str, port: int, remaining: float) -> Iterable[str]:
        args = (hostname, port, remaining)
        if _accepts_arguments(self.resolver, *args):
            return self.resolver(*args)
        return self.resolver(hostname, port)

    def _open_transport(
        self,
        url: str,
        pinned_ip: str,
        remaining: float,
        hostname: str,
        deadline: float,
    ) -> Any:
        args = (url, pinned_ip, remaining, hostname, deadline, self.clock)
        if _accepts_arguments(self.transport, *args):
            return self.transport(*args)
        return self.transport(url, pinned_ip, remaining)

    @staticmethod
    def _literal_addresses(hostname: str) -> Optional[List[str]]:
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                socket.inet_pton(family, hostname)
                return [hostname]
            except OSError:
                continue
        return None

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise _DeadlineExceeded("Fetch deadline exceeded.")
        return remaining

    @staticmethod
    def _status(response: Any) -> int:
        value = response.get("status", 0) if isinstance(response, dict) else getattr(response, "status", 0)
        return int(value)

    @staticmethod
    def _headers(response: Any) -> Dict[str, str]:
        raw_headers = response.get("headers", {}) if isinstance(response, dict) else getattr(response, "headers", {})
        headers = {}
        for key, value in dict(raw_headers or {}).items():
            normalized_key = key.decode("latin-1") if isinstance(key, bytes) else str(key)
            normalized_value = value.decode("latin-1") if isinstance(value, bytes) else str(value)
            headers[normalized_key.lower()] = normalized_value
        return headers

    def _read_body(self, response: Any, headers: Dict[str, str], deadline: float) -> bytes:
        content_length = headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_response_bytes:
                    raise ValueError("Response byte limit exceeded.")
            except ValueError as exc:
                if "exceeded" in str(exc):
                    raise
        if isinstance(response, dict):
            if "body" in response:
                chunks = response["body"]
            else:
                chunks = [response.get("content", b"")]
        elif hasattr(response, "iter_bytes"):
            chunks = response.iter_bytes()
        else:
            chunks = getattr(response, "body", ())

        body = bytearray()
        iterator = iter(chunks)
        while True:
            self._remaining(deadline)
            try:
                chunk = next(iterator)
            except StopIteration:
                break
            self._remaining(deadline)
            if not isinstance(chunk, bytes):
                chunk = str(chunk).encode("utf-8", errors="replace")
            if len(body) + len(chunk) > self.max_response_bytes:
                raise ValueError("Response byte limit exceeded.")
            body.extend(chunk)
        return bytes(body)

    @staticmethod
    def _close_response(response: Any) -> None:
        if response is None:
            return
        close = response.get("close") if isinstance(response, dict) else getattr(response, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _page_result(url: str, status: int, headers: Dict[str, str], raw: bytes) -> Dict[str, Any]:
        content_type = headers.get("content-type", "text/html").lower()
        if "text/html" not in content_type and not content_type.startswith("text/"):
            return {"url": url, "status": status, "error": f"Non-text content: {content_type}"}
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        return {"url": url, "status": status, "title": title, "text": text[:15000]}


__all__ = ["DeadlineDNSResolver", "PinnedNetworkBackend", "SafePublicFetcher"]
