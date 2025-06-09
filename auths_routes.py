from fastapi import APIRouter, HTTPException, status, Depends
from schemas import TeacherRegistrationRequest
from httpx import AsyncClient
from config import settings
from sqlmodel import Session
from database import get_db
from uuid import UUID
from model import Teacher
from sqlalchemy.exc import IntegrityError
from service_auth import verify_service_jwt

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
    async with AsyncClient(verify=False) as client:
        resp = await client.post(
            f"{settings.CORE_SERVICE_URL}/api/register-teacher",
            json = data.model_dump(),
            headers={"Authorization":f"Bearer {settings.SERVICE_JWT}"} # Corrected "AUthorization" to "Authorization"
        )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            raise HTTPException(
                status_code = resp.status_code,
                detail = detail
            )
        
        respond_data = resp.json()
        individual_id_str = respond_data.get("user_id")

        try:

            new_teacher = Teacher(individual_id=UUID(individual_id_str))
            db.add(new_teacher)
            db.commit()
            db.refresh(new_teacher)

        except IntegrityError:
            db.rollback()

        return {"message":"successful registration check your email for activation link",}