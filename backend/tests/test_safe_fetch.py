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
