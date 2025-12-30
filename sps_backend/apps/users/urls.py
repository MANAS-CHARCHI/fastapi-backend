from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from . import views, schemas
from apps.users.dependencies import is_authenticated

router = APIRouter()

@router.post("/register", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    return await views.create_user_view(user, db)

@router.get("/", response_model=list[schemas.UserResponse], dependencies=[Depends(is_authenticated)])
async def get_users(db: AsyncSession = Depends(get_db)):
    return await views.get_users_view(db)

@router.post("/login", response_model=schemas.UserLoginResponse)
async def login_user(form_data: schemas.UserLogin, db: AsyncSession = Depends(get_db), response = Response()):
    return await views.login_user_view(form_data, db, response)

@router.post("/activate/email={user_email}/activation_code={activation_code}", response_model=dict)
async def activate_user(user_email: str, activation_code: str, db: AsyncSession = Depends(get_db)):
    return await views.activate_user_view(user_email, activation_code, db)

@router.get("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    return await views.refresh_token_view(db, request, response)