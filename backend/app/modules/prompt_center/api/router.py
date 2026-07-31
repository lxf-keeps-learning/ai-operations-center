from fastapi import APIRouter

from app.modules.prompt_center.api.prompt_routes import router as prompt_router
from app.modules.prompt_center.api.prompt_version_routes import router as version_router
from app.modules.prompt_center.api.prompt_test_routes import router as test_router
from app.modules.prompt_center.api.prompt_release_routes import router as release_router

router = APIRouter(prefix="/prompt-center", tags=["Prompt 管理中心"])

router.include_router(prompt_router)
router.include_router(version_router)
router.include_router(test_router)
router.include_router(release_router)
