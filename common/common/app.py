from fastapi import FastAPI

from common.middlewares.logging import logging_middleware

def create_base_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(logging_middleware)
    return app