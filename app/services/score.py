from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, select, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.model import AssessmentScores
from uuid import UUID
from datetime import datetime
import uuid
from app.models.model import TeacherProfile
from app.core.dependencies import get_current_teacher
from app.core.database import get_db
from app.core.logger import logger
from app.schemas.schemas import AssessmentScoresCreate, AssessmentScoresUpdate, AssessmentScoresResponse, ColumnInfoS

router = APIRouter(tags=["Assessment Scores"])


@router.post("/create-assessment-scores", response_model=AssessmentScoresResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_scores(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    scores_data: AssessmentScoresCreate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Creating assessment scores: subject={scores_data.subject}, class_name={scores_data.class_name}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not scores_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        
        if not scores_data.class_name.strip():
            logger.error("Class name cannot be empty")
            raise HTTPException(status_code=400, detail="Class name cannot be empty")

        # Convert ColumnInfoS objects to dictionaries for storage
        columns_dict = [
            {
                "id": col.id,
                "label": col.label,
                "type": col.type,
                "assessmentType": col.assessmentType,
                "fullMark": col.fullMark,
                "customFullMark": col.customFullMark
            }
            for col in scores_data.columns
        ]

        # Log the data being stored for debugging
        logger.info(f"Input columns: {scores_data.columns}")
        logger.info(f"Converted columns for storage: {columns_dict}")
        logger.info(f"Input grades: {scores_data.grades}")

        # Create new assessment scores record
        assessment_scores = AssessmentScores(
            teacher_id=current_teacher.id,
            subject=scores_data.subject.strip(),
            class_name=scores_data.class_name.strip(),
            columns=columns_dict,  # Store the dictionary version
            grades=scores_data.grades  # Store grades directly
        )
        
        # Log the object before adding to DB
        logger.info(f"Assessment scores object before commit: columns={assessment_scores.columns}, grades={assessment_scores.grades}")
        
        db.add(assessment_scores)
        await db.commit()
        await db.refresh(assessment_scores)
        
        # Log the object after refresh
        logger.info(f"Assessment scores object after commit: columns={assessment_scores.columns}, grades={assessment_scores.grades}")

        logger.debug(f"Successfully created assessment scores: id={assessment_scores.id}")
        
        # Convert columns back to ColumnInfoS objects for response
        columns_response = [
            ColumnInfoS(
                id=col_dict["id"],
                label=col_dict["label"],
                type=col_dict["type"],
                assessmentType=col_dict.get("assessmentType"),
                fullMark=col_dict.get("fullMark"),
                customFullMark=col_dict.get("customFullMark")
            )
            for col_dict in assessment_scores.columns
        ]
        
        return AssessmentScoresResponse(
            id=assessment_scores.id,
            teacher_id=assessment_scores.teacher_id,
            subject=assessment_scores.subject,
            class_name=assessment_scores.class_name,
            columns=columns_response,  # Return the ColumnInfoS version
            grades=assessment_scores.grades,
            created_at=assessment_scores.created_at,
            updated_at=assessment_scores.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating assessment scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating assessment scores: {str(e)}")


@router.get("/read-assessment-scores", response_model=List[AssessmentScoresResponse])
async def read_assessment_scores(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: Optional[str] = None,
    class_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading assessment scores for teacher_id={current_teacher.id}")
    try:
        query = select(AssessmentScores).where(AssessmentScores.teacher_id == current_teacher.id)
        
        # Apply filters if provided
        if subject:
            query = query.where(AssessmentScores.subject == subject.strip())
        if class_name:
            query = query.where(AssessmentScores.class_name == class_name.strip())
        
        result = await db.execute(query)
        assessment_scores_list = result.scalars().all()
        
        if not assessment_scores_list:
            logger.debug("No assessment scores found")
            return []

        response = []
        for scores in assessment_scores_list:
            # Log the data being retrieved for debugging
            logger.info(f"Retrieved from DB - columns: {scores.columns}")
            logger.info(f"Retrieved from DB - grades: {scores.grades}")
            
            # Convert columns to ColumnInfoS objects for response
            columns_response = [
                ColumnInfoS(
                    id=col_dict["id"],
                    label=col_dict["label"],
                    type=col_dict["type"],
                    assessmentType=col_dict.get("assessmentType"),
                    fullMark=col_dict.get("fullMark"),
                    customFullMark=col_dict.get("customFullMark")
                )
                for col_dict in scores.columns
            ]
            
            response.append(AssessmentScoresResponse(
                id=scores.id,
                teacher_id=scores.teacher_id,
                subject=scores.subject,
                class_name=scores.class_name,
                columns=columns_response,
                grades=scores.grades,
                created_at=scores.created_at,
                updated_at=scores.updated_at
            ))

        logger.debug(f"Returning {len(response)} assessment scores")
        return response
    except Exception as e:
        logger.error(f"Error reading assessment scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessment scores: {str(e)}")


@router.get("/read-assessment-scores/{scores_id}", response_model=AssessmentScoresResponse)
async def read_assessment_scores_by_id(
    scores_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading assessment scores: scores_id={scores_id}, teacher_id={current_teacher.id}")
    try:
        query = select(AssessmentScores).where(
            AssessmentScores.id == scores_id,
            AssessmentScores.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_scores = result.scalars().first()
        
        if not assessment_scores:
            logger.error(f"Assessment scores {scores_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment scores {scores_id} not found")
        
        # Log the data being retrieved for debugging
        logger.info(f"Retrieved from DB - columns: {assessment_scores.columns}")
        logger.info(f"Retrieved from DB - grades: {assessment_scores.grades}")
        
        # Convert columns to ColumnInfoS objects for response
        columns_response = [
            ColumnInfoS(
                id=col_dict["id"],
                label=col_dict["label"],
                type=col_dict["type"],
                assessmentType=col_dict.get("assessmentType"),
                fullMark=col_dict.get("fullMark"),
                customFullMark=col_dict.get("customFullMark")
            )
            for col_dict in assessment_scores.columns
        ]
        
        return AssessmentScoresResponse(
            id=assessment_scores.id,
            teacher_id=assessment_scores.teacher_id,
            subject=assessment_scores.subject,
            class_name=assessment_scores.class_name,
            columns=columns_response,
            grades=assessment_scores.grades,
            created_at=assessment_scores.created_at,
            updated_at=assessment_scores.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading assessment scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessment scores: {str(e)}")


@router.put("/update-assessment-scores/{scores_id}", response_model=AssessmentScoresResponse, status_code=status.HTTP_200_OK)
async def update_assessment_scores(
    scores_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    scores_data: AssessmentScoresUpdate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Updating assessment scores: scores_id={scores_id}, teacher_id={current_teacher.id}")
    try:
        # Find the assessment scores
        query = select(AssessmentScores).where(
            AssessmentScores.id == scores_id,
            AssessmentScores.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_scores = result.scalars().first()
        
        if not assessment_scores:
            logger.error(f"Assessment scores {scores_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment scores {scores_id} not found")

        # Update fields if provided
        if scores_data.subject is not None:
            if not scores_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            assessment_scores.subject = scores_data.subject.strip()

        if scores_data.class_name is not None:
            if not scores_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            assessment_scores.class_name = scores_data.class_name.strip()

        if scores_data.columns is not None:
            # Convert ColumnInfoS objects to dictionaries for storage
            columns_dict = [
                {
                    "id": col.id,
                    "label": col.label,
                    "type": col.type,
                    "assessmentType": col.assessmentType,
                    "fullMark": col.fullMark,
                    "customFullMark": col.customFullMark
                }
                for col in scores_data.columns
            ]
            # Log the data being updated for debugging
            logger.info(f"Updating columns: {columns_dict}")
            assessment_scores.columns = columns_dict

        if scores_data.grades is not None:
            # Log the data being updated for debugging
            logger.info(f"Updating grades: {scores_data.grades}")
            assessment_scores.grades = scores_data.grades

        assessment_scores.updated_at = datetime.utcnow()
        
        # Log the object before committing
        logger.info(f"Assessment scores object before update commit: columns={assessment_scores.columns}, grades={assessment_scores.grades}")
        
        await db.commit()
        await db.refresh(assessment_scores)
        
        # Log the object after refresh
        logger.info(f"Assessment scores object after update commit: columns={assessment_scores.columns}, grades={assessment_scores.grades}")

        logger.debug(f"Successfully updated assessment scores: id={assessment_scores.id}")
        
        # Convert columns back to ColumnInfoS objects for response
        columns_response = [
            ColumnInfoS(
                id=col_dict["id"],
                label=col_dict["label"],
                type=col_dict["type"],
                assessmentType=col_dict.get("assessmentType"),
                fullMark=col_dict.get("fullMark"),
                customFullMark=col_dict.get("customFullMark")
            )
            for col_dict in assessment_scores.columns
        ]
        
        return AssessmentScoresResponse(
            id=assessment_scores.id,
            teacher_id=assessment_scores.teacher_id,
            subject=assessment_scores.subject,
            class_name=assessment_scores.class_name,
            columns=columns_response,
            grades=assessment_scores.grades,
            created_at=assessment_scores.created_at,
            updated_at=assessment_scores.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating assessment scores: {str(e)}")


@router.delete("/delete-assessment-scores/{scores_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment_scores(
    scores_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting assessment scores: scores_id={scores_id}, teacher_id={current_teacher.id}")
    try:
        # Find the assessment scores
        query = select(AssessmentScores).where(
            AssessmentScores.id == scores_id,
            AssessmentScores.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_scores = result.scalars().first()
        
        if not assessment_scores:
            logger.error(f"Assessment scores {scores_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment scores {scores_id} not found")

        await db.delete(assessment_scores)
        await db.commit()
        
        logger.info(f"Successfully deleted assessment scores: id={scores_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assessment scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting assessment scores: {str(e)}")