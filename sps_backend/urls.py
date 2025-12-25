from fastapi import APIRouter
from apps.users.urls import router as users_router

root_router = APIRouter()

# Route traffic to the "users" app with a prefix
root_router.include_router(users_router, prefix="/users", tags=["Users"])