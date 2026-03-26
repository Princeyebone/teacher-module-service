from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from sqlmodel import SQLModel, Field as SQLField, select, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from app.models.model import TeacherProfile, Question, QuestionDetail, Assessment, AssessmentQuestion, AssessmentSection, AssessmentSectionQuestion
from app.models.model import AssessmentAssignment, StudentAccessRule  # Add these imports
from app.core.dependencies import get_current_teacher
from app.core.database import get_db
from app.core.logger import logger
from app.schemas.schemas import QuestionOption, QuestionCreate, MatchingPair, QuestionUpdate, SubQuestion
from app.schemas.schemas import QuestionResponse, AssessmentCreate, AssessmentUpdate, AssessmentResponse
from app.schemas.schemas import AssessmentQuestionCreate, AssessmentQuestionUpdate, AssessmentQuestionResponse
from app.schemas.schemas import AssessmentWithSectionsCreate, AssessmentWithSectionsUpdate, AssessmentSectionCreate
# Import the student WebSocket message function
from app.sch_ground.background import publish_student_ws_message

router = APIRouter(tags=["Assessment Builder"])


@router.post("/create-question", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    question_data: QuestionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new question"""
    logger.debug(f"Creating question: teacher_id={current_teacher.id}, type={question_data.type}")
    try:
        # Validate inputs
        if not question_data.question_text.strip():
            logger.error("Question text cannot be empty")
            raise HTTPException(status_code=400, detail="Question text cannot be empty")
        
        if not question_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        
        if not question_data.class_name.strip():
            logger.error("Class name cannot be empty")
            raise HTTPException(status_code=400, detail="Class name cannot be empty")
        
        # Removed validation for strand being empty since it's now optional
        
        # Validate question type
        valid_types = ["multiple_choice", "true_false", "short_answer", "essay", "matching", "fill_in_blank"]
        if question_data.type not in valid_types:
            logger.error(f"Invalid question type: {question_data.type}")
            raise HTTPException(status_code=400, detail=f"Invalid question type. Must be one of: {valid_types}")
        
        # Validate type-specific fields
        if question_data.type in ["multiple_choice", "true_false"]:
            if not question_data.options or len(question_data.options) == 0:
                logger.error(f"Options are required for {question_data.type} questions")
                raise HTTPException(status_code=400, detail=f"Options are required for {question_data.type} questions")
            
            # For true/false, validate exactly 2 options
            if question_data.type == "true_false":
                if len(question_data.options) != 2:
                    logger.error("True/False questions must have exactly 2 options")
                    raise HTTPException(status_code=400, detail="True/False questions must have exactly 2 options")
                
                option_texts = [opt.text.lower() for opt in question_data.options]
                if "true" not in option_texts or "false" not in option_texts:
                    logger.error("True/False questions must have 'True' and 'False' options")
                    raise HTTPException(status_code=400, detail="True/False questions must have 'True' and 'False' options")
            
            # Validate that at least one option is marked as correct
            if not any(opt.is_correct for opt in question_data.options):
                logger.error("At least one option must be marked as correct")
                raise HTTPException(status_code=400, detail="At least one option must be marked as correct")
        
        elif question_data.type == "matching":
            if not question_data.matching_pairs or len(question_data.matching_pairs) < 2:
                logger.error("Matching questions must have at least 2 pairs")
                raise HTTPException(status_code=400, detail="Matching questions must have at least 2 pairs")
            
            # Validate that all pairs have both left and right values
            for pair in question_data.matching_pairs:
                if not pair.left.strip() or not pair.right.strip():
                    logger.error("All matching pairs must have both left and right values")
                    raise HTTPException(status_code=400, detail="All matching pairs must have both left and right values")
            
            # Make correct_answer optional for matching questions
            # Only validate if provided
            if question_data.correct_answer is not None:
                try:
                    correct_index = int(question_data.correct_answer)
                    if correct_index < 0 or correct_index >= len(question_data.matching_pairs):
                        logger.error("Correct answer index is out of range")
                        raise HTTPException(status_code=400, detail="Correct answer index is out of range")
                except (ValueError, TypeError):
                    logger.error("Correct answer must be a valid integer index")
                    raise HTTPException(status_code=400, detail="Correct answer must be a valid integer index")
        
        elif question_data.type in ["short_answer", "essay"]:
            if not question_data.correct_answer:
                logger.error("Correct answer is required for short answer and essay questions")
                raise HTTPException(status_code=400, detail="Correct answer is required for short answer and essay questions")
            
            # Validate sub-questions if provided
            if question_data.sub_questions:
                for sub_question in question_data.sub_questions:
                    # Ensure sub-questions are only short answer or essay types
                    if sub_question.type not in ["short_answer", "essay"]:
                        logger.error(f"Sub-questions can only be short_answer or essay types, got {sub_question.type}")
                        raise HTTPException(status_code=400, detail=f"Sub-questions can only be short_answer or essay types, got {sub_question.type}")
        
        elif question_data.type == "fill_in_blank":
            if not question_data.correct_answer:
                logger.error("Correct answer is required for fill in blank questions")
                raise HTTPException(status_code=400, detail="Correct answer is required for fill in blank questions")
        
        # Create the main question
        question = Question(
            teacher_id=current_teacher.id,
            subject=question_data.subject.strip(),
            class_name=question_data.class_name.strip(),
            strand=question_data.strand.strip() if question_data.strand else None,  # Handle optional strand
            topic=question_data.topic.strip() if question_data.topic else None,
            type=question_data.type,
            question_text=question_data.question_text.strip(),
            points=question_data.points,
            tags=question_data.tags
        )
        
        db.add(question)
        await db.commit()
        await db.refresh(question)
        
        # Create question details
        options_dict = None
        if question_data.options:
            options_dict = [
                {
                    "id": opt.id,
                    "text": opt.text,
                    "is_correct": opt.is_correct
                }
                for opt in question_data.options
            ]
        
        matching_pairs_dict = None
        if question_data.matching_pairs:
            matching_pairs_dict = [
                {
                    "id": pair.id,
                    "left": pair.left,
                    "right": pair.right
                }
                for pair in question_data.matching_pairs
            ]
        
        sub_questions_dict = None
        if question_data.sub_questions:
            sub_questions_dict = [
                {
                    "id": sub.id,
                    "type": sub.type,
                    "question_text": sub.question_text,
                    "correct_answer": sub.correct_answer,
                    "explanation": sub.explanation,
                    "marking_guidelines": sub.marking_guidelines,
                    "points": sub.points
                }
                for sub in question_data.sub_questions
            ]
        
        # Convert correct_answer to string for matching questions
        correct_answer_str = question_data.correct_answer
        if question_data.type == "matching" and correct_answer_str is not None:
            correct_answer_str = str(correct_answer_str)
        
        question_detail = QuestionDetail(
            question_id=question.id,
            options=options_dict,
            correct_answer=correct_answer_str,
            explanation=question_data.explanation,
            marking_guidelines=question_data.marking_guidelines,
            matching_pairs=matching_pairs_dict,
            sub_questions=sub_questions_dict
        )
        
        db.add(question_detail)
        await db.commit()
        await db.refresh(question_detail)
        
        logger.debug(f"Successfully created question: id={question.id}")
        
        # Prepare response
        response_options = None
        if question_detail.options:
            response_options = [
                QuestionOption(
                    id=opt["id"],
                    text=opt["text"],
                    is_correct=opt["is_correct"]
                )
                for opt in question_detail.options
            ]
        
        response_matching_pairs = None
        if question_detail.matching_pairs:
            response_matching_pairs = [
                MatchingPair(
                    id=pair["id"],
                    left=pair["left"],
                    right=pair["right"]
                )
                for pair in question_detail.matching_pairs
            ]
        
        response_sub_questions = None
        if question_detail.sub_questions:
            response_sub_questions = [
                SubQuestion(
                    id=sub["id"],
                    type=sub["type"],
                    question_text=sub["question_text"],
                    correct_answer=sub["correct_answer"],
                    explanation=sub["explanation"],
                    marking_guidelines=sub["marking_guidelines"],
                    points=sub["points"]
                )
                for sub in question_detail.sub_questions
            ]
        
        return QuestionResponse(
            id=question.id,
            teacher_id=question.teacher_id,
            subject=question.subject,
            class_name=question.class_name,
            strand=question.strand,  # This can now be None
            topic=question.topic,
            type=question.type,
            question_text=question.question_text,
            points=question.points,
            tags=question.tags,
            created_at=question.created_at,
            updated_at=question.updated_at,
            options=response_options,
            correct_answer=question_detail.correct_answer,
            explanation=question_detail.explanation,
            marking_guidelines=question_detail.marking_guidelines,
            matching_pairs=response_matching_pairs,
            sub_questions=response_sub_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating question: {str(e)}")

@router.get("/read-questions", response_model=List[QuestionResponse])
async def read_questions(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: Optional[str] = None,
    class_name: Optional[str] = None,
    strand: Optional[str] = None,
    question_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Read questions with optional filters"""
    logger.debug(f"Reading questions: teacher_id={current_teacher.id}")
    try:
        # Build query for questions
        query = select(Question).where(Question.teacher_id == current_teacher.id)
        
        # Apply filters
        if subject:
            query = query.where(Question.subject == subject.strip())
        if class_name:
            query = query.where(Question.class_name == class_name.strip())
        if strand:
            query = query.where(Question.strand == strand.strip())
        if question_type:
            query = query.where(Question.type == question_type.strip())
        
        result = await db.execute(query)
        questions = result.scalars().all()
        
        if not questions:
            logger.debug("No questions found")
            return []
        
        # Get question details for all questions
        question_ids = [q.id for q in questions]
        details_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
        details_result = await db.execute(details_query)
        details_map = {detail.question_id: detail for detail in details_result.scalars().all()}
        
        # Build response
        response = []
        for question in questions:
            detail = details_map.get(question.id)
            
            # Prepare options
            response_options = None
            if detail and detail.options:
                response_options = [
                    QuestionOption(
                        id=opt["id"],
                        text=opt["text"],
                        is_correct=opt["is_correct"]
                    )
                    for opt in detail.options
                ]
            
            # Prepare matching pairs
            response_matching_pairs = None
            if detail and detail.matching_pairs:
                response_matching_pairs = [
                    MatchingPair(
                        id=pair["id"],
                        left=pair["left"],
                        right=pair["right"]
                    )
                    for pair in detail.matching_pairs
                ]
            
            # Prepare sub-questions
            response_sub_questions = None
            if detail and detail.sub_questions:
                response_sub_questions = [
                    SubQuestion(
                        id=sub["id"],
                        type=sub["type"],
                        question_text=sub["question_text"],
                        correct_answer=sub["correct_answer"],
                        explanation=sub["explanation"],
                        marking_guidelines=sub["marking_guidelines"],
                        points=sub["points"]
                    )
                    for sub in detail.sub_questions
                ]
            
            response.append(QuestionResponse(
                id=question.id,
                teacher_id=question.teacher_id,
                subject=question.subject,
                class_name=question.class_name,
                strand=question.strand,
                topic=question.topic,
                type=question.type,
                question_text=question.question_text,
                points=question.points,
                tags=question.tags,
                created_at=question.created_at,
                updated_at=question.updated_at,
                options=response_options,
                correct_answer=detail.correct_answer if detail else None,
                explanation=detail.explanation if detail else None,
                marking_guidelines=detail.marking_guidelines if detail else None,
                matching_pairs=response_matching_pairs,
                sub_questions=response_sub_questions
            ))
        
        logger.debug(f"Returning {len(response)} questions")
        return response
    except Exception as e:
        logger.error(f"Error reading questions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading questions: {str(e)}")

@router.get("/read-question/{question_id}", response_model=QuestionResponse)
async def read_question_by_id(
    question_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Read a specific question by ID"""
    logger.debug(f"Reading question: question_id={question_id}, teacher_id={current_teacher.id}")
    try:
        # Get the question
        query = select(Question).where(
            Question.id == question_id,
            Question.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        question = result.scalars().first()
        
        if not question:
            logger.error(f"Question {question_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        # Get question details
        details_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
        details_result = await db.execute(details_query)
        detail = details_result.scalars().first()
        
        # Prepare options
        response_options = None
        if detail and detail.options:
            response_options = [
                QuestionOption(
                    id=opt["id"],
                    text=opt["text"],
                    is_correct=opt["is_correct"]
                )
                for opt in detail.options
            ]
        
        # Prepare matching pairs
        response_matching_pairs = None
        if detail and detail.matching_pairs:
            response_matching_pairs = [
                MatchingPair(
                    id=pair["id"],
                    left=pair["left"],
                    right=pair["right"]
                )
                for pair in detail.matching_pairs
            ]
        
        # Prepare sub-questions
        response_sub_questions = None
        if detail and detail.sub_questions:
            response_sub_questions = [
                SubQuestion(
                    id=sub["id"],
                    type=sub["type"],
                    question_text=sub["question_text"],
                    correct_answer=sub["correct_answer"],
                    explanation=sub["explanation"],
                    marking_guidelines=sub["marking_guidelines"],
                    points=sub["points"]
                )
                for sub in detail.sub_questions
            ]
        
        return QuestionResponse(
            id=question.id,
            teacher_id=question.teacher_id,
            subject=question.subject,
            class_name=question.class_name,
            strand=question.strand,
            topic=question.topic,
            type=question.type,
            question_text=question.question_text,
            points=question.points,
            tags=question.tags,
            created_at=question.created_at,
            updated_at=question.updated_at,
            options=response_options,
            correct_answer=detail.correct_answer if detail else None,
            explanation=detail.explanation if detail else None,
            marking_guidelines=detail.marking_guidelines if detail else None,
            matching_pairs=response_matching_pairs,
            sub_questions=response_sub_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading question: {str(e)}")

@router.put("/update-question/{question_id}", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def update_question(
    question_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    question_data: QuestionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a question"""
    logger.debug(f"Updating question: question_id={question_id}, teacher_id={current_teacher.id}")
    try:
        # Get the question
        query = select(Question).where(
            Question.id == question_id,
            Question.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        question = result.scalars().first()
        
        if not question:
            logger.error(f"Question {question_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        # Get question details
        details_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
        details_result = await db.execute(details_query)
        detail = details_result.scalars().first()
        
        if not detail:
            logger.error(f"Question details for question {question_id} not found")
            raise HTTPException(status_code=404, detail=f"Question details for question {question_id} not found")
        
        # Update question fields
        if question_data.subject is not None:
            if not question_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            question.subject = question_data.subject.strip()
        
        if question_data.class_name is not None:
            if not question_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            question.class_name = question_data.class_name.strip()
        
        if question_data.strand is not None:
            # Strand can now be None/empty since it's optional
            question.strand = question_data.strand.strip() if question_data.strand.strip() else None
        
        if question_data.topic is not None:
            question.topic = question_data.topic.strip() if question_data.topic.strip() else None
        
        if question_data.type is not None:
            # Validate question type
            valid_types = ["multiple_choice", "true_false", "short_answer", "essay", "matching", "fill_in_blank"]
            if question_data.type not in valid_types:
                logger.error(f"Invalid question type: {question_data.type}")
                raise HTTPException(status_code=400, detail=f"Invalid question type. Must be one of: {valid_types}")
            question.type = question_data.type
        
        if question_data.question_text is not None:
            if not question_data.question_text.strip():
                logger.error("Question text cannot be empty")
                raise HTTPException(status_code=400, detail="Question text cannot be empty")
            question.question_text = question_data.question_text.strip()
        
        if question_data.points is not None:
            question.points = question_data.points
        
        if question_data.tags is not None:
            question.tags = question_data.tags
        
        # Validate type-specific fields when changing question type or updating related fields
        # Check if we're updating to or from a type that supports sub-questions
        if question_data.type is not None or question_data.sub_questions is not None:
            current_type = question_data.type if question_data.type is not None else question.type
            
            if current_type in ["short_answer", "essay"] and question_data.sub_questions is not None:
                # Validate sub-questions for short answer and essay types
                for sub_question in question_data.sub_questions:
                    # Ensure sub-questions are only short answer or essay types
                    if sub_question.type not in ["short_answer", "essay"]:
                        logger.error(f"Sub-questions can only be short_answer or essay types, got {sub_question.type}")
                        raise HTTPException(status_code=400, detail=f"Sub-questions can only be short_answer or essay types, got {sub_question.type}")
        
        # Update question detail fields
        if question_data.options is not None:
            options_dict = [
                {
                    "id": opt.id,
                    "text": opt.text,
                    "is_correct": opt.is_correct
                }
                for opt in question_data.options
            ]
            detail.options = options_dict
        
        if question_data.correct_answer is not None:
            detail.correct_answer = question_data.correct_answer
        
        if question_data.explanation is not None:
            detail.explanation = question_data.explanation
        
        if question_data.marking_guidelines is not None:
            detail.marking_guidelines = question_data.marking_guidelines
        
        if question_data.matching_pairs is not None:
            matching_pairs_dict = [
                {
                    "id": pair.id,
                    "left": pair.left,
                    "right": pair.right
                }
                for pair in question_data.matching_pairs
            ]
            detail.matching_pairs = matching_pairs_dict
        
        if question_data.sub_questions is not None:
            sub_questions_dict = [
                {
                    "id": sub.id,
                    "type": sub.type,
                    "question_text": sub.question_text,
                    "correct_answer": sub.correct_answer,
                    "explanation": sub.explanation,
                    "marking_guidelines": sub.marking_guidelines,
                    "points": sub.points
                }
                for sub in question_data.sub_questions
            ]
            detail.sub_questions = sub_questions_dict
        
        # Convert correct_answer to string for matching questions
        if question.type == "matching" and detail.correct_answer is not None:
            try:
                detail.correct_answer = str(int(detail.correct_answer))
            except (ValueError, TypeError):
                pass  # Keep as is if it can't be converted to int then back to string
        
        question.updated_at = datetime.utcnow()
        detail.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(question)
        await db.refresh(detail)
        
        logger.debug(f"Successfully updated question: id={question.id}")
        
        # Prepare response
        response_options = None
        if detail.options:
            response_options = [
                QuestionOption(
                    id=opt["id"],
                    text=opt["text"],
                    is_correct=opt["is_correct"]
                )
                for opt in detail.options
            ]
        
        response_matching_pairs = None
        if detail.matching_pairs:
            response_matching_pairs = [
                MatchingPair(
                    id=pair["id"],
                    left=pair["left"],
                    right=pair["right"]
                )
                for pair in detail.matching_pairs
            ]
        
        response_sub_questions = None
        if detail.sub_questions:
            response_sub_questions = [
                SubQuestion(
                    id=sub["id"],
                    type=sub["type"],
                    question_text=sub["question_text"],
                    correct_answer=sub["correct_answer"],
                    explanation=sub["explanation"],
                    marking_guidelines=sub["marking_guidelines"],
                    points=sub["points"]
                )
                for sub in detail.sub_questions
            ]
        
        return QuestionResponse(
            id=question.id,
            teacher_id=question.teacher_id,
            subject=question.subject,
            class_name=question.class_name,
            strand=question.strand,  # This can now be None
            topic=question.topic,
            type=question.type,
            question_text=question.question_text,
            points=question.points,
            tags=question.tags,
            created_at=question.created_at,
            updated_at=question.updated_at,
            options=response_options,
            correct_answer=detail.correct_answer,
            explanation=detail.explanation,
            marking_guidelines=detail.marking_guidelines,
            matching_pairs=response_matching_pairs,
            sub_questions=response_sub_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating question: {str(e)}")

@router.delete("/delete-question/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Delete a question with cascading delete from all assessments"""
    logger.debug(f"Deleting question: question_id={question_id}, teacher_id={current_teacher.id}")
    try:
        # Get the question
        query = select(Question).where(
            Question.id == question_id,
            Question.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        question = result.scalars().first()
        
        if not question:
            logger.error(f"Question {question_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        # First, delete all assessment question links (cascading delete)
        assessment_question_query = select(AssessmentQuestion).where(
            AssessmentQuestion.question_id == question_id
        )
        assessment_question_result = await db.execute(assessment_question_query)
        assessment_questions = assessment_question_result.scalars().all()
        
        # Delete all assessment question links
        for aq in assessment_questions:
            await db.delete(aq)
        
        await db.flush()  # Ensure the assessment question links are deleted
        
        # Delete question details first (due to foreign key constraint)
        details_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
        details_result = await db.execute(details_query)
        detail = details_result.scalars().first()
        
        if detail:
            await db.delete(detail)
            await db.flush()  # Ensure the detail is deleted before deleting the question
        
        # Get all assessments that include this question
        assessment_query = select(Assessment).join(AssessmentQuestion).where(
            AssessmentQuestion.question_id == question_id
        )
        assessment_result = await db.execute(assessment_query)
        assessments = assessment_result.scalars().all()
        
        # Delete the question (hard delete)
        await db.delete(question)
        await db.commit()
        
        # Update total points for all affected assessments
        for assessment in assessments:
            # Recalculate total points
            new_total_points = sum(
                aq.points for aq in assessment.assessment_questions
                if aq.question_id != question_id
            )
            assessment.total_points = new_total_points
            await db.merge(assessment)
        
        await db.commit()
        
        logger.info(f"Successfully deleted question: id={question_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()  # Rollback in case of error
        logger.error(f"Error deleting question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting question: {str(e)}")


@router.post("/create-assessment", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    assessment_data: AssessmentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new assessment (quiz, test, exercise, etc.)"""
    logger.debug(f"Creating assessment: teacher_id={current_teacher.id}, title={assessment_data.title}")
    try:
        # Validate inputs
        if not assessment_data.title.strip():
            logger.error("Assessment title cannot be empty")
            raise HTTPException(status_code=400, detail="Assessment title cannot be empty")
        
        if not assessment_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        
        if not assessment_data.class_name.strip():
            logger.error("Class name cannot be empty")
            raise HTTPException(status_code=400, detail="Class name cannot be empty")
        
        if not assessment_data.assessment_type.strip():
            logger.error("Assessment type cannot be empty")
            raise HTTPException(status_code=400, detail="Assessment type cannot be empty")
        
        # Validate assessment type
        valid_types = ["quiz", "test", "exercise", "exam", "assignment", "project"]
        if assessment_data.assessment_type not in valid_types:
            logger.error(f"Invalid assessment type: {assessment_data.assessment_type}")
            raise HTTPException(status_code=400, detail=f"Invalid assessment type. Must be one of: {valid_types}")
        
        # Create the main assessment
        assessment = Assessment(
            teacher_id=current_teacher.id,
            title=assessment_data.title.strip(),
            description=assessment_data.description.strip() if assessment_data.description else None,
            subject=assessment_data.subject.strip(),
            class_name=assessment_data.class_name.strip(),
            assessment_type=assessment_data.assessment_type.strip(),
            tags=assessment_data.tags,
            is_published=False
        )
        
        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)
        
        # Calculate total points and create assessment questions
        total_points = 0
        assessment_questions = []
        
        for i, question_id in enumerate(assessment_data.question_ids):
            # Get the question to verify it exists and belongs to the teacher
            question_query = select(Question).where(
                Question.id == question_id,
                Question.teacher_id == current_teacher.id
            )
            question_result = await db.execute(question_query)
            question = question_result.scalars().first()
            
            if not question:
                logger.error(f"Question {question_id} not found or doesn't belong to teacher")
                raise HTTPException(status_code=404, detail=f"Question {question_id} not found or doesn't belong to teacher")
            
            # Calculate points for this question including subquestions if any
            question_points = question.points
            
            # Get question details to check for subquestions
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
            detail_result = await db.execute(detail_query)
            detail = detail_result.scalars().first()
            
            # If question has subquestions, add their points
            if detail and detail.sub_questions:
                subquestion_points = sum(sub["points"] for sub in detail.sub_questions if "points" in sub)
                question_points += subquestion_points
            
            # Create assessment question link
            assessment_question = AssessmentQuestion(
                assessment_id=assessment.id,
                question_id=question_id,
                question_order=i,
                points=question_points,
                section_id=None  # For non-sectioned assessments
            )
            
            db.add(assessment_question)
            assessment_questions.append(assessment_question)
            total_points += question_points
        
        # Update total points
        assessment.total_points = total_points
        
        await db.commit()
        await db.refresh(assessment)
        
        # Refresh all assessment questions
        for aq in assessment_questions:
            await db.refresh(aq)
        
        logger.debug(f"Successfully created assessment: id={assessment.id}")
        
        # Prepare response with assessment questions and their details
        response_assessment_questions = []
        for aq in assessment_questions:
            # Get the question details
            question_query = select(Question).where(Question.id == aq.question_id)
            question_result = await db.execute(question_query)
            question = question_result.scalars().first()
            
            if question:
                # Get question detail
                detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question.id)
                detail_result = await db.execute(detail_query)
                detail = detail_result.scalars().first()
                
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating assessment: {str(e)}")

@router.post("/create-assessment-with-sections", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_with_sections(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    assessment_data: AssessmentWithSectionsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new assessment with sections (for exams) and populate all three tables"""
    logger.debug(f"Creating assessment with sections: teacher_id={current_teacher.id}, title={assessment_data.title}")
    try:
        # Validate inputs
        if not assessment_data.title.strip():
            logger.error("Assessment title cannot be empty")
            raise HTTPException(status_code=400, detail="Assessment title cannot be empty")
        
        if not assessment_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        
        if not assessment_data.class_name.strip():
            logger.error("Class name cannot be empty")
            raise HTTPException(status_code=400, detail="Class name cannot be empty")
        
        if not assessment_data.assessment_type.strip():
            logger.error("Assessment type cannot be empty")
            raise HTTPException(status_code=400, detail="Assessment type cannot be empty")
        
        # Validate assessment type
        valid_types = ["quiz", "test", "exercise", "exam", "assignment", "project"]
        if assessment_data.assessment_type not in valid_types:
            logger.error(f"Invalid assessment type: {assessment_data.assessment_type}")
            raise HTTPException(status_code=400, detail=f"Invalid assessment type. Must be one of: {valid_types}")
        
        # Create the main assessment
        assessment = Assessment(
            teacher_id=current_teacher.id,
            title=assessment_data.title.strip(),
            description=assessment_data.description.strip() if assessment_data.description else None,
            subject=assessment_data.subject.strip(),
            class_name=assessment_data.class_name.strip(),
            assessment_type=assessment_data.assessment_type.strip(),
            tags=assessment_data.tags,
            is_published=False
        )
        
        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)
        
        # Create sections and track section IDs
        sections = []
        section_objects = []
        total_points = 0
        
        for i, section_data in enumerate(assessment_data.sections):
            section = AssessmentSection(
                assessment_id=assessment.id,
                name=section_data.name.strip(),
                description=section_data.description.strip() if section_data.description else None,
                section_order=section_data.section_order if section_data.section_order is not None else i
            )
            db.add(section)
            sections.append(section)
        
        if sections:
            await db.commit()
            for section in sections:
                await db.refresh(section)
                section_objects.append(section)
        
        # Create assessment questions and section questions
        assessment_questions = []
        section_questions = []
        
        # Process each section's questions
        for i, section_data in enumerate(assessment_data.sections):
            section = section_objects[i]  # Get the created section object
            section_total_points = 0
            
            for j, question_id in enumerate(section_data.questions):
                # Verify the question exists and belongs to the teacher
                question_query = select(Question).where(
                    Question.id == question_id,
                    Question.teacher_id == current_teacher.id
                )
                question_result = await db.execute(question_query)
                question = question_result.scalars().first()
                
                if not question:
                    logger.error(f"Question {question_id} not found or doesn't belong to teacher")
                    raise HTTPException(status_code=404, detail=f"Question {question_id} not found or doesn't belong to teacher")
                
                # Calculate points for this question including subquestions if any
                question_points = question.points
                
                # Get question details to check for subquestions
                detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
                detail_result = await db.execute(detail_query)
                detail = detail_result.scalars().first()
                
                # If question has subquestions, add their points
                if detail and detail.sub_questions:
                    subquestion_points = sum(sub["points"] for sub in detail.sub_questions if "points" in sub)
                    question_points += subquestion_points
                
                # Create assessment question link
                assessment_question = AssessmentQuestion(
                    assessment_id=assessment.id,
                    question_id=question_id,
                    question_order=j,  # Order within the entire assessment
                    points=question_points,
                    section_id=section.id  # Link to the specific section
                )
                
                db.add(assessment_question)
                assessment_questions.append(assessment_question)
                total_points += question_points
                section_total_points += question_points
                
                # Create section question link
                section_question = AssessmentSectionQuestion(
                    section_id=section.id,
                    question_id=question_id,
                    question_order=j,  # Order within the section
                    points=question_points
                )
                
                db.add(section_question)
                section_questions.append(section_question)
        
        # Update assessment total points
        assessment.total_points = total_points
        
        await db.commit()
        await db.refresh(assessment)
        
        # Refresh all created objects
        for aq in assessment_questions:
            await db.refresh(aq)
        
        for sq in section_questions:
            await db.refresh(sq)
        
        logger.debug(f"Successfully created assessment with sections: id={assessment.id}")
        
        # Prepare response with assessment questions and their details
        response_assessment_questions = []
        for aq in assessment_questions:
            # Get the question details
            question_query = select(Question).where(Question.id == aq.question_id)
            question_result = await db.execute(question_query)
            question = question_result.scalars().first()
            
            if question:
                # Get question detail
                detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question.id)
                detail_result = await db.execute(detail_query)
                detail = detail_result.scalars().first()
                
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        # Prepare sections response
        response_sections = []
        for section in section_objects:
            response_sections.append({
                "id": section.id,
                "assessment_id": section.assessment_id,
                "name": section.name,
                "description": section.description,
                "section_order": section.section_order,
                "created_at": section.created_at,
                "updated_at": section.updated_at
            })
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions,
            sections=response_sections
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating assessment with sections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating assessment with sections: {str(e)}")

@router.get("/read-assessments", response_model=List[AssessmentResponse])
async def read_assessments(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: Optional[str] = None,
    class_name: Optional[str] = None,
    assessment_type: Optional[str] = None,
    is_published: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Read assessments with optional filters"""
    logger.debug(f"Reading assessments: teacher_id={current_teacher.id}")
    try:
        # Build query for assessments
        query = select(Assessment).where(Assessment.teacher_id == current_teacher.id)
        
        # Apply filters
        if subject:
            query = query.where(Assessment.subject == subject.strip())
        if class_name:
            query = query.where(Assessment.class_name == class_name.strip())
        if assessment_type:
            query = query.where(Assessment.assessment_type == assessment_type.strip())
        if is_published is not None:
            query = query.where(Assessment.is_published == is_published)
        
        result = await db.execute(query)
        assessments = result.scalars().all()
        
        if not assessments:
            logger.debug("No assessments found")
            return []
        
        # Get assessment questions for all assessments
        assessment_ids = [a.id for a in assessments]
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id.in_(assessment_ids))
        aq_result = await db.execute(aq_query)
        aq_map = {}  # Map assessment_id to list of assessment questions
        for aq in aq_result.scalars().all():
            if aq.assessment_id not in aq_map:
                aq_map[aq.assessment_id] = []
            aq_map[aq.assessment_id].append(aq)
        
        # Get all unique question IDs
        question_ids = list(set([aq.question_id for aqs in aq_map.values() for aq in aqs]))
        question_map = {}  # Map question_id to question
        detail_map = {}    # Map question_id to question detail
        
        if question_ids:
            # Get questions
            question_query = select(Question).where(Question.id.in_(question_ids))
            question_result = await db.execute(question_query)
            for question in question_result.scalars().all():
                question_map[question.id] = question
            
            # Get question details
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Build response
        response = []
        for assessment in assessments:
            assessment_questions = aq_map.get(assessment.id, [])
            
            # Prepare assessment questions with question details
            response_assessment_questions = []
            for aq in assessment_questions:
                question = question_map.get(aq.question_id)
                detail = detail_map.get(aq.question_id)
                
                if question:
                    # Prepare question response
                    response_options = None
                    if detail and detail.options:
                        response_options = [
                            QuestionOption(
                                id=opt["id"],
                                text=opt["text"],
                                is_correct=opt["is_correct"]
                            )
                            for opt in detail.options
                        ]
                    
                    response_matching_pairs = None
                    if detail and detail.matching_pairs:
                        response_matching_pairs = [
                            MatchingPair(
                                id=pair["id"],
                                left=pair["left"],
                                right=pair["right"]
                            )
                            for pair in detail.matching_pairs
                        ]
                    
                    response_sub_questions = None
                    if detail and detail.sub_questions:
                        response_sub_questions = [
                            SubQuestion(
                                id=sub["id"],
                                type=sub["type"],
                                question_text=sub["question_text"],
                                correct_answer=sub["correct_answer"],
                                explanation=sub["explanation"],
                                marking_guidelines=sub["marking_guidelines"],
                                points=sub["points"]
                            )
                            for sub in detail.sub_questions
                        ]
                    
                    question_response = QuestionResponse(
                        id=question.id,
                        teacher_id=question.teacher_id,
                        subject=question.subject,
                        class_name=question.class_name,
                        strand=question.strand,
                        topic=question.topic,
                        type=question.type,
                        question_text=question.question_text,
                        points=question.points,
                        tags=question.tags,
                        created_at=question.created_at,
                        updated_at=question.updated_at,
                        options=response_options,
                        correct_answer=detail.correct_answer if detail else None,
                        explanation=detail.explanation if detail else None,
                        marking_guidelines=detail.marking_guidelines if detail else None,
                        matching_pairs=response_matching_pairs,
                        sub_questions=response_sub_questions
                    )
                    
                    response_assessment_questions.append(AssessmentQuestionResponse(
                        id=aq.id,
                        assessment_id=aq.assessment_id,
                        question_id=aq.question_id,
                        question_order=aq.question_order,
                        points=aq.points,
                        section_id=aq.section_id,  # Include section_id in response
                        created_at=aq.created_at,
                        question=question_response
                    ))
            
            # Get sections for this assessment
            section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment.id)
            section_result = await db.execute(section_query)
            sections = section_result.scalars().all()
            
            response_sections = []
            for section in sections:
                response_sections.append({
                    "id": section.id,
                    "assessment_id": section.assessment_id,
                    "name": section.name,
                    "description": section.description,
                    "section_order": section.section_order,
                    "created_at": section.created_at,
                    "updated_at": section.updated_at
                })
            
            response.append(AssessmentResponse(
                id=assessment.id,
                teacher_id=assessment.teacher_id,
                title=assessment.title,
                description=assessment.description,
                subject=assessment.subject,
                class_name=assessment.class_name,
                assessment_type=assessment.assessment_type,
                total_points=assessment.total_points,
                tags=assessment.tags,
                is_published=assessment.is_published,
                created_at=assessment.created_at,
                updated_at=assessment.updated_at,
                assessment_questions=response_assessment_questions,
                sections=response_sections
            ))
        
        logger.debug(f"Returning {len(response)} assessments")
        return response
    except Exception as e:
        logger.error(f"Error reading assessments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessments: {str(e)}")


@router.get("/read-assessment/{assessment_id}", response_model=AssessmentResponse)
async def read_assessment_by_id(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Read a specific assessment by ID"""
    logger.debug(f"Reading assessment: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Get assessment questions
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        # Get all unique question IDs
        question_ids = [aq.question_id for aq in assessment_questions]
        question_map = {}  # Map question_id to question
        detail_map = {}    # Map question_id to question detail
        
        if question_ids:
            # Get questions
            question_query = select(Question).where(Question.id.in_(question_ids))
            question_result = await db.execute(question_query)
            for question in question_result.scalars().all():
                question_map[question.id] = question
            
            # Get question details
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Prepare assessment questions with question details
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        # Get sections for this assessment
        section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment_id)
        section_result = await db.execute(section_query)
        sections = section_result.scalars().all()
        
        response_sections = []
        for section in sections:
            response_sections.append({
                "id": section.id,
                "assessment_id": section.assessment_id,
                "name": section.name,
                "description": section.description,
                "section_order": section.section_order,
                "created_at": section.created_at,
                "updated_at": section.updated_at
            })
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions,
            sections=response_sections
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assessment: {str(e)}")

@router.put("/update-assessment/{assessment_id}", response_model=AssessmentResponse, status_code=status.HTTP_200_OK)
async def update_assessment(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    assessment_data: AssessmentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an assessment"""
    logger.debug(f"Updating assessment: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Store original is_published status
        original_is_published = assessment.is_published
        
        # Update assessment fields
        if assessment_data.title is not None:
            if not assessment_data.title.strip():
                logger.error("Assessment title cannot be empty")
                raise HTTPException(status_code=400, detail="Assessment title cannot be empty")
            assessment.title = assessment_data.title.strip()
        
        if assessment_data.description is not None:
            assessment.description = assessment_data.description.strip() if assessment_data.description.strip() else None
        
        if assessment_data.subject is not None:
            if not assessment_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            assessment.subject = assessment_data.subject.strip()
        
        if assessment_data.class_name is not None:
            if not assessment_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            assessment.class_name = assessment_data.class_name.strip()
        
        if assessment_data.assessment_type is not None:
            # Validate assessment type
            valid_types = ["quiz", "test", "exercise", "exam", "assignment", "project"]
            if assessment_data.assessment_type not in valid_types:
                logger.error(f"Invalid assessment type: {assessment_data.assessment_type}")
                raise HTTPException(status_code=400, detail=f"Invalid assessment type. Must be one of: {valid_types}")
            assessment.assessment_type = assessment_data.assessment_type.strip()
        
        if assessment_data.tags is not None:
            assessment.tags = assessment_data.tags
        
        if assessment_data.is_published is not None:
            assessment.is_published = assessment_data.is_published
        
        assessment.updated_at = datetime.utcnow()
        
        # Handle question_ids update if provided
        if assessment_data.question_ids is not None:
            # Delete existing assessment questions
            existing_aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
            existing_aq_result = await db.execute(existing_aq_query)
            existing_assessment_questions = existing_aq_result.scalars().all()
            
            for aq in existing_assessment_questions:
                await db.delete(aq)
            
            await db.flush()  # Ensure deletions are processed
            
            # Add new assessment questions
            total_points = 0
            for i, question_id in enumerate(assessment_data.question_ids):
                # Verify the question exists and belongs to the teacher
                question_query = select(Question).where(
                    Question.id == question_id,
                    Question.teacher_id == current_teacher.id
                )
                question_result = await db.execute(question_query)
                question = question_result.scalars().first()
                
                if not question:
                    logger.error(f"Question {question_id} not found for teacher {current_teacher.id}")
                    raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
                
                # Calculate points for this question including subquestions if any
                question_points = question.points
                
                # Get question details to check for subquestions
                detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
                detail_result = await db.execute(detail_query)
                detail = detail_result.scalars().first()
                
                # If question has subquestions, add their points
                if detail and detail.sub_questions:
                    subquestion_points = sum(sub["points"] for sub in detail.sub_questions if "points" in sub)
                    question_points += subquestion_points
                
                # Create new assessment question
                assessment_question = AssessmentQuestion(
                    assessment_id=assessment_id,
                    question_id=question_id,
                    question_order=i,
                    points=question_points,
                    section_id=None  # For non-exam assessments, section_id is None
                )
                
                db.add(assessment_question)
                total_points += question_points
            
            # Update total points
            assessment.total_points = total_points
        
        assessment.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(assessment)
        
        logger.debug(f"Successfully updated assessment with sections: id={assessment.id}")
        
        # Check if the assessment is published and update the corresponding AssessmentAssignment
        if assessment.is_published:
            # Get the assessment assignment to update it
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            if assignment:
                # Update the assignment with the latest assessment data
                assignment.subject = assessment.subject
                assignment.class_name = assessment.class_name
                assignment.updated_at = datetime.utcnow()
                
                db.add(assignment)
                await db.commit()
                await db.refresh(assignment)
                
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UPDATE_PUBLISHING",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "available_from": assignment.available_from.isoformat() if assignment.available_from else None,
                        "available_until": assignment.available_until.isoformat() if assignment.available_until else None,
                        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                        "time_limit_minutes": assignment.time_limit_minutes,
                        "is_active": assignment.is_active,
                        "message": f"Assessment '{assessment.title}' has been updated"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
            elif original_is_published != assessment.is_published:
                # If assessment is now published but there was no existing assignment,
                # this might be an edge case - log for debugging
                logger.warning(f"Assessment {assessment_id} is published but no assignment found")
        elif original_is_published and not assessment.is_published:
            # If assessment was published but is now unpublished, send WebSocket notifications
            # Get the assessment assignment to get student access information
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            if assignment:
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UNPUBLISHED_ASSESSMENT",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "message": f"Assessment '{assessment.title}' has been unpublished"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
        
        # Prepare response with assessment questions and their details
        # Get assessment questions for response
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment.id)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        # Get all unique question IDs
        question_ids = [aq.question_id for aq in assessment_questions]
        question_map = {}  # Map question_id to question
        detail_map = {}    # Map question_id to question detail
        
        if question_ids:
            # Get questions
            question_query = select(Question).where(Question.id.in_(question_ids))
            question_result = await db.execute(question_query)
            for question in question_result.scalars().all():
                question_map[question.id] = question
            
            # Get question details
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Prepare assessment questions with question details
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Prepare assessment questions with question details
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating assessment: {str(e)}")

@router.put("/update-assessment/{assessment_id}", response_model=AssessmentResponse, status_code=status.HTTP_200_OK)
async def update_assessment(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    assessment_data: AssessmentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an assessment"""
    logger.debug(f"Updating assessment: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Store original is_published status
        original_is_published = assessment.is_published
        
        # Update assessment fields
        if assessment_data.title is not None:
            if not assessment_data.title.strip():
                logger.error("Assessment title cannot be empty")
                raise HTTPException(status_code=400, detail="Assessment title cannot be empty")
            assessment.title = assessment_data.title.strip()
        
        if assessment_data.description is not None:
            assessment.description = assessment_data.description.strip() if assessment_data.description.strip() else None
        
        if assessment_data.subject is not None:
            if not assessment_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            assessment.subject = assessment_data.subject.strip()
        
        if assessment_data.class_name is not None:
            if not assessment_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            assessment.class_name = assessment_data.class_name.strip()
        
        if assessment_data.assessment_type is not None:
            # Validate assessment type
            valid_types = ["quiz", "test", "exercise", "exam", "assignment", "project"]
            if assessment_data.assessment_type not in valid_types:
                logger.error(f"Invalid assessment type: {assessment_data.assessment_type}")
                raise HTTPException(status_code=400, detail=f"Invalid assessment type. Must be one of: {valid_types}")
            assessment.assessment_type = assessment_data.assessment_type.strip()
        
        if assessment_data.tags is not None:
            assessment.tags = assessment_data.tags
        
        if assessment_data.is_published is not None:
            assessment.is_published = assessment_data.is_published
        
        assessment.updated_at = datetime.utcnow()
        
        # Handle question_ids update if provided
        if assessment_data.question_ids is not None:
            # Delete existing assessment questions
            existing_aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
            existing_aq_result = await db.execute(existing_aq_query)
            existing_assessment_questions = existing_aq_result.scalars().all()
            
            for aq in existing_assessment_questions:
                await db.delete(aq)
            
            await db.flush()  # Ensure deletions are processed
            
            # Add new assessment questions
            total_points = 0
            for i, question_id in enumerate(assessment_data.question_ids):
                # Verify the question exists and belongs to the teacher
                question_query = select(Question).where(
                    Question.id == question_id,
                    Question.teacher_id == current_teacher.id
                )
                question_result = await db.execute(question_query)
                question = question_result.scalars().first()
                
                if not question:
                    logger.error(f"Question {question_id} not found for teacher {current_teacher.id}")
                    raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
                
                # Calculate points for this question including subquestions if any
                question_points = question.points
                
                # Get question details to check for subquestions
                detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
                detail_result = await db.execute(detail_query)
                detail = detail_result.scalars().first()
                
                # If question has subquestions, add their points
                if detail and detail.sub_questions:
                    subquestion_points = sum(sub["points"] for sub in detail.sub_questions if "points" in sub)
                    question_points += subquestion_points
                
                # Create new assessment question
                assessment_question = AssessmentQuestion(
                    assessment_id=assessment_id,
                    question_id=question_id,
                    question_order=i,
                    points=question_points,
                    section_id=None  # For non-exam assessments, section_id is None
                )
                
                db.add(assessment_question)
                total_points += question_points
            
            # Update total points
            assessment.total_points = total_points
        
        assessment.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(assessment)
        
        logger.debug(f"Successfully updated assessment: id={assessment.id}")
        
        # Handle WebSocket notifications for published assessments
        if assessment.is_published:
            # Get or create the assessment assignment
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            # If no assignment exists and assessment is now published, we might need to create one
            # But for updates, we should only work with existing assignments
            if assignment:
                # Update the assignment with the latest assessment data
                assignment.subject = assessment.subject
                assignment.class_name = assessment.class_name
                assignment.updated_at = datetime.utcnow()
                
                db.add(assignment)
                await db.commit()
                await db.refresh(assignment)
                
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UPDATE_PUBLISHING",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "available_from": assignment.available_from.isoformat() if assignment.available_from else None,
                        "available_until": assignment.available_until.isoformat() if assignment.available_until else None,
                        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                        "time_limit_minutes": assignment.time_limit_minutes,
                        "is_active": assignment.is_active,
                        "message": f"Assessment '{assessment.title}' has been updated"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
            elif original_is_published != assessment.is_published and assessment.is_published:
                # If assessment is now published but there was no existing assignment,
                # this might be an edge case - log for debugging
                logger.warning(f"Assessment {assessment_id} is published but no assignment found")
        elif original_is_published and not assessment.is_published:
            # If assessment was published but is now unpublished, send WebSocket notifications
            # Get the assessment assignment to get student access information
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            if assignment:
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UNPUBLISHED_ASSESSMENT",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "message": f"Assessment '{assessment.title}' has been unpublished"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
        
        # Prepare response with assessment questions and their details
        # Get assessment questions for response
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment.id)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        # Get all unique question IDs
        question_ids = [aq.question_id for aq in assessment_questions]
        question_map = {}  # Map question_id to question
        detail_map = {}    # Map question_id to question detail
        
        if question_ids:
            # Get questions
            question_query = select(Question).where(Question.id.in_(question_ids))
            question_result = await db.execute(question_query)
            for question in question_result.scalars().all():
                question_map[question.id] = question
            
            # Get question details
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Prepare assessment questions with question details
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating assessment: {str(e)}")

@router.put("/update-assessment-with-sections/{assessment_id}", response_model=AssessmentResponse, status_code=status.HTTP_200_OK)
async def update_assessment_with_sections(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    assessment_data: AssessmentWithSectionsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an assessment with sections and questions"""
    logger.debug(f"Updating assessment with sections: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Store original is_published status
        original_is_published = assessment.is_published
        
        # Update assessment fields if provided
        if assessment_data.title is not None:
            if not assessment_data.title.strip():
                logger.error("Assessment title cannot be empty")
                raise HTTPException(status_code=400, detail="Assessment title cannot be empty")
            assessment.title = assessment_data.title.strip()
        
        if assessment_data.description is not None:
            assessment.description = assessment_data.description.strip() if assessment_data.description.strip() else None
        
        if assessment_data.subject is not None:
            if not assessment_data.subject.strip():
                logger.error("Subject cannot be empty")
                raise HTTPException(status_code=400, detail="Subject cannot be empty")
            assessment.subject = assessment_data.subject.strip()
        
        if assessment_data.class_name is not None:
            if not assessment_data.class_name.strip():
                logger.error("Class name cannot be empty")
                raise HTTPException(status_code=400, detail="Class name cannot be empty")
            assessment.class_name = assessment_data.class_name.strip()
        
        if assessment_data.assessment_type is not None:
            # Validate assessment type
            valid_types = ["quiz", "test", "exercise", "exam", "assignment", "project"]
            if assessment_data.assessment_type not in valid_types:
                logger.error(f"Invalid assessment type: {assessment_data.assessment_type}")
                raise HTTPException(status_code=400, detail=f"Invalid assessment type. Must be one of: {valid_types}")
            assessment.assessment_type = assessment_data.assessment_type.strip()
        
        if assessment_data.tags is not None:
            assessment.tags = assessment_data.tags
        
        if assessment_data.is_published is not None:
            assessment.is_published = assessment_data.is_published
        
        assessment.updated_at = datetime.utcnow()
        
        # Handle sections if provided
        total_points = 0
        if assessment_data.sections is not None:
            # Get existing sections
            existing_sections_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment_id)
            existing_sections_result = await db.execute(existing_sections_query)
            existing_sections = existing_sections_result.scalars().all()
            existing_section_map = {section.id: section for section in existing_sections}
            
            # Track sections to keep and sections to delete
            updated_section_ids = []
            section_objects = []
            
            # Process each section in the update data
            for section_data in assessment_data.sections:
                if section_data.id and section_data.id in existing_section_map:
                    # Update existing section
                    section = existing_section_map[section_data.id]
                    section.name = section_data.name.strip()
                    section.description = section_data.description.strip() if section_data.description else None
                    section.section_order = section_data.section_order if section_data.section_order is not None else section.section_order
                    updated_section_ids.append(section.id)
                    section_objects.append(section)
                else:
                    # Create new section
                    section = AssessmentSection(
                        assessment_id=assessment_id,
                        name=section_data.name.strip(),
                        description=section_data.description.strip() if section_data.description else None,
                        section_order=section_data.section_order if section_data.section_order is not None else 0
                    )
                    db.add(section)
                    section_objects.append(section)
            
            # Delete sections that are not in the update data
            sections_to_delete = [section for section in existing_sections if section.id not in updated_section_ids]
            for section in sections_to_delete:
                # Delete associated assessment section questions
                asq_query = select(AssessmentSectionQuestion).where(AssessmentSectionQuestion.section_id == section.id)
                asq_result = await db.execute(asq_query)
                asq_records = asq_result.scalars().all()
                for asq in asq_records:
                    await db.delete(asq)
                
                # Delete associated assessment questions linked to this section
                aq_query = select(AssessmentQuestion).where(
                    AssessmentQuestion.assessment_id == assessment_id,
                    AssessmentQuestion.section_id == section.id
                )
                aq_result = await db.execute(aq_query)
                aq_records = aq_result.scalars().all()
                for aq in aq_records:
                    await db.delete(aq)
                
                await db.delete(section)
            
            # Commit section changes
            await db.commit()
            
            # Refresh section objects
            for section in section_objects:
                if not section.id:  # Only refresh newly created sections
                    await db.refresh(section)
            
            # Update assessment questions and section questions
            # First, delete all existing assessment questions and section questions for this assessment
            # Get all existing assessment questions
            existing_aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
            existing_aq_result = await db.execute(existing_aq_query)
            existing_aq_records = existing_aq_result.scalars().all()
            
            # Delete all existing assessment questions
            for aq in existing_aq_records:
                await db.delete(aq)
            
            # Get all existing section questions
            if updated_section_ids:
                existing_asq_query = select(AssessmentSectionQuestion).where(
                    AssessmentSectionQuestion.section_id.in_(updated_section_ids)
                )
                existing_asq_result = await db.execute(existing_asq_query)
                existing_asq_records = existing_asq_result.scalars().all()
                
                # Delete all existing section questions
                for asq in existing_asq_records:
                    await db.delete(asq)
            
            # Create new assessment questions and section questions
            assessment_questions = []
            section_questions = []
            
            # Process each section's questions
            for i, section_data in enumerate(assessment_data.sections):
                # Find the corresponding section object
                section = None
                if section_data.id and section_data.id in existing_section_map:
                    section = existing_section_map[section_data.id]
                else:
                    # For newly created sections, find by name and order
                    for s in section_objects:
                        if s.name == section_data.name.strip() and s.section_order == (section_data.section_order if section_data.section_order is not None else 0):
                            section = s
                            break
                
                if not section:
                    continue  # Skip if section not found
                
                section_total_points = 0
                
                for j, question_id in enumerate(section_data.questions):
                    # Verify the question exists and belongs to the teacher
                    question_query = select(Question).where(
                        Question.id == question_id,
                        Question.teacher_id == current_teacher.id
                    )
                    question_result = await db.execute(question_query)
                    question = question_result.scalars().first()
                    
                    if not question:
                        logger.error(f"Question {question_id} not found or doesn't belong to teacher")
                        raise HTTPException(status_code=404, detail=f"Question {question_id} not found or doesn't belong to teacher")
                    
                    # Calculate points for this question including subquestions if any
                    question_points = question.points
                    
                    # Get question details to check for subquestions
                    detail_query = select(QuestionDetail).where(QuestionDetail.question_id == question_id)
                    detail_result = await db.execute(detail_query)
                    detail = detail_result.scalars().first()
                    
                    # If question has subquestions, add their points
                    if detail and detail.sub_questions:
                        subquestion_points = sum(sub["points"] for sub in detail.sub_questions if "points" in sub)
                        question_points += subquestion_points
                    
                    # Create assessment question link
                    assessment_question = AssessmentQuestion(
                        assessment_id=assessment_id,
                        question_id=question_id,
                        question_order=j,  # Order within the entire assessment
                        points=question_points,
                        section_id=section.id  # Link to the specific section
                    )
                    
                    db.add(assessment_question)
                    assessment_questions.append(assessment_question)
                    total_points += question_points
                    section_total_points += question_points
                    
                    # Create section question link
                    section_question = AssessmentSectionQuestion(
                        section_id=section.id,
                        question_id=question_id,
                        question_order=j,  # Order within the section
                        points=question_points
                    )
                    
                    db.add(section_question)
                    section_questions.append(section_question)
            
            # Update assessment total points
            assessment.total_points = total_points
        
        await db.commit()
        await db.refresh(assessment)
        
        logger.debug(f"Successfully updated assessment with sections: id={assessment.id}")
        
        # Handle WebSocket notifications for published assessments
        if assessment.is_published:
            # Get or create the assessment assignment
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            # If no assignment exists and assessment is now published, we might need to create one
            # But for updates, we should only work with existing assignments
            if assignment:
                # Update the assignment with the latest assessment data
                assignment.subject = assessment.subject
                assignment.class_name = assessment.class_name
                assignment.updated_at = datetime.utcnow()
                
                db.add(assignment)
                await db.commit()
                await db.refresh(assignment)
                
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UPDATE_PUBLISHING",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "available_from": assignment.available_from.isoformat() if assignment.available_from else None,
                        "available_until": assignment.available_until.isoformat() if assignment.available_until else None,
                        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                        "time_limit_minutes": assignment.time_limit_minutes,
                        "is_active": assignment.is_active,
                        "message": f"Assessment '{assessment.title}' has been updated"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
            elif original_is_published != assessment.is_published and assessment.is_published:
                # If assessment is now published but there was no existing assignment,
                # this might be an edge case - log for debugging
                logger.warning(f"Assessment {assessment_id} is published but no assignment found")
        elif original_is_published and not assessment.is_published:
            # If assessment was published but is now unpublished, send WebSocket notifications
            # Get the assessment assignment to get student access information
            assignment_query = select(AssessmentAssignment).where(
                AssessmentAssignment.assessment_id == assessment_id
            )
            assignment_result = await db.execute(assignment_query)
            assignment = assignment_result.scalars().first()
            
            if assignment:
                # Get student IDs who have access to this assignment
                student_ids = []
                access_rules_query = select(StudentAccessRule).where(
                    StudentAccessRule.assignment_id == assignment.id
                )
                access_rules_result = await db.execute(access_rules_query)
                access_rules = access_rules_result.scalars().all()
                for access_rule in access_rules:
                    if access_rule.student_id:
                        student_ids.append(str(access_rule.student_id))
                
                # Send WebSocket notifications to students who have access to this assignment
                if student_ids:
                    websocket_message = {
                        "type": "UNPUBLISHED_ASSESSMENT",
                        "assignment_id": assignment.id,
                        "assessment_id": assessment.id,
                        "title": assessment.title,
                        "subject": assignment.subject,
                        "class_name": assignment.class_name,
                        "message": f"Assessment '{assessment.title}' has been unpublished"
                    }
                    
                    # Send WebSocket message to each student
                    for student_id in student_ids:
                        try:
                            await publish_student_ws_message(student_id, websocket_message)
                        except Exception as e:
                            logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
        
        # Prepare response with assessment questions and their details
        # Get assessment questions for response
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment.id)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        # Get all unique question IDs
        question_ids = [aq.question_id for aq in assessment_questions]
        question_map = {}  # Map question_id to question
        detail_map = {}    # Map question_id to question detail
        
        if question_ids:
            # Get questions
            question_query = select(Question).where(Question.id.in_(question_ids))
            question_result = await db.execute(question_query)
            for question in question_result.scalars().all():
                question_map[question.id] = question
            
            # Get question details
            detail_query = select(QuestionDetail).where(QuestionDetail.question_id.in_(question_ids))
            detail_result = await db.execute(detail_query)
            for detail in detail_result.scalars().all():
                detail_map[detail.question_id] = detail
        
        # Prepare assessment questions with question details
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response
                response_options = None
                if detail and detail.options:
                    response_options = [
                        QuestionOption(
                            id=opt["id"],
                            text=opt["text"],
                            is_correct=opt["is_correct"]
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        MatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        SubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            correct_answer=sub["correct_answer"],
                            explanation=sub["explanation"],
                            marking_guidelines=sub["marking_guidelines"],
                            points=sub["points"]
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = QuestionResponse(
                    id=question.id,
                    teacher_id=question.teacher_id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    tags=question.tags,
                    created_at=question.created_at,
                    updated_at=question.updated_at,
                    options=response_options,
                    correct_answer=detail.correct_answer if detail else None,
                    explanation=detail.explanation if detail else None,
                    marking_guidelines=detail.marking_guidelines if detail else None,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(AssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,  # Include section_id in response
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        # Get sections for this assessment
        section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment_id)
        section_result = await db.execute(section_query)
        sections = section_result.scalars().all()
        
        response_sections = []
        for section in sections:
            response_sections.append({
                "id": section.id,
                "assessment_id": section.assessment_id,
                "name": section.name,
                "description": section.description,
                "section_order": section.section_order,
                "created_at": section.created_at,
                "updated_at": section.updated_at
            })
        
        return AssessmentResponse(
            id=assessment.id,
            teacher_id=assessment.teacher_id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            tags=assessment.tags,
            is_published=assessment.is_published,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions,
            sections=response_sections
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment with sections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating assessment with sections: {str(e)}")

@router.delete("/delete-assessment/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Delete an assessment (hard delete)"""
    logger.debug(f"Deleting assessment: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Delete assessment questions first (due to foreign key constraint)
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        for aq in assessment_questions:
            await db.delete(aq)
        
        await db.flush()  # Ensure the assessment questions are deleted
        
        # Delete assessment section questions (due to foreign key constraints)
        # First get all sections for this assessment
        section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment_id)
        section_result = await db.execute(section_query)
        sections = section_result.scalars().all()
        
        # Get section IDs
        section_ids = [section.id for section in sections]
        
        if section_ids:
            # Delete assessment section questions
            asq_query = select(AssessmentSectionQuestion).where(AssessmentSectionQuestion.section_id.in_(section_ids))
            asq_result = await db.execute(asq_query)
            section_questions = asq_result.scalars().all()
            
            for asq in section_questions:
                await db.delete(asq)
            
            await db.flush()  # Ensure the section questions are deleted
        
        # Delete assessment sections (due to foreign key constraint)
        for section in sections:
            await db.delete(section)
        
        await db.flush()  # Ensure the sections are deleted
        
        # Delete the assessment (hard delete)
        await db.delete(assessment)
        await db.commit()
        
        logger.info(f"Successfully deleted assessment: id={assessment_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()  # Rollback in case of error
        logger.error(f"Error deleting assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting assessment: {str(e)}")

@router.post("/add-section-to-assessment/{assessment_id}", status_code=status.HTTP_201_CREATED)
async def add_section_to_assessment(
    assessment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    section_data: AssessmentSectionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a section to an existing assessment"""
    logger.debug(f"Adding section to assessment: assessment_id={assessment_id}, teacher_id={current_teacher.id}")
    try:
        # Get the assessment
        query = select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        # Create the section
        section = AssessmentSection(
            assessment_id=assessment_id,
            name=section_data.name.strip(),
            description=section_data.description.strip() if section_data.description else None,
            section_order=section_data.section_order
        )
        
        db.add(section)
        await db.commit()
        await db.refresh(section)
        
        logger.debug(f"Successfully added section to assessment: section_id={section.id}")
        
        return {
            "id": section.id,
            "assessment_id": section.assessment_id,
            "name": section.name,
            "description": section.description,
            "section_order": section.section_order,
            "created_at": section.created_at,
            "updated_at": section.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding section to assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding section to assessment: {str(e)}")

@router.delete("/delete-section/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Delete a section from an assessment"""
    logger.debug(f"Deleting section: section_id={section_id}, teacher_id={current_teacher.id}")
    try:
        # Get the section
        query = select(AssessmentSection).where(AssessmentSection.id == section_id)
        result = await db.execute(query)
        section = result.scalars().first()
        
        if not section:
            logger.error(f"Section {section_id} not found")
            raise HTTPException(status_code=404, detail=f"Section {section_id} not found")
        
        # Get the assessment to verify ownership
        assessment_query = select(Assessment).where(
            Assessment.id == section.assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            logger.error(f"Assessment {section.assessment_id} not found for teacher {current_teacher.id}")
            raise HTTPException(status_code=404, detail=f"Assessment not found or access denied")
        
        # Delete the section
        await db.delete(section)
        await db.commit()
        
        logger.info(f"Successfully deleted section: id={section_id}")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting section: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting section: {str(e)}")