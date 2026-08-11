class ManualClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeStreamResponse:
    def __init__(self, chunks, *, status=200, headers=None):
        self.status = status
        self.headers = headers or {"content-type": "text/html"}
        self.chunks = chunks
        self.closed = False

    def iter_bytes(self):
        yield from self.chunks

    def close(self):
        self.closed = True


def test_safe_fetch_rejects_hostname_when_any_dns_answer_is_private():
    from app.services.agents.safe_fetch import SafePublicFetcher

    transport_calls = []
    fetcher = SafePublicFetcher(
        resolver=lambda host, port: ["93.184.216.34", "10.0.0.7"],
        transport=lambda url, pinned_ip, timeout: transport_calls.append((url, pinned_ip)),
    )

    result = fetcher.fetch_page("https://public.example/article")

    assert "error" in result
    assert "public" in result["error"].lower()
    assert transport_calls == []


def test_safe_fetch_revalidates_private_redirect_before_second_request():
    from app.services.agents.safe_fetch import SafePublicFetcher

    calls = []

    def resolver(host, port):
        return {"public.example": ["93.184.216.34"], "internal.example": ["192.168.1.8"]}[host]

    def transport(url, pinned_ip, timeout):
        calls.append((url, pinned_ip))
        return {"status": 302, "headers": {"location": "http://internal.example/admin"}, "content": b""}

    result = SafePublicFetcher(resolver=resolver, transport=transport).fetch_page(
        "https://public.example/start"
    )

    assert "error" in result
    assert len(calls) == 1
    assert calls[0][1] == "93.184.216.34"


def test_safe_fetch_enforces_redirect_limit_and_revalidates_every_hop():
    from app.services.agents.safe_fetch import SafePublicFetcher

    calls = []

    def transport(url, pinned_ip, timeout):
        calls.append(url)
        return {"status": 302, "headers": {"location": f"{url}/next"}, "content": b""}

    fetcher = SafePublicFetcher(
        resolver=lambda host, port: ["93.184.216.34"],
        transport=transport,
        max_redirects=1,
    )
    result = fetcher.fetch_page("https://public.example/start")

    assert "redirect limit" in result["error"].lower()
    assert len(calls) == 2


def test_pinned_backend_connects_to_validated_address_not_original_hostname():
    from app.services.agents.safe_fetch import PinnedNetworkBackend

    calls = []

    class Delegate:
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            calls.append((host, port, timeout))
            return object()

    backend = PinnedNetworkBackend("93.184.216.34", backend=Delegate())
    stream = backend.connect_tcp("public.example", 443, timeout=2.0)

    assert stream is not None
    assert calls == [("93.184.216.34", 443, 2.0)]


def test_deadline_pinned_stream_preserves_original_hostname_for_tls_sni():
    from app.services.agents.safe_fetch import PinnedNetworkBackend

    tls_names = []

    class RawStream:
        def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            tls_names.append((server_hostname, timeout))
            return self

        def get_extra_info(self, info):
            return None

        def close(self):
            pass

    class Delegate:
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            return RawStream()

    stream = PinnedNetworkBackend(
        "93.184.216.34",
        backend=Delegate(),
        deadline=5.0,
        clock=lambda: 0.0,
    ).connect_tcp("public.example", 443, timeout=4.0)
    secured = stream.start_tls(object(), server_hostname="public.example", timeout=3.0)

    assert secured is not None
    assert tls_names == [("public.example", 3.0)]


def test_safe_fetch_rejects_invalid_and_private_targets_without_transport():
    from app.services.agents.safe_fetch import SafePublicFetcher

    calls = []
    fetcher = SafePublicFetcher(
        resolver=lambda host, port: ["93.184.216.34"],
        transport=lambda url, pinned_ip, timeout: calls.append(url),
    )

    for url in (
        "http://127.0.0.1/private",
        "https://bad_label.example/private",
        "https://-bad.example/private",
    ):
        assert "error" in fetcher.fetch_page(url)

    assert calls == []


def test_safe_fetch_passes_remaining_lifetime_and_reports_dns_timeout_without_transport():
    from app.services.agents.safe_fetch import SafePublicFetcher

    clock = ManualClock()
    lifetimes = []
    transport_calls = []

    def resolver(host, port, lifetime):
        lifetimes.append(lifetime)
        clock.advance(lifetime)
        raise TimeoutError("DNS deadline expired")

    result = SafePublicFetcher(
        resolver=resolver,
        transport=lambda *args: transport_calls.append(args),
        timeout=2.0,
        clock=clock,
    ).fetch_page("https://public.example/article")

    assert lifetimes == [2.0]
    assert "dns" in result["error"].lower()
    assert "timeout" in result["error"].lower()
    assert transport_calls == []


def test_safe_fetch_aborts_oversized_stream_and_always_closes_response():
    from app.services.agents.safe_fetch import SafePublicFetcher

    response = FakeStreamResponse([b"<html>", b"0123456789", b"</html>"])
    result = SafePublicFetcher(
        resolver=lambda host, port, lifetime: ["93.184.216.34"],
        transport=lambda *args: response,
        max_response_bytes=12,
    ).fetch_page("https://public.example/article")

    assert "response byte limit" in result["error"].lower()
    assert response.closed is True


def test_safe_fetch_trickle_stream_cannot_extend_past_monotonic_total_deadline():
    from app.services.agents.safe_fetch import SafePublicFetcher

    clock = ManualClock()
    response = FakeStreamResponse([])

    def chunks():
        clock.advance(0.6)
        yield b"<html>"
        clock.advance(0.6)
        yield b"still arriving"

    response.chunks = chunks()
    result = SafePublicFetcher(
        resolver=lambda host, port, lifetime: ["93.184.216.34"],
        transport=lambda *args: response,
        timeout=1.0,
        clock=clock,
    ).fetch_page("https://public.example/article")

    assert "deadline" in result["error"].lower()
    assert response.closed is True


def test_safe_fetch_normal_stream_preserves_original_host_metadata_and_pinned_ip():
    from app.services.agents.safe_fetch import SafePublicFetcher

    observed = []
    response = FakeStreamResponse([b"<html><title>Safe</title><body>Readable evidence</body></html>"])

    def transport(url, pinned_ip, timeout, hostname, deadline, clock):
        observed.append(
            {
                "url": url,
                "pinned_ip": pinned_ip,
                "hostname": hostname,
                "host_header": hostname,
                "tls_server_name": hostname,
            }
        )
        return response

    result = SafePublicFetcher(
        resolver=lambda host, port, lifetime: ["93.184.216.34"],
        transport=transport,
    ).fetch_page("https://Public.Example:443/article#fragment")

    assert result["status"] == 200
    assert result["url"] == "https://public.example/article"
    assert result["title"] == "Safe"
    assert observed == [
        {
            "url": "https://public.example/article",
            "pinned_ip": "93.184.216.34",
            "hostname": "public.example",
            "host_header": "public.example",
            "tls_server_name": "public.example",
        }
    ]
    assert response.closed is True
