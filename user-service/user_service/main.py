from fastapi import FastAPI

from user_service.routes import users
from common.app import create_base_app

app: FastAPI = create_base_app()
app.include_router(users.router)
