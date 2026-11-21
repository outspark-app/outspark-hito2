from uuid import uuid4

from starlette.responses import JSONResponse, Response

MAX_BODY = 16 * 1024
ORIGINS = {
    "http://127.0.0.1:5177",
    "http://localhost:5177",
    "http://127.0.0.1:5178",
    "http://localhost:5178",
}


class RequestBoundary:
    """Limita también cuerpos fragmentados; la demo no acepta hosts ni orígenes externos."""

    def __init__(self, app, local_demo=False):
        self.app, self.local_demo = app, local_demo

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        scope["request_id"] = str(uuid4())
        origin = headers.get("origin")
        allowed_origins = ORIGINS
        if self.local_demo:
            host = headers.get("host", "").split(":")[0]
            # Swagger is served by this API. Browser writes include its own Origin.
            allowed_origins = ORIGINS | {
                f"{scope.get('scheme', 'http')}://{headers.get('host', '')}"
            }
            if host not in ("127.0.0.1", "localhost", "testserver") or (
                origin and origin not in allowed_origins
            ):
                return await JSONResponse(
                    {"error": {"code": "local_origin", "message": "Origen local no permitido."}},
                    403,
                )(scope, receive, send)
            if scope["method"] == "OPTIONS":
                if origin not in allowed_origins:
                    return await JSONResponse({"error": {"code": "local_origin"}}, 403)(
                        scope, receive, send
                    )
                return await Response(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type,Idempotency-Key,X-Demo-User",
                    },
                )(scope, receive, send)
        try:
            if int(headers.get("content-length", "0")) > MAX_BODY:
                return await JSONResponse(
                    {"error": {"code": "body_limit", "message": "Payload demasiado grande."}}, 413
                )(scope, receive, send)
        except ValueError:
            return await JSONResponse({"error": {"code": "invalid_body"}}, 400)(
                scope, receive, send
            )
        body = b""
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return
            body += message.get("body", b"")
            if len(body) > MAX_BODY:
                return await JSONResponse(
                    {"error": {"code": "body_limit", "message": "Payload demasiado grande."}}, 413
                )(scope, receive, send)
            if not message.get("more_body"):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        async def respond(message):
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"x-request-id", scope["request_id"].encode()),
                    (b"cache-control", b"no-store"),
                ]
                if self.local_demo and origin in allowed_origins:
                    message["headers"] += [
                        (b"access-control-allow-origin", origin.encode()),
                        (b"vary", b"Origin"),
                    ]
            await send(message)

        await self.app(scope, replay, respond)
