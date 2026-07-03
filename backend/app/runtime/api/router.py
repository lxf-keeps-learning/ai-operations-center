from fastapi import APIRouter

from app.runtime.api.conversation_api import router as conversation_router
from app.runtime.api.session_api import router as session_router
from app.runtime.api.prompt_api import router as prompt_router
from app.runtime.api.trace_api import router as trace_router
from app.runtime.api.feedback_api import router as feedback_router
from app.runtime.api.chat_api import router as chat_router
from app.runtime.api.runtime_chat_api import router as runtime_chat_router

runtime_router = APIRouter()
runtime_router.include_router(conversation_router, tags=["Runtime"])
runtime_router.include_router(session_router, tags=["Runtime"])
runtime_router.include_router(prompt_router, tags=["Runtime"])
runtime_router.include_router(trace_router, tags=["Runtime"])
runtime_router.include_router(feedback_router, tags=["Runtime"])
runtime_router.include_router(chat_router, tags=["Runtime"])
runtime_router.include_router(runtime_chat_router, tags=["Runtime"])
