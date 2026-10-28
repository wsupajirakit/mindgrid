"""Outbound HTTP rules for every call the server makes on someone's behalf (connectors,
webhooks, callbacks): https only and a public address, unless the host is explicitly
allowed (an internal service). Redirects are never followed by callers of this module."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from mindgrid.core.config import AppSettings, CommaList, env_field, settings_getter


class OutboundSettings(AppSettings):
    allow_private_hosts: CommaList = env_field(
        "MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS",
        (),
        doc="Hosts outbound calls may reach although they resolve to a private or loopback "
        "address (also allowed over plain http), e.g. an internal service.",
    )


get_settings = settings_getter(OutboundSettings)


class BlockedTargetError(RuntimeError):
    """The URL may not be called (scheme or address)."""


def is_allowed_host(host: str) -> bool:
    return host in get_settings().allow_private_hosts


async def check(url: str) -> None:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host:
        raise BlockedTargetError("the URL has no host")
    if is_allowed_host(host):
        return
    if parts.scheme != "https":
        raise BlockedTargetError("outbound calls use https (allow the host to use http)")
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, parts.port or 443, type=socket.SOCK_STREAM
    )
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise BlockedTargetError(
                f"{host} resolves to a non-public address; allow it explicitly"
            )
