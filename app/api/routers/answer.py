from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, select, Column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
import uuid
from app.models.model import Student, StudentSubmission, SubmissionAnswer, StudentAccessRule, AssessmentAssignment, AssignmentStatus
from app.schemas.schemas import StudentSubmissionWithAnswersResponse, StudentAssessmentSubmissionCreate, StudentSubmissionResponse, SubmissionAnswerResponse
from app.core.dependencies import get_current_student
from app.core.database import get_db
from app.core.logger import logger

router = APIRouter(tags=["student_submission"])

@router.post("/student/assessments/{assignment_id}/submit", response_model=StudentSubmissionWithAnswersResponse, status_code=status.HTTP_201_CREATED)
async def create_student_assessment_submission(
    assignment_id: int,
    submission_data: StudentAssessmentSubmissionCreate,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Create a new student submission and associated answers"""
    logger.debug(f"Creating student assessment submission: assignment_id={assignment_id}, student_id={current_student.id}")
    try:
        # Verify student has access to this assignment
        access_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id,
            StudentAccessRule.student_id == current_student.id,
            StudentAccessRule.can_access == True
        )
        access_result = await db.execute(access_query)
        access_rule = access_result.scalars().first()
        
        if not access_rule:
            logger.warning(f"Access denied for assignment_id={assignment_id}, student_id={current_student.id}")
            raise HTTPException(status_code=403, detail="Access denied to this assessment")
        
        # Verify assignment is active
        assignment_query = select(AssessmentAssignment).where(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.is_active == True
        )
        assignment_result = await db.execute(assignment_query)
        assignment = assignment_result.scalars().first()
        
        if not assignment:
            logger.warning(f"Assignment not found or not active for assignment_id={assignment_id}")
            raise HTTPException(status_code=404, detail="Assessment not found or not active")
        
        # Create the student submission
        student_submission = StudentSubmission(
            assignment_id=assignment_id,
            student_id=current_student.id,
            started_at=submission_data.started_at,
            submitted_at=submission_data.submitted_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(student_submission)
        await db.commit()
        await db.refresh(student_submission)
        
        # Create individual submission answers from submission_data.answers
        created_answers = []
        for question_id_str, answer_data in submission_data.answers.items():
            try:
                question_id = int(question_id_str)
                # Create a submission answer for each question
                submission_answer = SubmissionAnswer(
                    submission_id=student_submission.id,
                    question_id=question_id,
                    answer_data={"answer": answer_data} if not isinstance(answer_data, dict) else answer_data,
                    is_correct=None  # Will be set during grading
                )
                db.add(submission_answer)
                created_answers.append(submission_answer)
            except ValueError:
                # Skip invalid question IDs
                logger.warning(f"Invalid question ID in submission: {question_id_str}")
                continue
        
        # Commit all submission answers
        await db.commit()
        
        # Refresh all created answers
        for answer in created_answers:
            await db.refresh(answer)
        
        # Update assignment status to completed if submitted_at is provided
        if submission_data.submitted_at is not None:
            status_query = select(AssignmentStatus).where(
                AssignmentStatus.assignment_id == assignment_id,
                AssignmentStatus.student_id == current_student.id
            )
            status_result = await db.execute(status_query)
            assignment_status = status_result.scalars().first()
            
            if assignment_status:
                assignment_status.is_completed = True
                assignment_status.updated_at = datetime.utcnow()
                db.add(assignment_status)
                await db.commit()
        
        logger.debug(f"Successfully created student assessment submission: submission_id={student_submission.id}")
        
        # Prepare response
        submission_response = StudentSubmissionResponse(
            id=student_submission.id,
            assignment_id=student_submission.assignment_id,
            student_id=student_submission.student_id,
            started_at=student_submission.started_at,
            submitted_at=student_submission.submitted_at,
            created_at=student_submission.created_at,
            updated_at=student_submission.updated_at
        )
        
        answers_response = [
            SubmissionAnswerResponse(
                id=answer.id,
                submission_id=answer.submission_id,
                question_id=answer.question_id,
                answer_data=answer.answer_data,
                is_correct=answer.is_correct,
                created_at=answer.created_at,
                updated_at=answer.updated_at
            )
            for answer in created_answers
        ]
        
        return StudentSubmissionWithAnswersResponse(
            submission=submission_response,
            answers=answers_response
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating student assessment submission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating student assessment submission: {str(e)}")

