from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadLimit:
    """Limita multipart antes de buffering, inclusive transferências sem Content-Length."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/import"):
            await self.app(scope, receive, send)
            return
        limit = 3 * 1024 * 1024
        received = 0
        for name, value in scope["headers"]:
            if name.lower() == b"content-length":
                try:
                    size = int(value)
                except ValueError:
                    size = limit + 1
                if not 0 <= size <= limit:
                    await JSONResponse({"detail": "Upload excede o limite."}, status_code=413)(
                        scope, receive, send
                    )
                    return

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(413, "Upload excede o limite.")
            return message

        await self.app(scope, bounded_receive, send)
