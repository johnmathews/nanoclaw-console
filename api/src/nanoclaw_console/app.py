"""The FastAPI app: the healthcheck, the JSON API under /api/, and the built web app.

The console holds no NanoClaw access of its own (docs/architecture.md §2). The view APIs that read
NanoClaw through the broker replace the /api/overview placeholder in a later unit.
"""

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

DEFAULT_STATIC_DIR = Path("/app/static")


class SpaFiles(StaticFiles):
    """The built web app: a real file when there is one, else index.html for a client route.

    A path under api/ stays a 404, so a mistyped API call never gets HTML with a 200. Starlette's
    StaticFiles resolves every path inside the directory, which keeps `..` out.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(static_dir: Path | None) -> FastAPI:
    """The app; `static_dir` is the built web app (web/dist), served when it exists."""
    app = FastAPI(
        title="NanoClaw console",
        # No interactive docs: the API is the web app's, not a public surface.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        """The container healthcheck. No auth, and nothing about NanoClaw: only that we answer."""
        return {"ok": True}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        """Placeholder until the view APIs read NanoClaw through the broker."""
        return {"status": "scaffold"}

    if static_dir is not None and static_dir.is_dir():
        app.mount("/", SpaFiles(directory=static_dir, html=True), name="web")

    return app


def create_app_from_env() -> FastAPI:
    """The app as the container runs it (uvicorn --factory); STATIC_DIR overrides the default."""
    return create_app(Path(os.environ.get("STATIC_DIR", str(DEFAULT_STATIC_DIR))))
