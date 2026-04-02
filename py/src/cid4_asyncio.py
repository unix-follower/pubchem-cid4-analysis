from __future__ import annotations

import argparse
import asyncio
import logging
import ssl

import log_settings
from cid4_api import ApiResponse, resolve_data_dir, resolve_server_config, route_api_request

LOGGER = logging.getLogger(__name__)
MAX_REQUEST_HEAD_BYTES = 16_384


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CID 4 asyncio HTTPS server.")
    parser.add_argument("--host", help="Override the bind host.")
    parser.add_argument("--port", type=int, help="Override the bind port.")
    return parser


def main() -> None:
    log_settings.configure_logging()
    args = build_argument_parser().parse_args()

    data_dir = resolve_data_dir()
    server_config = resolve_server_config(
        data_dir,
        preferred_host_env_names=("ASYNCIO_HOST",),
        preferred_port_env_names=("ASYNCIO_PORT",),
    )

    host = args.host or server_config.host
    port = args.port or server_config.port
    ssl_context = build_ssl_context(server_config)

    asyncio.run(serve(host, port, data_dir, ssl_context))


async def serve(host: str, port: int, data_dir, ssl_context: ssl.SSLContext) -> None:
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(reader, writer, data_dir),
        host=host,
        port=port,
        ssl=ssl_context,
    )

    LOGGER.info("AsyncIO API server listening on https://%s:%s", host, port)
    async with server:
        await server.serve_forever()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, data_dir) -> None:
    response = ApiResponse(status_code=400, body='{"message":"Malformed HTTP request"}')

    try:
        request_head = await _read_request_head(reader)
        if request_head:
            response = build_response_from_request_head(request_head, data_dir)
    except TimeoutError:
        LOGGER.info("Timed out reading request head from client")
    except ConnectionError:
        LOGGER.info("Client disconnected before request completion")
    except Exception:
        LOGGER.exception("Unexpected asyncio server error")
        response = ApiResponse(status_code=500, body='{"message":"Internal server error"}')

    try:
        writer.write(render_http_response(response).encode("utf-8"))
        await writer.drain()
    except ConnectionError:
        LOGGER.info("Client disconnected before response completion")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            LOGGER.info("Connection closed while waiting for writer shutdown")


def build_response_from_request_head(request_head: str, data_dir) -> ApiResponse:
    request_line = request_head.split("\r\n", 1)[0]
    parts = request_line.split()
    if len(parts) != 3:
        return ApiResponse(status_code=400, body='{"message":"Malformed HTTP request"}')

    method, target, http_version = parts
    if not http_version.startswith("HTTP/"):
        return ApiResponse(status_code=400, body='{"message":"Malformed HTTP request"}')

    return route_api_request(method, target, data_dir, "asyncio", "AsyncIO")


def render_http_response(response: ApiResponse) -> str:
    reason = _reason_phrase(response.status_code)
    lines = [
        f"HTTP/1.1 {response.status_code} {reason}",
        f"Content-Type: {response.content_type}",
        "Access-Control-Allow-Origin: *",
        "Access-Control-Allow-Methods: GET, OPTIONS",
        "Access-Control-Allow-Headers: Content-Type",
        "Connection: close",
    ]
    if response.status_code == 405:
        lines.append("Allow: GET, OPTIONS")
    lines.append(f"Content-Length: {len(response.body.encode('utf-8'))}")
    lines.append("")
    lines.append(response.body)
    return "\r\n".join(lines)


def build_ssl_context(server_config) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        certfile=str(server_config.cert_file),
        keyfile=str(server_config.key_file),
        password=server_config.key_password,
    )
    return context


async def _read_request_head(reader: asyncio.StreamReader) -> str:
    buffer = bytearray()
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            break
        buffer.extend(chunk)
        if b"\r\n\r\n" in buffer:
            return bytes(buffer).split(b"\r\n\r\n", 1)[0].decode("utf-8", errors="replace")
        if len(buffer) > MAX_REQUEST_HEAD_BYTES:
            break
    return ""


def _reason_phrase(status_code: int) -> str:
    return {
        200: "OK",
        204: "No Content",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }.get(status_code, "OK")


if __name__ == "__main__":
    main()
