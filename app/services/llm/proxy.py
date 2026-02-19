"""
LLM Proxy helper.

Usage:
    Set LLM_PROXY_URL in .env:
        LLM_PROXY_URL=socks5://127.0.0.1:3128    # Shadowsocks local SOCKS5
        LLM_PROXY_URL=http://127.0.0.1:3128      # HTTP/HTTPS proxy

    Inside Docker, the host is reachable via:
        - host.docker.internal  (Docker Desktop / mac)
        - The host's docker bridge IP, e.g. 172.17.0.1 (Linux)
        So set LLM_PROXY_URL=socks5://172.17.0.1:3128 (or host.docker.internal:3128)

NOTE: SOCKS5 requires either 'socksio' or 'httpx[socks]' installed.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def get_proxy_transport(proxy_url: Optional[str]) -> Optional[httpx.AsyncHTTPTransport]:
    """
    Returns an httpx AsyncHTTPTransport configured for the proxy,
    or None if no proxy is configured.
    """
    if not proxy_url:
        return None

    logger.info(f"LLM proxy enabled: {proxy_url}")

    # httpx >= 0.24 accepts mounts dict for SOCKS/HTTP proxies
    return None  # unused — we use proxies= kwarg directly


def build_async_client(proxy_url: Optional[str], timeout: int = 60) -> httpx.AsyncClient:
    """
    Build an httpx.AsyncClient optionally routed through a proxy.

    Supports:
        - socks5://host:port   (requires 'socksio' package)
        - socks5h://host:port  (DNS resolved by proxy)
        - http://host:port
        - https://host:port
    """
    if proxy_url:
        logger.debug(f"Using proxy for LLM request: {proxy_url}")
        return httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy_url,
        )
    return httpx.AsyncClient(timeout=timeout)
