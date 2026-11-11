"""Local-only E2E composition. Optional feature modules are explicit test seams."""

from contextlib import asynccontextmanager
from dataclasses import replace
from importlib import import_module

from app.main import create_app as create_foundation_app
from safevoice_shared.config import AppConfig


def optional_module(name: str):
    try:
        return import_module(name)
    except ModuleNotFoundError as error:
        # An existing module with a broken dependency must fail, never fall back.
        if error.name == name or name.startswith((error.name or "") + "."):
            return None
        raise


def _fixture_config() -> AppConfig:
    """The E2E process has no Voyage key. Start on the fixture on purpose, announced in the log,
    then the lifespan below swaps in the real pgvector retriever over the seeded corpus."""
    base = AppConfig()
    return replace(base, knowledge=replace(base.knowledge, retriever="fixture"))


def create_app():
    app = create_foundation_app(cfg=_fixture_config())
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            if application.state.settings.app_env != "test":
                raise ValueError("Scripted E2E app requires APP_ENV=test")
            scenarios = optional_module("safevoice_agent.testing.scripted_scenarios")
            if scenarios is not None:
                application.state.runtime = scenarios.build_e2e_runtime(application.state.cfg)
            # Phase 2 owns this optional factory. Absence is expected before P2.
            knowledge = optional_module("app.modules.knowledge.testing")
            if knowledge is not None:
                application.state.knowledge = knowledge.build_e2e_retriever(
                    application.state.engine, application.state.cfg
                )
            yield

    app.router.lifespan_context = lifespan
    return app
