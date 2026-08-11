"""Custom provider URL validation, including basic SSRF destination checks."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeProviderURL(ValueError):
    code = "unsafe_url"


def validate_provider_url(url: str, *, allow_local: bool = False, resolve_host: bool = True) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise UnsafeProviderURL("provider URL must use HTTPS")
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise UnsafeProviderURL("provider URL contains unsupported components")
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise UnsafeProviderURL("provider URL is malformed") from exc
    host = parsed.hostname.rstrip(".").lower()
    local = _is_local_host(host)
    # Local destinations are an explicit opt-in for *both* HTTP and HTTPS.
    # HTTPS does not make a loopback/private destination safe: it can still be
    # used to reach a host-local admin service or cloud metadata endpoint.
    if local and not allow_local:
        raise UnsafeProviderURL("local provider URLs require explicit opt-in")
    if parsed.scheme == "http" and not (allow_local and local):
        raise UnsafeProviderURL("HTTP is permitted only for explicitly allowed local services")
    if not local and resolve_host:
        addresses = _resolve(host, port or 443)
        if not addresses:
            raise UnsafeProviderURL("provider host could not be resolved")
        for address in addresses:
            if _unsafe_ip(address) and not allow_local:
                raise UnsafeProviderURL("provider URL resolves to a private or reserved address")
    return url.rstrip("/")


def _is_local_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(host)
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        )
    except ValueError:
        return False


def _resolve(host: str, port: int) -> set[str]:
    try:
        return {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except (OSError, socket.gaierror):
        return set()


def _unsafe_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


validate_custom_url = validate_provider_url
