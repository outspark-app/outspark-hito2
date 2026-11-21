import socket
import time

import uvicorn


class HttpServer:
    def __init__(self, app, port):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", port))
        self.server_port = self.socket.getsockname()[1]
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.server_port,
                log_level="error",
                access_log=False,
                lifespan="off",
            )
        )

    def serve_forever(self):
        self.server.run(sockets=[self.socket])

    def wait_ready(self):
        deadline = time.monotonic() + 5
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("El servidor HTTP no arrancó")
            time.sleep(0.01)

    def shutdown(self):
        self.server.should_exit = True

    def server_close(self):
        self.socket.close()


def make_server(app, port):
    return HttpServer(app, port)


def lambda_call(adapter, event):
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return adapter(event, None)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def lambda_adapter(app):
    def invoke(event, context):
        from mangum import Mangum

        return Mangum(app, lifespan="off")(event, context)

    return invoke
