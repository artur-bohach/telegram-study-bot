from study_assistant_bot.bot.handlers.sections import router as sections_router
from study_assistant_bot.bot.handlers.start import router as start_router

ROUTERS = (start_router, sections_router)

__all__ = ["ROUTERS"]
