from ipaddress import ip_address

from fastapi import HTTPException, Request


def check_peer(request: Request) -> None:
    settings = request.app.state.settings
    try:
        peer = ip_address(request.client.host) if request.client else None
    except ValueError:
        peer = None
    if peer is None or not any(peer in network for network in settings.ingest_networks):
        raise HTTPException(403, "Origem fora das redes de ingestão")


def check_ingestion(request: Request) -> None:
    check_peer(request)
    settings = request.app.state.settings
    if len(request.scope["query_string"]) > settings.max_query_bytes:
        raise HTTPException(414, "Query excede o limite")
    if request.headers.get("transfer-encoding") or request.headers.get("content-length", "0") != "0":
        raise HTTPException(413, "Envie os parâmetros na query de GET")
