"""本地元件管理系统入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import configure_database, init_db
from app.importers.normalizers import ImportValidationError
from app.routes import bom_library, boms, components, data_management, inventory, orders, pages, storage
from app.services import BusinessRuleError


def create_app(database_url: str | None = None) -> FastAPI:
    if database_url is not None:
        configure_database(database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        yield

    application = FastAPI(title="元件管理系统", lifespan=lifespan)
    application.state.import_previews = {}
    application.mount("/static", StaticFiles(directory="static"), name="static")
    application.include_router(pages.router)
    application.include_router(components.router)
    application.include_router(bom_library.router)
    application.include_router(storage.router)
    application.include_router(boms.router)
    application.include_router(orders.router)
    application.include_router(inventory.router)
    application.include_router(data_management.router)

    @application.exception_handler(BusinessRuleError)
    async def business_rule_error(_: Request, exc: BusinessRuleError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(ImportValidationError)
    async def import_validation_error(_: Request, exc: ImportValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, reload_excludes=["*.db", "*.db-*"])
