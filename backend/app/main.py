
from fastapi import FastAPI

app = FastAPI(
    title="Internet Order Automation API",
    description="API for automating customer internet orders",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "status": "success",
        "message": "Internet Order Automation API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
