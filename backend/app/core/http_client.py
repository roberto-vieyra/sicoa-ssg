"""Único punto de creación de clientes salientes: CA del sistema y proxy corporativo."""

import ssl

import httpx

TIMEOUT = httpx.Timeout(connect=3.0, read=6.0, write=6.0, pool=3.0)


def http_client() -> httpx.Client:
    return httpx.Client(
        verify=ssl.create_default_context(), trust_env=True, http2=False, timeout=TIMEOUT
    )


def async_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        verify=ssl.create_default_context(), trust_env=True, http2=False, timeout=TIMEOUT
    )
