from fastapi import APIRouter, HTTPException, status, Depends, Request
from schemas import TeacherRegistrationRequest
from httpx import AsyncClient
from config import settings
from sqlmodel import Session
from database import get_db
from uuid import UUID
from model import TeacherProfile
from sqlalchemy.exc import IntegrityError
from logger import logger
from dependencies import get_current_teacher



router = APIRouter(tags=["Athentication/Registration"])

@router.post(
    "/register-teacher",
    status_code=status.HTTP_201_CREATED,
    summary="Standalone teacher Registration Module",
)
async def register_teacher(
    data:TeacherRegistrationRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"Received teacher registration request for: {data.email}")
    async with AsyncClient(verify=False) as client:
        logger.info(f"Sending registration request for teacher: {data.email} to core service")
        resp = await client.post(
            f"{settings.CORE_SERVICE_URL}/api/register-teacher",
            json = data.model_dump(),
            headers={"intSAuthorization":f"Bearer {settings.SERVICE_JWT}"}
        )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            logger.error(f"Registration failed for {data.email} with status {resp.status_code}: {detail}")
            raise HTTPException(
                status_code = resp.status_code,
                detail = detail
            )
        
        respond_data = resp.json()
        individual_id_str = respond_data.get("user_id")
        logger.info(f"Teacher registered in core service with user_id: {individual_id_str}")

        try:
            new_teacher = TeacherProfile(individual_id=UUID(individual_id_str))
            db.add(new_teacher)
            db.commit()
            db.refresh(new_teacher)
            logger.info(f"TeacherProfile created in local DB for user_id: {individual_id_str}")
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"IntegrityError while creating TeacherProfile for user_id: {individual_id_str}: {e}")

        return {"message":"successful registration check your email for activation link",}
    


@router.get("/central-me")
async def get_full_profile(
    request: Request,
    current_teacher = Depends(get_current_teacher),
):
    logger.info(f"Received request for central user info (teacher: {getattr(current_teacher, 'id', None)})")
    # --- 1) Local teacher‐module profile (SQLModel -> dict) ---
    # Assuming `current_teacher` is a SQLModel instance
    teacher_data = current_teacher.dict()  

    # --- 2) Forward user token to Central ERP `/api/me` ---
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid token in /central-me request")
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    service_token = settings.SERVICE_JWT

    logger.info("Sending request to core service /api/me endpoint")
    async with AsyncClient(verify=False) as client:
        central_resp = await client.get(
            f"{settings.CORE_SERVICE_URL}/api/me",
            headers={
                "Authorization": auth_header,
                "intSAuthorization": f"Bearer {service_token}"
            },
            timeout=5.0
        )

    if central_resp.status_code != 200:
        logger.error(f"Central ERP error: {central_resp.status_code} - {central_resp.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Central ERP error: {central_resp.text}"
        )

    central_json = central_resp.json()
    logger.info("Successfully fetched user info from ERP")

    # --- 3) Return both raw JSON blobs directly ---
    return {
        "central": central_json,
        "teacher": teacher_data
    }
