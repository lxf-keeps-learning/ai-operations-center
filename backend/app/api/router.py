from fastapi import APIRouter

from app.api.routes import agent, conversations, feedback, health, items, prompts

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
