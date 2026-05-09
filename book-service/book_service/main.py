from fastapi import FastAPI

from book_service.routes import books
from common.app import create_base_app

app: FastAPI = create_base_app()
app.include_router(books.router)
