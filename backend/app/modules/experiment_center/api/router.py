from fastapi import APIRouter

from app.modules.experiment_center.api.experiment_routes import router as experiment_router

router = APIRouter()
router.include_router(experiment_router)
