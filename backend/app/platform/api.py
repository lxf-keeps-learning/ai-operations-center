from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.platform.schemas.overview_schema import PlatformOverviewResponse
from app.platform.services.overview_service import OverviewService


router = APIRouter(tags=["Platform"])
overview_service = OverviewService()


@router.get("/platform/overview", response_model=ApiResponse[PlatformOverviewResponse])
def get_overview(db: Session = Depends(get_db)) -> ApiResponse[PlatformOverviewResponse]:
    return ApiResponse(data=overview_service.get_overview(db))
