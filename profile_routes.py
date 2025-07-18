# profile_routes.py or inside auth_routes.py
from schemas import TeacherRead, TeacherUpdate, EmailSync, TeacherProfileRead
from model import TeacherProfile
from database import get_db
from dependencies import get_current_teacher
from service_auth import verify_service_jwt
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlmodel import Session, select
from typing import Annotated
from httpx import AsyncClient
from config import settings
from logger import logger



router = APIRouter(prefix="/api")

    


@router.patch("/update-profile")
async def update_my_profile(
    data: TeacherUpdate,
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db),
    
):
    logger.info(f"Updating profile for teacher: {getattr(current_teacher, 'id', None)} with data: {data.model_dump(exclude_unset=True)}")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_teacher, field, value)

    db.add(current_teacher)
    db.commit()
    db.refresh(current_teacher)
    logger.info(f"Profile updated for teacher: {getattr(current_teacher, 'id', None)}")
    return {"message":"Successfully updated profile"}

@router.post(
    "/deactivate-teacher"    
)
async def deactivate_teacher(
    request:Request    
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
                "intSAuthorization":f"Bearer {auth_header}",
                "Authorization":f"Bearer {settings.SERVICE_JWT}"
            } # Corrected "AUthorization" to "Authorization"
        )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            logger.error(f"Deactivation failed with status {resp.status_code}: {detail}")
            raise HTTPException(
                status_code = resp.status_code,
                detail = detail
            )

        logger.info("Teacher deactivated successfully")
        return {"message":"successful deactivation",}