import ipaddress
import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def canonical_public_url(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None

    hostname = hostname.rstrip(".").lower()
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        return None
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            return None
        if len(hostname) > 253 or any(not _DNS_LABEL.fullmatch(label) for label in hostname.split(".")):
            return None
    else:
        if not is_public_ip(str(address)):
            return None
        hostname = address.compressed

    default_port = 443 if scheme == "https" else 80
    host_for_netloc = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_for_netloc if port in (None, default_port) else f"{host_for_netloc}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def canonical_hostname(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


__all__ = ["canonical_hostname", "canonical_public_url", "is_public_ip"]
