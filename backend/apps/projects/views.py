from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Response, Request, Form, UploadFile, File
import aioboto3
from sqlalchemy import select, exists, desc, update
from .models import Project, ProjectVersion
from apps.users.models import Users

class S3Service:
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        self.session = aioboto3.Session()

    async def add(self, file_obj, key: str):
        async with self.session.client("s3", region_name=self.region) as client:
            await client.upload_fileobj(
                Fileobj=file_obj,
                Bucket=self.bucket,
                Key=key,
            )

    async def remove(self, key: str):
        async with self.session.client("s3", region_name=self.region) as client:
            await client.delete_object(
                Bucket=self.bucket,
                Key=key,
            )

    async def delete_prefix(self, prefix: str):
        async with self.session.client("s3", region_name=self.region) as client:
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix
            ):
                objects = page.get("Contents", [])
                if not objects:
                    continue

                await client.delete_objects(
                    Bucket=self.bucket,
                    Delete={
                        "Objects": [
                            {"Key": obj["Key"]} for obj in objects
                        ],
                        "Quiet": True,
                    },
                )

s3 = S3Service(bucket="aws-manas-generic-sites")

async def upload_project_view(
    db: AsyncSession,
    request: Request,
    name: str = Form(...),
    file: UploadFile = File(...)
):
    # 1. Prevent duplicate project names
    stmt = select(exists().where(Project.name == name))
    project_exists = await db.scalar(stmt)

    if project_exists:
        raise HTTPException(status_code=400, detail="Project name already exists")

    # 2. Upload to S3 (STREAMING)
    s3_key = f"projects/{name}/v1/{file.filename}"
    try:
        await s3.add(file.file, s3_key)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"S3 Upload Failed: {str(e)}",
        )

    # 3. Database transaction
    try:
        user_id = request.state.user_id

        new_project = Project(
            name=name,
            owner_id=user_id,
        )
        db.add(new_project)
        await db.flush()  # get new_project.id

        first_version = ProjectVersion(
            project_id=new_project.id,
            version="v1",
            active=True,
        )
        db.add(first_version)

        await db.commit()

        return {
            "message": "Project uploaded successfully",
            "project_id": new_project.id,
            "s3_key": s3_key,
        }

    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database transaction failed",
        )
    
async def update_project_view(
    db: AsyncSession,
    request: Request,
    project_id: int,
    file: UploadFile = File(...)
):
    # 1. Validate project exists
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == request.state.user_id
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # 2. Get latest active version
    latest_version = await db.scalar(
        select(ProjectVersion)
        .where(
            ProjectVersion.project_id == project_id
        )
        .order_by(desc(ProjectVersion.id))
        .limit(1)
    )
    # 3. Compute next version
    if latest_version:
        latest_version.active = False
        current_version_number = int(latest_version.version.replace("v", ""))
        next_version = f"v{current_version_number + 1}"
    else:
        next_version = "v1"
    
    # 4. Upload file to S3
    s3_key = f"projects/{project.name}/{next_version}/{file.filename}"
    try:
        await s3.add(file.file, s3_key)

        # 5. Create new version
        new_version = ProjectVersion(
            project_id=project_id,
            version=next_version,
            active=True,
        )

        db.add(new_version)
        await db.commit()

        return {
            "message": "Project updated successfully",
            "project_id": project_id,
            "version": next_version,
            "s3_key": s3_key,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )

async def change_version_view(
    db: AsyncSession,
    request: Request,
    project_id: int,
    version_id: int
):
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == request.state.user_id
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # 2. Validate version exists and belongs to project
    target_version = await db.scalar(
        select(ProjectVersion)
        .where(
            ProjectVersion.id == version_id,
            ProjectVersion.project_id == project_id
        )
    )
    if not target_version:
        raise HTTPException(
            status_code=404,
            detail="Version does not exist for this project"
        )
    try:
        # 3. Deactivate all versions for this project
        await db.execute(
            update(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .values(active=False)
        )

        # 4. Activate requested version
        await db.execute(
            update(ProjectVersion)
            .where(ProjectVersion.id == version_id)
            .values(active=True)
        )

        await db.commit()

        return {
            "message": "Project version changed successfully",
            "project_id": project_id,
            "active_version_id": version_id,
            "version": target_version.version,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change version: {str(e)}"
        )

async def get_versions_view(
    db: AsyncSession,
    request: Request,
    project_id: int
):
    # 1. Validate project
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == request.state.user_id
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Fetch all versions
    result = await db.scalars(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.id)
    )
    all_versions = result.all()

    if not all_versions:
        raise HTTPException(status_code=404, detail="No versions exist")

    # 3. Serialize response
    return {
        "project_id": project_id,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "active": v.active,
                "created_at": v.created_at,
            }
            for v in all_versions
        ]
    }

async def delete_project_view(
    db: AsyncSession,
    request: Request,
    project_id: int,
    version_id:int
):
    # 1. Validate project
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == request.state.user_id
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # 2. Validate version belongs to project
    version = await db.scalar(
        select(ProjectVersion)
        .where(
            ProjectVersion.id == version_id,
            ProjectVersion.project_id == project_id
        )
    )
    if not version:
        raise HTTPException(
            status_code=404,
            detail="Version not found for this project"
        )
    try:
        # 3. Delete ALL files under version prefix
        version_prefix = f"projects/{project.name}/{version.version}/"
        await s3.delete_prefix(version_prefix)
        
        was_active = version.active
        # 4. Delete DB record
        await db.delete(version)
        await db.flush()
        # 5. Activate latest remaining version if needed
        if was_active:
            latest_version = await db.scalar(
                select(ProjectVersion)
                .where(ProjectVersion.project_id == project_id)
                .order_by(desc(ProjectVersion.id))
                .limit(1)
            )
            if latest_version:
                latest_version.active = True
        await db.commit()

        return {
            "message": "Project version deleted successfully",
            "project_id": project_id,
            "deleted_version": version.version,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Delete failed: {str(e)}"
        )

async def get_all_project_view(
    db: AsyncSession,
    request: Request
):
    result = await db.scalars(
        select(Project)
        .where(Project.owner_id == request.state.user_id)
        .order_by(Project.id.desc())
    )
    all_projects = result.all()
    if not all_projects:
        raise HTTPException(
            status_code=404,
            detail="No projects exist for you"
        )
    return {
        "projects": [
            {
                "id": project.id,
                "name": project.name,
            }
            for project in all_projects
        ]
    }


async def get_user_project_view(
    db: AsyncSession,
    request: Request,
    user_email: str
):
    # 1. Validate user by email
    user = await db.scalar(
        select(Users).where(Users.email == user_email)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Fetch user's projects
    result = await db.scalars(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.id.desc())
    )

    projects = result.all()

    if not projects:
        return {
            "user_email": user_email,
            "projects": []
        }

    # 3. Serialize response
    return {
        "user_email": user_email,
        "projects": [
            {
                "id": project.id,
                "name": project.name,
                "created_at": project.created_at,
            }
            for project in projects
        ]
    }