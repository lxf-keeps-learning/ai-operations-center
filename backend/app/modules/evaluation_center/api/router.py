from fastapi import APIRouter

from app.modules.evaluation_center.api.evaluation_routes import router as evaluation_router

router = APIRouter()
router.include_router(evaluation_router)
