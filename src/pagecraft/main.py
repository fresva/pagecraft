import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pagecraft.config import Settings
from pagecraft.database import get_db, init_db
from pagecraft.demo import demo_handler
from pagecraft.mcp_server.server import mcp as mcp_server
from pagecraft.orchestrator.mcp_bridge import MCPBridge
from pagecraft.orchestrator.prompt_loader import PromptLoader
from pagecraft.registry import load_component_registry
from pagecraft.routes import interview, preview
from pagecraft.routes import websocket as ws_route

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    await init_db(settings.db_path)
    app.state.db = await get_db(settings.db_path)
    app.state.mcp_bridge = MCPBridge(mcp_server)
    app.state.prompt_loader = PromptLoader(settings.prompts_dir)

    # Set up LLM client if Azure credentials are configured
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from pagecraft.orchestrator.llm_client import LLMClient
        app.state.llm_client = LLMClient(settings)
        logger.info("LLM client configured — using real conversation engine")
    else:
        app.state.llm_client = None
        logger.info("No Azure credentials — using demo mode")

    yield
    await app.state.db.close()


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title="PageCraft", debug=settings.debug, lifespan=lifespan)

    # Logging
    logging.basicConfig(level=settings.debug and logging.DEBUG or logging.INFO)

    # Static files and templates
    pkg_dir = Path(__file__).parent
    app.mount("/static", StaticFiles(directory=pkg_dir / "static"), name="static")

    from jinja2 import ChainableUndefined
    templates = Jinja2Templates(directory=pkg_dir / "templates")
    templates.env.undefined = ChainableUndefined
    app.state.templates = templates
    app.state.settings = settings
    app.state.component_registry = load_component_registry()
    app.state.demo_handler = demo_handler

    # Routes
    app.include_router(interview.router)
    app.include_router(preview.router)
    app.include_router(ws_route.router)

    return app


app = create_app()
