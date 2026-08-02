"""掌问本地服务 — FastAPI 入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zhangwen.auth.middleware import AuthSessionMiddleware
from zhangwen.auth.router import router as auth_router
from zhangwen.artifacts.router import router as artifacts_router
from zhangwen.cad_agent.router import router as cad_agent_router
from zhangwen.cad_agent.router import stop_cad_coordinator
from zhangwen.code_agent.router import router as code_agent_router
from zhangwen.config import settings
from zhangwen.chat.router import router as chat_router
from zhangwen.clarification.router import router as clarification_router
from zhangwen.devices.router import router as devices_router, shutdown_device_services
from zhangwen.device_lab.router import (
    router as device_lab_router,
    shutdown_device_lab_services,
)
from zhangwen.creator.router import (
    ensure_creator_job_runner,
    router as creator_router,
    stop_creator_job_runner,
)
from zhangwen.creator.delivery import CreatorDeliveryService
from zhangwen.experts.router import router as agent_packages_router
from zhangwen.hardware.router import router as hardware_router
from zhangwen.health.router import router as health_router
from zhangwen.lesson_agent.router import router as lesson_agent_router
from zhangwen.local_bridge.router import router as local_bridge_router
from zhangwen.mvp.router import router as mvp_router
from zhangwen.orchestrator.router import router as orchestrator_router
from zhangwen.project_packages.router import router as project_packages_router
from zhangwen.projects.router import router as projects_router
from zhangwen.proposals.router import router as proposals_router
from zhangwen.settings.router import router as settings_router
from zhangwen.skills.router import router as skills_router
from zhangwen.solutions.router import router as solutions_router
from zhangwen.specs.router import router as specs_router
from zhangwen.v2.router import router as v2_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    CreatorDeliveryService(settings.data_dir).recover_incomplete_imports()
    await ensure_creator_job_runner()
    try:
        yield
    finally:
        await stop_creator_job_runner()
        await shutdown_device_services()
        await shutdown_device_lab_services()
        await stop_cad_coordinator()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

# 本地账号会话保护全部业务 API；CORS 作为外层中间件覆盖认证错误响应。
app.add_middleware(AuthSessionMiddleware)

# CORS — 仅允许受信任的本地开发和 Tauri UI 来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Zhangwen-Host",
        "X-Zhangwen-Capability-Token",
        "X-Zhangwen-Bridge-Lease",
        "X-Zhangwen-Bridge-Request-Id",
    ],
)

# 路由
app.include_router(health_router)
app.include_router(local_bridge_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(projects_router)
app.include_router(chat_router)
app.include_router(clarification_router)
app.include_router(solutions_router)
app.include_router(proposals_router)
app.include_router(artifacts_router)
app.include_router(orchestrator_router)
app.include_router(agent_packages_router)
app.include_router(skills_router)
app.include_router(specs_router)
app.include_router(code_agent_router)
app.include_router(cad_agent_router)
app.include_router(lesson_agent_router)
app.include_router(devices_router)
app.include_router(device_lab_router)
app.include_router(project_packages_router)
app.include_router(mvp_router)
app.include_router(hardware_router)
app.include_router(v2_router)
app.include_router(creator_router)
