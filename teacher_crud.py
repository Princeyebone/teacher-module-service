from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select
from model import TeacherProfile
from uuid import UUID
from schemas import TeacherUpdate
from httpx import AsyncClient
from config import settings
import logging

router = APIRouter(tags=["Teacher CRUD"])
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def verify_teacher_access(
    db: Session,
    teacher_id: UUID,
    current_user: dict
) -> TeacherProfile:
    """Shared verification logic for teacher operations"""
    teacher = db.get(TeacherProfile, teacher_id)
    if not teacher:
        logger.error(f"Teacher not found: {teacher_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )
    
    # Add any additional permission checks here if needed
    return teacher

@router.get("/read-teacher/{teacher_id}", summary="Get teacher details")
async def get_teacher(
    
    teacher_id: UUID,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        teacher = await verify_teacher_access(db, teacher_id, current_user)
        return teacher
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching teacher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve teacher"
        )

@router.get("/", summary="List all teachers")
async def get_teachers(
    current_user: Annotated[dict, Depends(get_current_teacher)],
    db: Annotated[Session, Depends(get_db)]
):
    try:
        return db.exec(select(TeacherProfile)).all()
    except Exception as e:
        logger.error(f"Error fetching teachers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve teachers"
        )

@router.patch("/{teacher_id}", summary="Update teacher")
async def update_teacher(
    current_user: Annotated[dict, Depends(get_current_teacher)],
    teacher_id: UUID,
    data: TeacherUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        teacher = await verify_teacher_access(db, teacher_id, current_user)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(teacher, key, value)

        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return teacher
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating teacher: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update teacher"
        )

@router.post("/{teacher_id}/deactivate", summary="Deactivate teacher")
async def deactivate_teacher(
    current_user: Annotated[dict, Depends(get_current_teacher)],
    teacher_id: UUID,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        teacher = await verify_teacher_access(db, teacher_id, current_user)
        
        async with AsyncClient() as client:
            resp = await client.post(
                f"{settings.CORE_SERVICE_URL}/api/deactivate",
                headers={"Authorization": f"Bearer {settings.SERVICE_JWT}"},
                params={"individual_id": teacher.individual_id}
            )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            logger.error(f"Auth service error: {detail}")
            raise HTTPException(
                status_code=resp.status_code,
                detail=detail
            )
            
        return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating teacher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not deactivate teacher"
        )

@router.delete("/{teacher_id}", summary="Delete teacher")
async def delete_teacher(
    current_user: Annotated[dict, Depends(get_current_teacher)],
    teacher_id: UUID,
    db: Annotated[Session, Depends(get_db)]
):
    try:
        teacher = await verify_teacher_access(db, teacher_id, current_user)
        
        # Only allow deletion if teacher isn't linked to auth system
        if teacher.individual_id is None:
            db.delete(teacher)
            db.commit()
            return {"message": "Teacher deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete teacher with active authentication record"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting teacher: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete teacher"
        )