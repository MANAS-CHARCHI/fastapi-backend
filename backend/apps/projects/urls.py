from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from . import views, schemas
from apps.users.decorators import login_required, role_required
from typing import Optional
from fastapi import Request, Form, UploadFile, File

router = APIRouter()

@router.post("/upload", response_model=dict)
@login_required
async def upload_project(
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    file: UploadFile = File(...),
    request: Request = None
):
    return await views.upload_project_view(
        db=db, 
        name=name, 
        file=file, 
        request=request
    )

@router.put("/update/{project_id}", response_model=dict)
@login_required
async def update_project(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    return await views.update_project_view(
        db=db,
        request=request,
        project_id=project_id,
        file=file,
    )

@router.put("/change-version/{project_id}", response_model=dict)
@login_required
async def change_version(
    project_id: int,
    version_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    return await views.change_version_view(db, request, project_id, version_id)

@router.get("/versions/{project_id}", response_model=dict)
@login_required
async def get_versions(
    project_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    return await views.get_versions_view(db, request, project_id)

@router.delete("/delete/{project_id}", response_model=dict)
@login_required
async def delete_project(
    project_id: int,
    version_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    return await views.delete_project_view(db, request, project_id, version_id)

@router.get("/all", response_model=dict)
@login_required
async def get_all_projects(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    return await views.get_all_project_view(db, request)

@router.get("/admin/user/{user_email}", response_model=dict)
@login_required
@role_required("admin")
async def get_user_project(
    user_email: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    return await views.get_user_project_view(db, request, user_email)