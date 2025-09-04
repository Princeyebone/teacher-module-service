from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from model import TeacherProfile, AssessmentWeights
from dependencies import get_current_teacher
from database import get_db
from logger import logger
from schemas import AssessmentWeightsResponse, AssessmentWeightsCreate, AssessmentWeightsUpdate, WeightsEntry, ColumnInfoW


# Router
router = APIRouter(tags=["Assessment Weights"])

@router.post("/create-assessment-weights", response_model=AssessmentWeightsResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_weights(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    weights_data: AssessmentWeightsCreate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Creating assessment weights: name={weights_data.name}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not weights_data.name.strip():
            logger.error("Assessment weights name cannot be empty")
            raise HTTPException(status_code=400, detail="Assessment weights name cannot be empty")
        
        if not weights_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
            
        if not weights_data.class_name.strip():
            logger.error("Class name cannot be empty")
            raise HTTPException(status_code=400, detail="Class name cannot be empty")

        # Check for duplicate weights name for this teacher, subject, and class
        existing_weights = (await db.execute(
            select(AssessmentWeights).where(
                AssessmentWeights.name == weights_data.name.strip(),
                AssessmentWeights.teacher_id == current_teacher.id,
                AssessmentWeights.subject == weights_data.subject.strip(),
                AssessmentWeights.class_name == weights_data.class_name.strip()
            )
        )).scalars().first()
        
        if existing_weights:
            logger.error(f"Assessment weights {weights_data.name} already exists for this teacher, subject, and class")
            raise HTTPException(status_code=400, detail=f"Assessment weights {weights_data.name} already exists for this subject and class")

        # If this is marked as default, unset any existing default for this teacher, subject, and class
        if weights_data.is_default:
            result = await db.execute(
                select(AssessmentWeights).where(
                    AssessmentWeights.teacher_id == current_teacher.id,
                    AssessmentWeights.subject == weights_data.subject.strip(),
                    AssessmentWeights.class_name == weights_data.class_name.strip(),
                    AssessmentWeights.is_default == True
                )
            )
            existing_defaults = result.scalars().all()
            for system in existing_defaults:
                system.is_default = False

        # Convert WeightsEntry objects to dictionaries for storage
        weights_dict = [
            {
                "id": entry.id,
                "assessment_type": entry.assessment_type,
                "weight": entry.weight
            }
            for entry in weights_data.weights
        ]

        # Convert ColumnInfoW objects to dictionaries for storage (if provided)
        columns_dict = []
        if weights_data.columns:
            columns_dict = [
                {
                    "id": col.id,
                    "assessment_type": col.assessment_type,
                    "full_mark": col.full_mark,
                    "custom_full_mark": col.custom_full_mark
                }
                for col in weights_data.columns
            ]

        # Create new assessment weights
        assessment_weights = AssessmentWeights(
            name=weights_data.name.strip(),
            teacher_id=current_teacher.id,
            subject=weights_data.subject.strip(),
            class_name=weights_data.class_name.strip(),
            weights=weights_dict,
            columns=columns_dict,  # Add columns data
            is_default=weights_data.is_default
        )
        
        db.add(assessment_weights)
        await db.commit()
        await db.refresh(assessment_weights)

        logger.debug(f"Successfully created assessment weights: id={assessment_weights.id}, name={assessment_weights.name}")
        
        # Convert weights back to WeightsEntry objects for response
        weights_response = [
            WeightsEntry(
                id=weight_dict["id"],
                assessment_type=weight_dict["assessment_type"],
                weight=weight_dict["weight"]
            )
            for weight_dict in assessment_weights.weights
        ]
        
        # Convert columns back to ColumnInfoW objects for response
        columns_response = []
        if assessment_weights.columns:
            columns_response = [
                ColumnInfoW(
                    id=col_dict["id"],
                    assessment_type=col_dict["assessment_type"],
                    full_mark=col_dict["full_mark"],
                    custom_full_mark=col_dict.get("custom_full_mark")
                )
                for col_dict in assessment_weights.columns
            ]
        
        return AssessmentWeightsResponse(
            id=assessment_weights.id,
            name=assessment_weights.name,
            teacher_id=assessment_weights.teacher_id,
            subject=assessment_weights.subject,
            class_name=assessment_weights.class_name,
            weights=weights_response,
            columns=columns_response,  # Add columns data
            is_default=assessment_weights.is_default,
            created_at=assessment_weights.created_at,
            updated_at=assessment_weights.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating assessment weights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating assessment weights: {str(e)}")


@router.get("/read-assessment-weights", response_model=List[AssessmentWeightsResponse])
async def read_assessment_weights(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: Optional[str] = None,
    class_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading assessment weights for teacher_id={current_teacher.id}")
    try:
        # Load ALL assessment weights for the teacher, regardless of subject/class
        query = select(AssessmentWeights).where(AssessmentWeights.teacher_id == current_teacher.id)
        
        # Note: We're not filtering by subject/class anymore to allow cross-subject usage
        # But we still accept the parameters for potential future use or specific filtering
        
        result = await db.execute(query)
        assessment_weights_list = result.scalars().all()
        
        if not assessment_weights_list:
            logger.debug("No assessment weights found")
            return []

        response = []
        for aw in assessment_weights_list:
            # Convert weights to WeightsEntry objects for response
            weights_response = [
                WeightsEntry(
                    id=weight_dict["id"],
                    assessment_type=weight_dict["assessment_type"],
                    weight=weight_dict["weight"]
                )
                for weight_dict in aw.weights
            ]
            
            # Convert columns to ColumnInfoW objects for response
            columns_response = []
            if aw.columns:
                columns_response = [
                    ColumnInfoW(
                        id=col_dict["id"],
                        assessment_type=col_dict["assessment_type"],
                        full_mark=col_dict["full_mark"],
                        custom_full_mark=col_dict.get("custom_full_mark")
                    )
                    for col_dict in aw.columns
                ]
            
            response.append(AssessmentWeightsResponse(
                id=aw.id,
                name=aw.name,
                teacher_id=aw.teacher_id,
                subject=aw.subject,
                class_name=aw.class_name,
                weights=weights_response,
                columns=columns_response,  # Add columns data
                is_default=aw.is_default,
                created_at=aw.created_at,
                updated_at=aw.updated_at
            ))

        logger.debug(f"Returning {len(response)} assessment weights")
        return response
    except Exception as e:
        logger.error(f"Error reading assessment weights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessment weights: {str(e)}")


@router.get("/read-assessment-weights/{weights_id}", response_model=AssessmentWeightsResponse)
async def read_assessment_weights_by_id(
    weights_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading assessment weights: weights_id={weights_id}, teacher_id={current_teacher.id}")
    try:
        query = select(AssessmentWeights).where(
            AssessmentWeights.id == weights_id,
            AssessmentWeights.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_weights = result.scalars().first()
        
        if not assessment_weights:
            logger.error(f"Assessment weights {weights_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment weights {weights_id} not found")
        
        # Convert weights to WeightsEntry objects for response
        weights_response = [
            WeightsEntry(
                id=weight_dict["id"],
                assessment_type=weight_dict["assessment_type"],
                weight=weight_dict["weight"]
            )
            for weight_dict in assessment_weights.weights
        ]
        
        # Convert columns to ColumnInfoW objects for response
        columns_response = []
        if assessment_weights.columns:
            columns_response = [
                ColumnInfoW(
                    id=col_dict["id"],
                    assessment_type=col_dict["assessment_type"],
                    full_mark=col_dict["full_mark"],
                    custom_full_mark=col_dict.get("custom_full_mark")
                )
                for col_dict in assessment_weights.columns
            ]
        
        return AssessmentWeightsResponse(
            id=assessment_weights.id,
            name=assessment_weights.name,
            teacher_id=assessment_weights.teacher_id,
            subject=assessment_weights.subject,
            class_name=assessment_weights.class_name,
            weights=weights_response,
            columns=columns_response,  # Add columns data
            is_default=assessment_weights.is_default,
            created_at=assessment_weights.created_at,
            updated_at=assessment_weights.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading assessment weights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessment weights: {str(e)}")


@router.put("/update-assessment-weights/{weights_id}", response_model=AssessmentWeightsResponse, status_code=status.HTTP_200_OK)
async def update_assessment_weights(
    weights_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    weights_data: AssessmentWeightsUpdate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Updating assessment weights: weights_id={weights_id}, teacher_id={current_teacher.id}")
    try:
        # Find the assessment weights
        query = select(AssessmentWeights).where(
            AssessmentWeights.id == weights_id,
            AssessmentWeights.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_weights = result.scalars().first()
        
        if not assessment_weights:
            logger.error(f"Assessment weights {weights_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment weights {weights_id} not found")

        # Update fields if provided
        if weights_data.name is not None:
            if not weights_data.name.strip():
                logger.error("Assessment weights name cannot be empty")
                raise HTTPException(status_code=400, detail="Assessment weights name cannot be empty")
            
            # Check for duplicate name (excluding current weights) for this teacher, subject, and class
            if weights_data.name.strip() != assessment_weights.name:
                existing_weights = (await db.execute(
                    select(AssessmentWeights).where(
                        AssessmentWeights.name == weights_data.name.strip(),
                        AssessmentWeights.teacher_id == current_teacher.id,
                        AssessmentWeights.subject == assessment_weights.subject,
                        AssessmentWeights.class_name == assessment_weights.class_name,
                        AssessmentWeights.id != weights_id
                    )
                )).scalars().first()
                
                if existing_weights:
                    logger.error(f"Assessment weights {weights_data.name} already exists for this teacher, subject, and class")
                    raise HTTPException(status_code=400, detail=f"Assessment weights {weights_data.name} already exists for this subject and class")
            
            assessment_weights.name = weights_data.name.strip()

        if weights_data.subject is not None:
            if not weights_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            assessment_weights.subject = weights_data.subject.strip()

        if weights_data.class_name is not None:
            if not weights_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            assessment_weights.class_name = weights_data.class_name.strip()

        if weights_data.weights is not None:
            # Convert WeightsEntry objects to dictionaries for storage
            weights_dict = [
                {
                    "id": entry.id,
                    "assessment_type": entry.assessment_type,
                    "weight": entry.weight
                }
                for entry in weights_data.weights
            ]
            assessment_weights.weights = weights_dict

        if weights_data.columns is not None:
            # Convert ColumnInfoW objects to dictionaries for storage
            columns_dict = [
                {
                    "id": col.id,
                    "assessment_type": col.assessment_type,
                    "full_mark": col.full_mark,
                    "custom_full_mark": col.custom_full_mark
                }
                for col in weights_data.columns
            ]
            assessment_weights.columns = columns_dict

        if weights_data.is_default is not None:
            # If setting as default, unset any existing default for this teacher, subject, and class
            if weights_data.is_default:
                result = await db.execute(
                    select(AssessmentWeights).where(
                        AssessmentWeights.teacher_id == current_teacher.id,
                        AssessmentWeights.subject == assessment_weights.subject,
                        AssessmentWeights.class_name == assessment_weights.class_name,
                        AssessmentWeights.is_default == True,
                        AssessmentWeights.id != weights_id
                    )
                )
                existing_defaults = result.scalars().all()
                for system in existing_defaults:
                    system.is_default = False
            assessment_weights.is_default = weights_data.is_default

        assessment_weights.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(assessment_weights)

        logger.debug(f"Successfully updated assessment weights: id={assessment_weights.id}, name={assessment_weights.name}")
        
        # Convert weights back to WeightsEntry objects for response
        weights_response = [
            WeightsEntry(
                id=weight_dict["id"],
                assessment_type=weight_dict["assessment_type"],
                weight=weight_dict["weight"]
            )
            for weight_dict in assessment_weights.weights
        ]
        
        # Convert columns back to ColumnInfoW objects for response
        columns_response = []
        if assessment_weights.columns:
            columns_response = [
                ColumnInfoW(
                    id=col_dict["id"],
                    assessment_type=col_dict["assessment_type"],
                    full_mark=col_dict["full_mark"],
                    custom_full_mark=col_dict.get("custom_full_mark")
                )
                for col_dict in assessment_weights.columns
            ]
        
        return AssessmentWeightsResponse(
            id=assessment_weights.id,
            name=assessment_weights.name,
            teacher_id=assessment_weights.teacher_id,
            subject=assessment_weights.subject,
            class_name=assessment_weights.class_name,
            weights=weights_response,
            columns=columns_response,  # Add columns data
            is_default=assessment_weights.is_default,
            created_at=assessment_weights.created_at,
            updated_at=assessment_weights.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment weights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating assessment weights: {str(e)}")


@router.delete("/delete-assessment-weights/{weights_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment_weights(
    weights_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting assessment weights: weights_id={weights_id}, teacher_id={current_teacher.id}")
    try:
        # Find the assessment weights
        query = select(AssessmentWeights).where(
            AssessmentWeights.id == weights_id,
            AssessmentWeights.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment_weights = result.scalars().first()
        
        if not assessment_weights:
            logger.error(f"Assessment weights {weights_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment weights {weights_id} not found")

        await db.delete(assessment_weights)
        await db.commit()
        
        logger.info(f"Successfully deleted assessment weights: id={weights_id}, name={assessment_weights.name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assessment weights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting assessment weights: {str(e)}")