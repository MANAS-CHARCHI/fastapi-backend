
from fastapi import FastAPI
from celery import Celery
from urls import root_router
import os
import jwt

app = FastAPI()

celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

# celery_app.autodiscover_tasks(['send_email', 'user'], related_name='tasks')

# Configure Celery to use JSON serialization
celery_app.conf.update(
    # TTL: Results are removed from Redis after 1 hour
    result_expires=360,

    # RELIABILITY: Task is removed from queue ONLY after success
    task_acks_late=True,

    task_serializer="json",
    result_serializer="json",
    accept_content=["json"]
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Connect the central routing system
app.include_router(root_router)