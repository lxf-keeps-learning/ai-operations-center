from fastapi import APIRouter

from app.modules.failure_center.api.failure_routes import router as failure_router

router = APIRouter()
router.include_router(failure_router)
