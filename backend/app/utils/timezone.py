from datetime import datetime

from zoneinfo import ZoneInfo

from app.config.settings import settings


def now_local() -> datetime:
    return datetime.now(ZoneInfo(settings.app_timezone)).replace(tzinfo=None)
