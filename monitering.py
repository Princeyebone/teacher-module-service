from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, select, Column, Relationship, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from schemas import StudentMonitoringUpdate, StudentMonitoringResponse, SurveillanceDataResponse
from model import TeacherProfile, Student, Assessment, AssessmentAssignment, AssessmentQuestion, StudentAssessmentMonitoring
from dependencies import get_current_teacher
from database import get_db
from logger import logger

router = APIRouter(tags=["Monitoring"])


@router.get("/read-student-monitoring/{assessment_id}", response_model=List[StudentMonitoringResponse])
async def read_student_monitoring(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Get all student monitoring records for an assessment - called by teacher frontend for polling"""
    logger.debug(f"Reading student monitoring: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Verify assessment exists and belongs to teacher
        assessment_query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get all monitoring records for this assessment
        query = select(StudentAssessmentMonitoring).where(
            StudentAssessmentMonitoring.assessment_id == assessment_id
        ).order_by(StudentAssessmentMonitoring.last_updated.desc())
        
        result = await db.execute(query)
        records = result.scalars().all()
        
        return [
            StudentMonitoringResponse(
                id=record.id,
                assessment_id=record.assessment_id,
                student_id=record.student_id,
                student_name=record.student_name,
                last_updated=record.last_updated,
                current_status=record.current_status,
                current_question_id=record.current_question_id,
                time_on_question=record.time_on_question,
                total_time=record.total_time,
                ip_address=record.ip_address,
                location=record.location,
                security_breaches=record.security_breaches,
                additional_data=record.additional_data,
                created_at=record.created_at
            )
            for record in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading student monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading student monitoring: {str(e)}")


@router.get("/polling-updates/{assessment_id}", response_model=List[StudentMonitoringResponse])
async def get_polling_updates(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    last_polled_at: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get polling updates for student monitoring - called by teacher frontend for polling"""
    logger.debug(f"Getting polling updates: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Verify assessment exists and belongs to teacher
        assessment_query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get monitoring records updated since last poll
        query = select(StudentAssessmentMonitoring).where(
            StudentAssessmentMonitoring.assessment_id == assessment_id
        )
        
        # If last_polled_at is provided, only get records updated since then
        if last_polled_at:
            query = query.where(StudentAssessmentMonitoring.last_updated > last_polled_at)
            
        query = query.order_by(StudentAssessmentMonitoring.last_updated.desc())
        
        result = await db.execute(query)
        records = result.scalars().all()
        
        return [
            StudentMonitoringResponse(
                id=record.id,
                assessment_id=record.assessment_id,
                student_id=record.student_id,
                student_name=record.student_name,
                last_updated=record.last_updated,
                current_status=record.current_status,
                current_question_id=record.current_question_id,
                time_on_question=record.time_on_question,
                total_time=record.total_time,
                ip_address=record.ip_address,
                location=record.location,
                security_breaches=record.security_breaches,
                additional_data=record.additional_data,
                created_at=record.created_at
            )
            for record in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting polling updates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting polling updates: {str(e)}")


@router.get("/read-all-publishing", response_model=List[SurveillanceDataResponse])
async def read_all_publishing(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Get all publishing data for surveillance dashboard"""
    logger.debug(f"Reading all publishing data: teacher_id={current_teacher.id}")
    try:
        # Query for all published assessments belonging to this teacher
        # Use join to eagerly load assessment_questions to avoid lazy loading issues
        query = select(Assessment).where(
            Assessment.teacher_id == current_teacher.id,
            Assessment.is_published == True
        ).order_by(Assessment.created_at.desc())
        
        result = await db.execute(query)
        assessments = result.scalars().all()
        
        # Get assignment data for each assessment to determine active status
        surveillance_data = []
        for assessment in assessments:
            # Get the assignment for this assessment
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment.id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            # Get question count through a separate query instead of accessing relationship directly
            question_count_query = select(func.count(AssessmentQuestion.id)).where(
                AssessmentQuestion.assessment_id == assessment.id
            )
            question_count_result = await db.execute(question_count_query)
            question_count = question_count_result.scalar_one()
            
            # Transform to response format
            surveillance_item = SurveillanceDataResponse(
                id=assessment.id,
                title=assessment.title,
                assessment_type=assessment.assessment_type,
                subject=assessment.subject,
                class_name=assessment.class_name,
                question_count=question_count,
                total_points=assessment.total_points or 0,
                created_at=assessment.created_at,
                is_published=assessment.is_published,
                is_active=assignment.is_active if assignment else False,
                available_from=assignment.available_from if assignment else assessment.created_at,
                available_until=assignment.available_until if assignment else assessment.created_at
            )
            surveillance_data.append(surveillance_item)
        
        logger.debug(f"Successfully retrieved {len(surveillance_data)} publishing records")
        return surveillance_data
    except Exception as e:
        logger.error(f"Error reading all publishing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading all publishing data: {str(e)}")
