"""A minimal HTTP/1.1 server on 127.0.0.1, enough for the hook and the web page."""
from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qsl, urlsplit

MAX_BODY = 1 << 20
REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 409: "Conflict", 500: "Server Error"}


def reply(status, data, content_type="application/json"):
    body = data if isinstance(data, bytes) else json.dumps(data).encode()
    return status, content_type, body


async def _handle(handler, reader, writer):
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length") or 0)
        if length > MAX_BODY:
            raise ValueError("body too large")
        body = await asyncio.wait_for(reader.readexactly(length), 5) if length else b""
        url = urlsplit(target)
        status, ctype, out = await handler(method, url.path, dict(parse_qsl(url.query)), headers, body)
    except Exception as e:  # noqa: BLE001  report any failure to the client, keep serving
        status, ctype, out = reply(500 if not isinstance(e, ValueError) else 400, {"error": str(e)})
    try:
        writer.write(
            f"HTTP/1.1 {status} {REASONS.get(status, 'OK')}\r\nContent-Type: {ctype}\r\n"
            f"Content-Length: {len(out)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + out)
        await writer.drain()
    finally:
        writer.close()


async def serve(handler, port=0):
    server = await asyncio.start_server(lambda r, w: _handle(handler, r, w), "127.0.0.1", port)
    return server, server.sockets[0].getsockname()[1]
