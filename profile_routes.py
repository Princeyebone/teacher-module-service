# profile_routes.py or inside auth_routes.py
from schemas import TeacherRead, TeacherUpdate, EmailSync
from model import Teacher
from database import get_db
from dependencies import get_current_teacher
from service_auth import verify_service_jwt
from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import Annotated



router = APIRouter(prefix="/teachers")


@router.get("/me", response_model=TeacherRead)
async def get_my_profile(current_teacher:Annotated[Teacher, Depends(get_current_teacher)] ):
    return current_teacher


@router.patch("/me", response_model=TeacherRead)
async def update_my_profile(
    data: TeacherUpdate,
    current_teacher:Annotated[Teacher, Depends(get_current_teacher)],
    session: Session = Depends(get_db),
    
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_teacher, field, value)

    session.add(current_teacher)
    session.commit()
    session.refresh(current_teacher)
    return current_teacher

@router.delete("/me", status_code=204)
async def delete_my_account(
    current_teacher:Annotated[Teacher, Depends(get_current_teacher)],
    session: Session = Depends(get_db)
):
    current_teacher.is_active = False
    session.add(current_teacher)
    session.commit()

# teacher_module/profile_routes.py
#
@router.post("/sync-email",dependencies=[Depends(verify_service_jwt)] )
async def sync_email(data: EmailSync, session: Session = Depends(get_db)):
    teacher = session.exec(select(Teacher).where(Teacher.email == data.old_email)).first()
    if not teacher:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teacher not found")
    teacher.email = data.new_email
    session.add(teacher)
    session.commit()
    return {"message": "Local email updated."}

# teacher_module/profile_routes.py

class SyncProfile(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    bio: str | None = None

@router.post(
    "/sync-profile",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_service_jwt)],
    summary="Create or update teacher profile (internal)"
)
async def sync_profile(
    data: SyncProfile,
    session: Session = Depends(get_db)
):
    # Upsert pattern: create or update existing
    existing = session.exec(select(Teacher).where(Teacher.email == data.email)).first()
    if existing:
        existing.first_name = data.first_name
        existing.last_name  = data.last_name
        existing.bio        = data.bio
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return {"message": "Profile updated", "teacher_id": existing.id}

    new_teacher = Teacher(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        bio=data.bio
    )
    session.add(new_teacher)
    session.commit()
    session.refresh(new_teacher)
    return {"message": "Profile created", "teacher_id": new_teacher.id}
