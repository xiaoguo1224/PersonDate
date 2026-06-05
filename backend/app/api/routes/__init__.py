from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.calendar_events import router as calendar_events_router
from app.api.routes.conflicts import router as conflicts_router
from app.api.routes.day_plans import router as day_plans_router
from app.api.routes.health import router as health_router
from app.api.routes.invite_codes import router as invite_codes_router
from app.api.routes.reminders import router as reminders_router
from app.api.routes.setup import router as setup_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(invite_codes_router)
api_router.include_router(users_router)
api_router.include_router(calendar_events_router)
api_router.include_router(agent_router)
api_router.include_router(tasks_router)
api_router.include_router(day_plans_router)
api_router.include_router(conflicts_router)
api_router.include_router(reminders_router)
