from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from typing import Annotated, List, Dict, Any, Optional
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from model import TeacherProfile, GradeSystem
from dependencies import get_current_teacher
from database import get_db
from logger import logger
from schemas import GradeSystemResponse, GradeSystemCreate, GradeSystemUpdate, GradeRange


# Grade System Schemas

# Router
router = APIRouter(tags=["Grade Systems"])


@router.post("/create-grade-system", response_model=GradeSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_grade_system(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    grade_system_data: GradeSystemCreate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Creating grade system: name={grade_system_data.name}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not grade_system_data.name.strip():
            logger.error("Grade system name cannot be empty")
            raise HTTPException(status_code=400, detail="Grade system name cannot be empty")
        
        if not grade_system_data.grading_type.strip():
            logger.error("Grading type cannot be empty")
            raise HTTPException(status_code=400, detail="Grading type cannot be empty")

        # If this is marked as default, unset any existing default for this teacher
        if grade_system_data.is_default:
            # Update all existing default systems to non-default
            result = await db.execute(
                select(GradeSystem).where(
                    GradeSystem.teacher_id == current_teacher.id,
                    GradeSystem.is_default == True
                )
            )
            existing_defaults = result.scalars().all()
            for system in existing_defaults:
                system.is_default = False

        # Convert GradeRange objects to dictionaries for storage
        grade_ranges_dict = [
            {
                "id": range_obj.id,
                "min": range_obj.min,
                "max": range_obj.max,
                "grade": range_obj.grade,
                "description": range_obj.description
            }
            for range_obj in grade_system_data.grade_ranges
        ]

        # Create new grade system
        grade_system = GradeSystem(
            name=grade_system_data.name.strip(),
            teacher_id=current_teacher.id,
            grading_type=grade_system_data.grading_type.strip(),
            grade_ranges=grade_ranges_dict,
            is_default=grade_system_data.is_default
        )
        
        db.add(grade_system)
        await db.commit()
        await db.refresh(grade_system)

        logger.debug(f"Successfully created grade system: id={grade_system.id}, name={grade_system.name}")
        
        # Convert grade_ranges back to GradeRange objects for response
        grade_ranges_response = [
            GradeRange(
                id=range_dict["id"],
                min=range_dict["min"],
                max=range_dict["max"],
                grade=range_dict["grade"],
                description=range_dict.get("description")
            )
            for range_dict in grade_system.grade_ranges
        ]
        
        return GradeSystemResponse(
            id=grade_system.id,
            name=grade_system.name,
            teacher_id=grade_system.teacher_id,
            grading_type=grade_system.grading_type,
            grade_ranges=grade_ranges_response,
            is_default=grade_system.is_default,
            created_at=grade_system.created_at,
            updated_at=grade_system.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating grade system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating grade system: {str(e)}")


@router.get("/read-grade-systems", response_model=List[GradeSystemResponse])
async def read_grade_systems(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading grade systems for teacher_id={current_teacher.id}")
    try:
        query = select(GradeSystem).where(GradeSystem.teacher_id == current_teacher.id)
        result = await db.execute(query)
        grade_systems = result.scalars().all()
        
        if not grade_systems:
            logger.debug("No grade systems found")
            return []

        response = []
        for gs in grade_systems:
            # Convert grade_ranges to GradeRange objects for response
            grade_ranges_response = [
                GradeRange(
                    id=range_dict["id"],
                    min=range_dict["min"],
                    max=range_dict["max"],
                    grade=range_dict["grade"],
                    description=range_dict.get("description")
                )
                for range_dict in gs.grade_ranges
            ]
            
            response.append(GradeSystemResponse(
                id=gs.id,
                name=gs.name,
                teacher_id=gs.teacher_id,
                grading_type=gs.grading_type,
                grade_ranges=grade_ranges_response,
                is_default=gs.is_default,
                created_at=gs.created_at,
                updated_at=gs.updated_at
            ))

        logger.debug(f"Returning {len(response)} grade systems")
        return response
    except Exception as e:
        logger.error(f"Error reading grade systems: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading grade systems: {str(e)}")


@router.get("/read-grade-system/{system_id}", response_model=GradeSystemResponse)
async def read_grade_system(
    system_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading grade system: system_id={system_id}, teacher_id={current_teacher.id}")
    try:
        query = select(GradeSystem).where(
            GradeSystem.id == system_id,
            GradeSystem.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        grade_system = result.scalars().first()
        
        if not grade_system:
            logger.error(f"Grade system {system_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Grade system {system_id} not found")
        
        # Convert grade_ranges to GradeRange objects for response
        grade_ranges_response = [
            GradeRange(
                id=range_dict["id"],
                min=range_dict["min"],
                max=range_dict["max"],
                grade=range_dict["grade"],
                description=range_dict.get("description")
            )
            for range_dict in grade_system.grade_ranges
        ]
        
        return GradeSystemResponse(
            id=grade_system.id,
            name=grade_system.name,
            teacher_id=grade_system.teacher_id,
            grading_type=grade_system.grading_type,
            grade_ranges=grade_ranges_response,
            is_default=grade_system.is_default,
            created_at=grade_system.created_at,
            updated_at=grade_system.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading grade system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading grade system: {str(e)}")


@router.put("/update-grade-system/{system_id}", response_model=GradeSystemResponse, status_code=status.HTTP_200_OK)
async def update_grade_system(
    system_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    grade_system_data: GradeSystemUpdate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Updating grade system: system_id={system_id}, teacher_id={current_teacher.id}")
    try:
        # Find the grade system
        query = select(GradeSystem).where(
            GradeSystem.id == system_id,
            GradeSystem.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        grade_system = result.scalars().first()
        
        if not grade_system:
            logger.error(f"Grade system {system_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Grade system {system_id} not found")

        # Update fields if provided
        if grade_system_data.name is not None:
            if not grade_system_data.name.strip():
                logger.error("Grade system name cannot be empty")
                raise HTTPException(status_code=400, detail="Grade system name cannot be empty")
            
            # Check for duplicate name (excluding current system)
            if grade_system_data.name.strip() != grade_system.name:
                existing_system = (await db.execute(
                    select(GradeSystem).where(
                        GradeSystem.name == grade_system_data.name.strip(),
                        GradeSystem.teacher_id == current_teacher.id,
                        GradeSystem.id != system_id
                    )
                )).scalars().first()
                
                if existing_system:
                    logger.error(f"Grade system {grade_system_data.name} already exists for this teacher")
                    raise HTTPException(status_code=400, detail=f"Grade system {grade_system_data.name} already exists")
            
            grade_system.name = grade_system_data.name.strip()

        if grade_system_data.grading_type is not None:
            if not grade_system_data.grading_type.strip():
                logger.error("Grading type cannot be empty")
                raise HTTPException(status_code=400, detail="Grading type cannot be empty")
            grade_system.grading_type = grade_system_data.grading_type.strip()

        if grade_system_data.grade_ranges is not None:
            # Convert GradeRange objects to dictionaries for storage
            grade_ranges_dict = [
                {
                    "id": range_obj.id,
                    "min": range_obj.min,
                    "max": range_obj.max,
                    "grade": range_obj.grade,
                    "description": range_obj.description
                }
                for range_obj in grade_system_data.grade_ranges
            ]
            grade_system.grade_ranges = grade_ranges_dict

        if grade_system_data.is_default is not None:
            # If setting as default, unset any existing default for this teacher
            if grade_system_data.is_default:
                result = await db.execute(
                    select(GradeSystem).where(
                        GradeSystem.teacher_id == current_teacher.id,
                        GradeSystem.is_default == True,
                        GradeSystem.id != system_id
                    )
                )
                existing_defaults = result.scalars().all()
                for system in existing_defaults:
                    system.is_default = False
            grade_system.is_default = grade_system_data.is_default

        grade_system.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(grade_system)

        logger.debug(f"Successfully updated grade system: id={grade_system.id}, name={grade_system.name}")
        
        # Convert grade_ranges back to GradeRange objects for response
        grade_ranges_response = [
            GradeRange(
                id=range_dict["id"],
                min=range_dict["min"],
                max=range_dict["max"],
                grade=range_dict["grade"],
                description=range_dict.get("description")
            )
            for range_dict in grade_system.grade_ranges
        ]
        
        return GradeSystemResponse(
            id=grade_system.id,
            name=grade_system.name,
            teacher_id=grade_system.teacher_id,
            grading_type=grade_system.grading_type,
            grade_ranges=grade_ranges_response,
            is_default=grade_system.is_default,
            created_at=grade_system.created_at,
            updated_at=grade_system.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating grade system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating grade system: {str(e)}")


@router.delete("/delete-grade-system/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grade_system(
    system_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting grade system: system_id={system_id}, teacher_id={current_teacher.id}")
    try:
        # Find the grade system
        query = select(GradeSystem).where(
            GradeSystem.id == system_id,
            GradeSystem.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        grade_system = result.scalars().first()
        
        if not grade_system:
            logger.error(f"Grade system {system_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Grade system {system_id} not found")

        # Prevent deletion of the default system
        if grade_system.is_default:
            logger.error(f"Cannot delete default grade system {system_id}")
            raise HTTPException(status_code=400, detail="Cannot delete default grade system. Set another system as default first.")

        await db.delete(grade_system)
        await db.commit()
        
        logger.info(f"Successfully deleted grade system: id={system_id}, name={grade_system.name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting grade system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting grade system: {str(e)}")