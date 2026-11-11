from ipaddress import IPv6Address, ip_address

from fastapi import Request

from app.core.config import Settings


def client_ip(request: Request, settings: Settings) -> str:
    """The caller's address for rate limiting.

    X-Forwarded-For is honoured only when the direct peer is a configured trusted proxy, and the
    rightmost address that is not itself a trusted proxy is used, so a client cannot spoof its way out
    of a rate limit by sending its own header.
    """
    peer = request.client.host if request.client else "unknown"
    try:
        address = ip_address(peer)
        peer = (
            str(address.ipv4_mapped)
            if isinstance(address, IPv6Address) and address.ipv4_mapped
            else str(address)
        )
    except ValueError:
        return "unknown"
    if not settings.is_trusted_proxy(peer):
        return peer
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if len(hops) > 16:
        return peer
    try:
        # Refuse malformed chains as a whole; do not let attacker-controlled text become a quota key.
        hops = [str(ip_address(hop)) for hop in hops]
    except ValueError:
        return peer
    for hop in reversed(hops):
        if not settings.is_trusted_proxy(hop):
            return hop
    return hops[0] if hops else peer
