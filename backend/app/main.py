
from fastapi import FastAPI

from app.routes.order_routes import router as order_router
from app.services.database_service import create_database_tables

app = FastAPI(
    title="Internet Order Automation API",
    description="API for receiving and managing internet connection orders.",
    version="1.0.0"
)


@app.on_event("startup")
def startup_event():
    create_database_tables()


app.include_router(order_router)


@app.get("/")
def home():
    return {
        "message": "Internet Order Automation API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
