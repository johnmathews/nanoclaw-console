"""The FastAPI app: the healthcheck, the JSON views under /api/, and the built web app.

The console holds no NanoClaw access of its own (docs/architecture.md §2): it reads NanoClaw only
through the broker's socket and Loki. Every request but `GET /healthz` passes the Access check
first (§4.2), including the web app's static files. The only writes are the four actions
(§4.8), each a `POST` behind the CSRF guard and the audit log in `actions.py`.
"""

import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx2
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .access import AccessMiddleware, AccessVerifier
from .actions import ACTIONS, ID_PATTERN, ActionRunner, audit_view
from .audit import AuditLog
from .broker_client import BrokerClient
from .config import Settings
from .loki import LokiClient
from .ttl_cache import DEFAULT_TTL, TtlCache
from .views import (
    Context,
    NotFound,
    Unavailable,
    groups_view,
    overview_view,
    permissions_view,
    problems_view,
    task_detail,
    tasks_view,
)

NO_STORE = {"Cache-Control": "no-store"}


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


@dataclass
class Services:
    """The long-lived parts: clients, the verifier, the Loki cache and the clock."""

    settings: Settings
    verifier: AccessVerifier
    broker: BrokerClient
    loki: LokiClient | None
    cache: TtlCache
    clock: Callable[[], datetime]
    audit: AuditLog
    actions: ActionRunner

    @classmethod
    def build(
        cls,
        settings: Settings,
        *,
        jwks_transport: httpx2.AsyncBaseTransport | None = None,
        loki_transport: httpx2.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> "Services":
        broker = BrokerClient(settings.broker_socket)
        audit = AuditLog(settings.audit_dir)
        now = clock or (lambda: datetime.now(UTC))
        return cls(
            settings=settings,
            verifier=AccessVerifier(
                team_domain=settings.access_team_domain,
                audience=settings.access_aud,
                allowed_emails=settings.allowed_emails,
                transport=jwks_transport,
            ),
            broker=broker,
            loki=LokiClient(settings.loki_url, transport=loki_transport)
            if settings.loki_url
            else None,
            cache=TtlCache(DEFAULT_TTL, time.monotonic),
            clock=now,
            audit=audit,
            actions=ActionRunner(
                broker=broker, audit=audit, origin=settings.console_origin, clock=now
            ),
        )

    def context(self) -> Context:
        return Context(
            broker=self.broker,
            loki=self.loki,
            cache=self.cache,
            timezone=self.settings.timezone,
            now=self.clock(),
        )


def create_app(settings: Settings, *, services: Services | None = None) -> FastAPI:
    """The app; `services` is injectable for tests (fake transports, a fixed clock)."""
    svc = services or Services.build(settings)
    app = FastAPI(
        title="NanoClaw console",
        # No interactive docs: the API is the web app's, not a public surface.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(AccessMiddleware, verifier=svc.verifier)

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        """The container healthcheck. No auth, and nothing about NanoClaw: only that we answer."""
        return {"ok": True}

    def view(build: Callable[[Context], Awaitable[dict[str, Any]]]) -> Callable[[], Any]:
        async def handler() -> JSONResponse:
            return JSONResponse(await build(svc.context()), headers=NO_STORE)

        return handler

    app.get("/api/overview")(view(overview_view))
    app.get("/api/groups")(view(groups_view))
    app.get("/api/tasks")(view(tasks_view))
    app.get("/api/permissions")(view(permissions_view))
    app.get("/api/problems")(view(problems_view))

    @app.get("/api/tasks/{series_id}")
    async def task(series_id: str) -> JSONResponse:
        if ID_PATTERN.fullmatch(series_id) is None:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=NO_STORE)
        try:
            body = await task_detail(svc.context(), series_id)
        except NotFound:
            return JSONResponse({"error": "not_found"}, status_code=404, headers=NO_STORE)
        except Unavailable as exc:
            return JSONResponse(
                {"error": "broker_unavailable", "code": exc.code},
                status_code=503,
                headers=NO_STORE,
            )
        return JSONResponse(body, headers=NO_STORE)

    @app.get("/api/audit")
    def audit() -> JSONResponse:
        return JSONResponse(audit_view(svc.audit, svc.clock()), headers=NO_STORE)

    def not_found() -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404, headers=NO_STORE)

    @app.post("/api/tasks/{series_id}/{name}")
    async def task_action(request: Request, series_id: str, name: str) -> JSONResponse:
        action = ACTIONS.get(("task", name))
        if action is None:
            return not_found()
        return await svc.actions.handle(request, action, series_id)

    @app.post("/api/groups/{group_id}/{name}")
    async def group_action(request: Request, group_id: str, name: str) -> JSONResponse:
        action = ACTIONS.get(("group", name))
        if action is None:
            return not_found()
        return await svc.actions.handle(request, action, group_id)

    static_dir = settings.static_dir
    if static_dir is not None and static_dir.is_dir():
        app.mount("/", SpaFiles(directory=static_dir, html=True), name="web")

    return app


def create_app_from_env() -> FastAPI:
    """The app as the container runs it (uvicorn --factory), configured from the environment."""
    return create_app(Settings.from_env(os.environ))
