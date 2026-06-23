"""
FastAPI app for the Prospectus-Kernel platform agents.
Entry point that assembles all route modules.
"""
import logging
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from agents.runtime import initialize_memory_managers, shutdown_memory_managers_async
from agents.config import CHROMA_PATH, get_locale_instance
from agents.routes.management import router as management_router
from agents.routes.leads import router as leads_router
from agents.routes.messaging import router as messaging_router
from agents.routes.research import router as research_router
from agents.routes.discourse import router as discourse_router
from agents.routes.resonance import router as resonance_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Prospectus-Kernel API", description="API for Prospectus-Kernel platform agents")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": get_locale_instance().get_fallback("internal_error")},
    )


# ── Lifecycle ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Prospectus-Kernel API...")
    await initialize_memory_managers({"chroma": {"path": CHROMA_PATH}})
    logger.info("Memory managers initialized")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Prospectus-Kernel API...")
    await shutdown_memory_managers_async()
    logger.info("Memory managers shut down")


# ── Routes ────────────────────────────────────────────────────────────────

app.include_router(management_router)
app.include_router(leads_router)
app.include_router(messaging_router)
app.include_router(research_router)
app.include_router(discourse_router)
app.include_router(resonance_router)


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
