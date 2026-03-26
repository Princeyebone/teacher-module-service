from app.schemas.schemas import TeacherRead, TeacherUpdate, EmailSync, TeacherProfileRead
from app.models.model import TeacherProfile
from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.core.service_auth import verify_service_jwt
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import Annotated
from httpx import AsyncClient
from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/api")

@router.patch("/update-profile")
async def update_my_profile(
    data: TeacherUpdate,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Updating profile for teacher: {getattr(current_teacher, 'id', None)} with data: {data.model_dump(exclude_unset=True)}")
    try:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(current_teacher, field, value)

        db.add(current_teacher)
        await db.commit()
        await db.refresh(current_teacher)
        logger.info(f"Profile updated for teacher: {getattr(current_teacher, 'id', None)}")
        return {"message": "Successfully updated profile"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating profile for teacher {getattr(current_teacher, 'id', None)}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error updating profile: {str(e)}")

@router.post("/deactivate-teacher")
async def deactivate_teacher(
    request: Request    
):
    logger.info("Received request to deactivate teacher")
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning("Missing Authorization header in deactivate_teacher request")
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    async with AsyncClient(verify=False) as client:
        logger.info("Sending deactivation request to core service")
        resp = await client.post(
            f"{settings.CORE_SERVICE_URL}/api/register-teacher",
            headers={
                "intSAuthorization": f"Bearer {auth_header}",
                "Authorization": f"Bearer {settings.SERVICE_JWT}"
            }
        )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            logger.error(f"Deactivation failed with status {resp.status_code}: {detail}")
            raise HTTPException(
                status_code=resp.status_code,
                detail=detail
            )

        logger.info("Teacher deactivated successfully")
        return {"message": "successful deactivation"}