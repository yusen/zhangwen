"""掌问本地服务 — 单一正式 FastAPI 入口。"""

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from zhangwen.artifacts.router import router as artifacts_router
from zhangwen.auth.middleware import AuthSessionMiddleware
from zhangwen.auth.router import router as auth_router
from zhangwen.cad_agent.router import router as cad_agent_router
from zhangwen.cad_agent.router import stop_cad_coordinator
from zhangwen.clarification.router import router as clarification_router
from zhangwen.code_agent.router import router as code_agent_router
from zhangwen.config import settings
from zhangwen.creator.delivery import CreatorDeliveryService
from zhangwen.creator.router import (
    ensure_creator_job_runner,
    stop_creator_job_runner,
)
from zhangwen.device_lab.router import (
    recover_device_lab_runs,
    router as device_lab_router,
    shutdown_device_lab_services,
)
from zhangwen.devices.router import router as devices_router, shutdown_device_services
from zhangwen.domains.events.router import router as realtime_router
from zhangwen.domains.classroom.router import router as classroom_router
from zhangwen.domains.events.runtime import (
    realtime_event_hub,
    stop_realtime_event_hubs,
)
from zhangwen.domains.inventory.router import router as inventory_router
from zhangwen.domains.mqtt_service.router import (
    recover_mqtt_service,
    router as mqtt_service_router,
    shutdown_mqtt_service,
)
from zhangwen.domains.orchestration.router import router as orchestration_router
from zhangwen.domains.packages.router import router as packages_router
from zhangwen.domains.packages.watcher import (
    package_workspace_watcher,
    stop_package_workspace_watchers,
)
from zhangwen.domains.runs.router import router as runs_router
from zhangwen.domains.works.canvas import WorkCanvasService
from zhangwen.domains.works.router import router as works_router
from zhangwen.experts.router import router as agent_packages_router
from zhangwen.hardware.router import router as hardware_router
from zhangwen.health.router import router as health_router
from zhangwen.lesson_agent.router import router as lesson_agent_router
from zhangwen.local_bridge.router import router as local_bridge_router
from zhangwen.orchestrator.router import router as orchestrator_router
from zhangwen.project_packages.router import router as project_packages_router
from zhangwen.projects.router import router as projects_router
from zhangwen.proposals.router import router as proposals_router
from zhangwen.settings.router import router as settings_router
from zhangwen.skills.router import router as skills_router
from zhangwen.solutions.router import router as solutions_router
from zhangwen.specs.router import router as specs_router


_LEGACY_API_PREFIXES = ("/api/projects",)


@asynccontextmanager
async def lifespan(_: FastAPI):
    CreatorDeliveryService(settings.data_dir).recover_incomplete_imports()
    WorkCanvasService(settings.data_dir).recover_interrupted()
    recover_device_lab_runs()
    recover_mqtt_service()
    await realtime_event_hub(settings.data_dir).start()
    await package_workspace_watcher(settings.data_dir).start()
    await ensure_creator_job_runner()
    try:
        yield
    finally:
        await stop_creator_job_runner()
        await stop_package_workspace_watchers()
        await shutdown_device_services()
        await shutdown_device_lab_services()
        shutdown_mqtt_service()
        await stop_cad_coordinator()
        await stop_realtime_event_hubs()


def create_application() -> FastAPI:
    """Build the single packaged application."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    @application.exception_handler(RequestValidationError)
    async def redact_sensitive_validation_inputs(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors: list[dict[str, object]] = []
        for raw in exc.errors():
            item = dict(raw)
            location = tuple(str(part).lower() for part in item.get("loc", ()))
            if any(
                sensitive in part
                for part in location
                for sensitive in (
                    "password",
                    "secret",
                    "credential",
                    "token",
                    "api_key",
                    "apikey",
                )
            ):
                item["input"] = "**********"
            errors.append(item)
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": errors}),
        )

    @application.middleware("http")
    async def mark_compatibility_apis_deprecated(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in _LEGACY_API_PREFIXES
        ):
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = '</api/works>; rel="successor-version"'
        return response

    application.add_middleware(AuthSessionMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Last-Event-ID",
            "X-Zhangwen-Host",
            "X-Zhangwen-Capability-Token",
            "X-Zhangwen-Bridge-Lease",
            "X-Zhangwen-Bridge-Request-Id",
        ],
    )

    for formal_router in (
        health_router,
        local_bridge_router,
        auth_router,
        settings_router,
        classroom_router,
        works_router,
        runs_router,
        orchestration_router,
        realtime_router,
        packages_router,
        inventory_router,
        mqtt_service_router,
    ):
        application.include_router(formal_router)

    migration_router = APIRouter()
    for compatibility_router in (
        projects_router,
        clarification_router,
        solutions_router,
        proposals_router,
        artifacts_router,
        orchestrator_router,
        agent_packages_router,
        skills_router,
        specs_router,
        code_agent_router,
        cad_agent_router,
        lesson_agent_router,
        devices_router,
        device_lab_router,
        project_packages_router,
        hardware_router,
    ):
        migration_router.include_router(compatibility_router)
    application.include_router(migration_router, include_in_schema=False)

    return application


app = create_application()
