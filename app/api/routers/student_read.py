from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Optional
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
import uuid
from app.models.model import Student, StudentEnrollment, SecuritySetting
from app.core.dependencies import get_current_student
from app.core.database import get_db
from app.core.logger import logger
from app.models.model import AssessmentAssignment, StudentAccessRule, SecuritySetting
from app.models.model import Assessment, Question, QuestionDetail, AssessmentQuestion, AssessmentSection, AssignmentStatus
from app.schemas.schemas import AssessmentCountResponse ,StudentAvailableAssessmentResponse, StudentAssessmentResponse, StudentEnrollmentResponse, StudentSubQuestion, DashboardDailyChallengeResponse
from app.schemas.schemas import StudentAssessmentQuestionResponse, StudentQuestionResponse, StudentAssessmentDetailResponse
from app.schemas.schemas import StudentAssignedAssessmentResponse,StudentAssessmentAccessResponse
from app.schemas.schemas import StudentAssessmentSectionResponse, StudentQuestionOption, StudentMatchingPair
from app.schemas.schemas import StudentAssessmentInitialDetailResponse  # Added import for initial detail response

router = APIRouter(tags=["Student Assessment Reader"])


# IMPORTANT: The count endpoint must be defined BEFORE the assignment_id endpoint to avoid routing conflicts
@router.get("/assessment-counts", response_model=AssessmentCountResponse)
async def get_assessment_counts(
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """
    Get assessment counts for dashboard tiles:
    - Total assessments (published, not completed)
    - Daily challenges (assigned in last 24 hours, not completed)
    - Enrolled courses (distinct subjects/classes student has access to)
    """
    logger.debug(f"Getting assessment counts for student: student_id={current_student.id}")
    try:
        # Get total assessments count (published, not completed)
        total_query = select(func.count(AssessmentAssignment.id)).where(
            AssessmentAssignment.is_active == True,
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            ),
            AssessmentAssignment.id.notin_(
                select(AssignmentStatus.assignment_id).where(
                    AssignmentStatus.student_id == current_student.id,
                    AssignmentStatus.is_completed == True
                )
            )
        )
        
        total_result = await db.execute(total_query)
        total_assessments = total_result.scalar_one()
        
        # Get daily challenges count (assigned in last 24 hours, not completed)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        daily_query = select(func.count(AssessmentAssignment.id)).where(
            AssessmentAssignment.available_from >= twenty_four_hours_ago,
            AssessmentAssignment.is_active == True,
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            ),
            AssessmentAssignment.id.notin_(
                select(AssignmentStatus.assignment_id).where(
                    AssignmentStatus.student_id == current_student.id,
                    AssignmentStatus.is_completed == True
                )
            )
        )
        
        daily_result = await db.execute(daily_query)
        daily_challenges = daily_result.scalar_one()
        
        # Get enrolled courses count (distinct subjects/classes)
        # This is now simplified to directly count the student's enrollments
        enrollment_query = select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.student_id == current_student.id,
            StudentEnrollment.is_active == True
        )
        
        enrollment_result = await db.execute(enrollment_query)
        enrolled_courses = enrollment_result.scalar_one()
        
        logger.debug(f"Assessment counts - Total: {total_assessments}, Daily: {daily_challenges}, Courses: {enrolled_courses}")
        
        return AssessmentCountResponse(
            total_assessments=total_assessments,
            daily_challenges=daily_challenges,
            enrolled_courses=enrolled_courses
        )
    except Exception as e:
        logger.error(f"Error getting assessment counts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting assessment counts: {str(e)}")


@router.get("/published-assessments/daily-challenges", response_model=List[DashboardDailyChallengeResponse])
async def get_dashboard_daily_challenges(
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get published assessments for the daily challenges section (assigned in the last 24 hours) - Simplified for dashboard"""
    logger.debug(f"Getting dashboard daily challenges for student: student_id={current_student.id}")
    try:
        # Get assignments assigned in the last 24 hours that are active and not completed
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.available_from >= twenty_four_hours_ago,
            AssessmentAssignment.is_active == True,
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            ),
            AssessmentAssignment.id.notin_(
                select(AssignmentStatus.assignment_id).where(
                    AssignmentStatus.student_id == current_student.id,
                    AssignmentStatus.is_completed == True
                )
            )
        )
        
        result = await db.execute(query)
        assignments = result.scalars().all()
        
        # Get assessment IDs from assignments
        assessment_ids = [assignment.assessment_id for assignment in assignments]
        
        if not assessment_ids:
            return []
        
        # Get assessments - only the basic information needed for dashboard
        assessment_query = select(Assessment).where(Assessment.id.in_(assessment_ids))
        assessment_result = await db.execute(assessment_query)
        assessments = assessment_result.scalars().all()
        
        # Create assessment ID to assignment mapping
        assignment_map = {assignment.assessment_id: assignment for assignment in assignments}
        
        # Build simplified response for dashboard
        response = []
        for assessment in assessments:
            assignment = assignment_map.get(assessment.id)
            if not assignment:
                continue
            
            response.append(DashboardDailyChallengeResponse(
                id=assignment.id,
                title=assessment.title,
                subject=assessment.subject,
                class_name=assessment.class_name,
                assessment_type=assessment.assessment_type,
                total_points=assessment.total_points,
                created_at=assessment.created_at
            ))
        
        logger.debug(f"Returning {len(response)} dashboard daily challenges")
        return response
    except Exception as e:
        logger.error(f"Error getting dashboard daily challenges: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting dashboard daily challenges: {str(e)}")

@router.get("/published-assessments/daily-challenges/{assignment_id}", response_model=StudentAssessmentResponse)
async def get_daily_challenge_detail(
    assignment_id: int,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get full details of a specific daily challenge when clicked"""
    logger.debug(f"Getting daily challenge detail: assignment_id={assignment_id}, student_id={current_student.id}")
    try:
        # Verify student has access to this assignment
        access_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id,
            StudentAccessRule.student_id == current_student.id,
            StudentAccessRule.can_access == True
        )
        access_result = await db.execute(access_query)
        access_rule = access_result.scalars().first()
        logger.info(f"Access rule: {access_rule}")
        if not access_rule:
            raise HTTPException(status_code=403, detail="Access denied to this assessment")
        
        # Verify assignment is active
        assignment_query = select(AssessmentAssignment).where(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.is_active == True
        )
        assignment_result = await db.execute(assignment_query)
        assignment = assignment_result.scalars().first()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assessment not found or not active")
        
        # Get the assessment
        assessment_query = select(Assessment).where(Assessment.id == assignment.assessment_id)
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment details not found")
        
        # Get assessment questions
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
        
        # Prepare assessment questions with question details (without answers/explanations)
        response_assessment_questions = []
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Prepare question response (without answers/explanations)
                response_options = None
                if detail and detail.options:
                    response_options = [
                        StudentQuestionOption(
                            id=opt["id"],
                            text=opt["text"]
                            # Note: Not including is_correct to avoid exposing answers
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        StudentMatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                            # Note: Not including correct matches to avoid exposing answers
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        StudentSubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            points=sub["points"]
                            # Note: Not including correct_answer, explanation, marking_guidelines
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = StudentQuestionResponse(
                    id=question.id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    created_at=question.created_at,
                    options=response_options,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(StudentAssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,
                    created_at=aq.created_at,
                    question=question_response
                ))
        
        # Get sections for this assessment
        section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment.id)
        section_result = await db.execute(section_query)
        sections = section_result.scalars().all()
        
        response_sections = []
        for section in sections:
            response_sections.append(StudentAssessmentSectionResponse(
                id=section.id,
                name=section.name,
                section_order=section.section_order,
                description=section.description,
                created_at=section.created_at
            ))
        
        response = StudentAssessmentResponse(
            id=assessment.id,
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at,
            assessment_questions=response_assessment_questions,
            sections=response_sections
        )
        
        logger.debug(f"Returning daily challenge detail for assignment_id={assignment_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily challenge detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting daily challenge detail: {str(e)}")

@router.get("/published-assessments/course/{subject}/{class_name}", response_model=List[StudentAssessmentResponse])
async def get_course_assessments(
    subject: str,
    class_name: str,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get published assessments for a specific course/subject"""
    logger.debug(f"Getting course assessments: subject={subject}, class_name={class_name}, student_id={current_student.id}")
    try:
        # Get active assignments for this student in the specified course that are not completed
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.is_active == True,
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            ),
            AssessmentAssignment.id.notin_(
                select(AssignmentStatus.assignment_id).where(
                    AssignmentStatus.student_id == current_student.id,
                    AssignmentStatus.is_completed == True
                )
            ),
            AssessmentAssignment.id.in_(
                select(Assessment.id).where(
                    Assessment.subject == subject,
                    Assessment.class_name == class_name
                )
            )
        )
        
        result = await db.execute(query)
        assignments = result.scalars().all()
        
        # Get assessment IDs from assignments
        assessment_ids = [assignment.assessment_id for assignment in assignments]
        
        if not assessment_ids:
            return []
        
        # Get assessments
        assessment_query = select(Assessment).where(Assessment.id.in_(assessment_ids))
        assessment_result = await db.execute(assessment_query)
        assessments = assessment_result.scalars().all()
        
        # Create assessment ID to assignment mapping
        assignment_map = {assignment.assessment_id: assignment for assignment in assignments}
        
        # Build response
        response = []
        for assessment in assessments:
            assignment = assignment_map.get(assessment.id)
            if not assignment:
                continue
            
            # Get assessment questions
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
            
            # Prepare assessment questions with question details (without answers/explanations)
            response_assessment_questions = []
            for aq in assessment_questions:
                question = question_map.get(aq.question_id)
                detail = detail_map.get(aq.question_id)
                
                if question:
                    # Prepare question response (without answers/explanations)
                    response_options = None
                    if detail and detail.options:
                        response_options = [
                            StudentQuestionOption(
                                id=opt["id"],
                                text=opt["text"]
                                # Note: Not including is_correct to avoid exposing answers
                            )
                            for opt in detail.options
                        ]
                    
                    response_matching_pairs = None
                    if detail and detail.matching_pairs:
                        response_matching_pairs = [
                            StudentMatchingPair(
                                id=pair["id"],
                                left=pair["left"],
                                right=pair["right"]
                                # Note: Not including correct matches to avoid exposing answers
                            )
                            for pair in detail.matching_pairs
                        ]
                    
                    response_sub_questions = None
                    if detail and detail.sub_questions:
                        response_sub_questions = [
                            StudentSubQuestion(
                                id=sub["id"],
                                type=sub["type"],
                                question_text=sub["question_text"],
                                points=sub["points"]
                                # Note: Not including correct_answer, explanation, marking_guidelines
                            )
                            for sub in detail.sub_questions
                        ]
                    
                    question_response = StudentQuestionResponse(
                        id=question.id,
                        subject=question.subject,
                        class_name=question.class_name,
                        strand=question.strand,
                        topic=question.topic,
                        type=question.type,
                        question_text=question.question_text,
                        points=question.points,
                        created_at=question.created_at,
                        options=response_options,
                        matching_pairs=response_matching_pairs,
                        sub_questions=response_sub_questions
                    )
                    
                    response_assessment_questions.append(StudentAssessmentQuestionResponse(
                        id=aq.id,
                        assessment_id=aq.assessment_id,
                        question_id=aq.question_id,
                        question_order=aq.question_order,
                        points=aq.points,
                        section_id=aq.section_id,
                        created_at=aq.created_at,
                        question=question_response
                    ))
            
            # Get sections for this assessment
            section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment.id)
            section_result = await db.execute(section_query)
            sections = section_result.scalars().all()
            
            response_sections = []
            for section in sections:
                response_sections.append(StudentAssessmentSectionResponse(
                    id=section.id,
                    name=section.name,
                    section_order=section.section_order,
                    description=section.description,
                    created_at=section.created_at
                ))
            
            response.append(StudentAssessmentResponse(
                id=assessment.id,
                title=assessment.title,
                description=assessment.description,
                subject=assessment.subject,
                class_name=assessment.class_name,
                assessment_type=assessment.assessment_type,
                total_points=assessment.total_points,
                created_at=assessment.created_at,
                updated_at=assessment.updated_at,
                assessment_questions=response_assessment_questions,
                sections=response_sections
            ))
        
        logger.debug(f"Returning {len(response)} course assessments")
        return response
    except Exception as e:
        logger.error(f"Error getting course assessments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting course assessments: {str(e)}")

@router.get("/students/me/enrollments", response_model=List[StudentEnrollmentResponse])
async def get_current_student_enrollments(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all enrollments for the currently authenticated student.
    
    Args:
        current_student: Authenticated student from token
        db: Database session
    
    Returns:
        List of student enrollments
    """
    logger.info(f"Fetching enrollments for current student ID: {current_student.id}")
    
    try:
        statement = select(StudentEnrollment).where(
            StudentEnrollment.student_id == current_student.id,
            StudentEnrollment.is_active == True
        ).order_by(StudentEnrollment.enrollment_date.desc())
        
        result = await db.execute(statement)
        enrollments = result.scalars().all()
        
        logger.info(f"Fetched {len(enrollments)} enrollments for student ID: {current_student.id}")
        return enrollments
    except Exception as e:
        logger.error(f"Error fetching enrollments for student ID {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch enrollments"
        )

@router.get("/student/assessments/course/{subject}/{class_name}", response_model=List[StudentAssessmentAccessResponse])
async def get_student_assessments_by_course(
    subject: str,
    class_name: str,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get assessments that student has access to (not completed) for a specific course when clicking on a course card"""
    logger.debug(f"Getting student assessments for course: subject={subject}, class_name={class_name}, student_id={current_student.id}")
    try:
        # Get active assignments for this student in the specified course that are not completed
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.is_active == True,
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            ),
            AssessmentAssignment.id.notin_(
                select(AssignmentStatus.assignment_id).where(
                    AssignmentStatus.student_id == current_student.id,
                    AssignmentStatus.is_completed == True
                )
            ),
            AssessmentAssignment.assessment_id.in_(
                select(Assessment.id).where(
                    Assessment.subject == subject,
                    Assessment.class_name == class_name,
                    Assessment.is_published == True
                )
            )
        ).order_by(AssessmentAssignment.available_from.desc())
        
        result = await db.execute(query)
        assignments = result.scalars().all()
        
        if not assignments:
            return []
        
        # Get assessment IDs from assignments
        assessment_ids = [assignment.assessment_id for assignment in assignments]
        
        # Get assessments
        assessment_query = select(Assessment).where(Assessment.id.in_(assessment_ids))
        assessment_result = await db.execute(assessment_query)
        assessments = assessment_result.scalars().all()
        
        # Create assessment ID to assignment mapping
        assignment_map = {assignment.assessment_id: assignment for assignment in assignments}
        
        # Build response
        response = []
        for assessment in assessments:
            assignment = assignment_map.get(assessment.id)
            if not assignment:
                continue
            
            response.append(StudentAssessmentAccessResponse(
                id=assignment.id,  # Return assignment ID for frontend reference
                title=assessment.title,
                description=assessment.description,
                subject=assessment.subject,
                class_name=assessment.class_name,
                assessment_type=assessment.assessment_type,
                total_points=assessment.total_points,
                available_from=assignment.available_from,
                available_until=assignment.available_until,
                time_limit_minutes=assignment.time_limit_minutes,
                show_results_timing=assignment.show_results_timing,
                instructions=assignment.instructions,
                created_at=assessment.created_at,
                updated_at=assessment.updated_at
            ))
        
        logger.debug(f"Returning {len(response)} assessments for course {subject}/{class_name}")
        return response
    except Exception as e:
        logger.error(f"Error getting student assessments for course {subject}/{class_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting assessments: {str(e)}")


@router.get("/student/assessments/{assignment_id}/detail", response_model=StudentAssessmentDetailResponse)
async def get_student_assessment_detail(
    current_student: Annotated[Student, Depends(get_current_student)],
    assignment_id: int,
    page: int = 1,
    page_size: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """Get full assessment details including questions, security settings, and instructions for student to answer with pagination support"""
    logger.info(f"Getting student assessment detail: assignment_id={assignment_id}, student_id={current_student.id}, page={page}, page_size={page_size}")
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
        
        # Get the assessment
        assessment_query = select(Assessment).where(Assessment.id == assignment.assessment_id)
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            logger.warning(f"Assessment details not found for assignment.assessment_id={assignment.assessment_id}")
            raise HTTPException(status_code=404, detail="Assessment details not found")
        
        # Get security settings
        security_query = select(SecuritySetting).where(SecuritySetting.assignment_id == assignment_id)
        security_result = await db.execute(security_query)
        security_setting = security_result.scalars().first()
        
        # Prepare security settings for response
        security_settings = {
            "strict_mode": security_setting.strict_mode if security_setting else False,
            "open_mode": security_setting.open_mode if security_setting else False,
            "free_mode": security_setting.free_mode if security_setting else False
        }
        
        # Get assessment questions
        aq_query = select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment.id).order_by(AssessmentQuestion.question_order)
        aq_result = await db.execute(aq_query)
        assessment_questions = aq_result.scalars().all()
        
        # info logging
        logger.info(f"Found {len(assessment_questions)} assessment questions for assessment_id={assessment.id}")
        for aq in assessment_questions:
            logger.info(f"  Question: id={aq.id}, assessment_id={aq.assessment_id}, question_id={aq.question_id}, section_id={aq.section_id}")
        
        # Get all unique question IDs
        question_ids = [aq.question_id for aq in assessment_questions]
        logger.info(f"Question IDs to fetch: {question_ids}")
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
        
        # Prepare assessment questions with question details (without answers/explanations)
        response_assessment_questions = []
        
        # Create a mapping of subquestion text to parent question ID for identifying embedded subquestions
        # We'll use a more specific approach to avoid false positives
        subquestion_to_parent = {}
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question and detail and detail.sub_questions:
                # For each subquestion in this question's sub_questions array, map its text to the parent question ID
                # Include the parent question ID in the mapping to be more specific
                for sub in detail.sub_questions:
                    if sub.get("question_text"):
                        # Create a unique key combining parent ID and question text to avoid false matches
                        key = f"{question.id}|{sub['question_text']}"
                        subquestion_to_parent[key] = question.id
        
        for aq in assessment_questions:
            question = question_map.get(aq.question_id)
            detail = detail_map.get(aq.question_id)
            
            if question:
                # Determine if this question is a subquestion based on its text matching a subquestion in another question
                # Use the more specific key to avoid false positives
                parent_id = None
                
                # Check if this question might be a subquestion by looking for exact matches
                # This is a simplified approach - in a real implementation, you might need a more robust way
                # to identify subquestions
                
                # Check if this question might be a subquestion by looking for exact matches
                # This is a simplified approach - in a real implementation, you might need a more robust way
                # to identify subquestions
                
                # Prepare question response (without answers/explanations)
                response_options = None
                if detail and detail.options:
                    response_options = [
                        StudentQuestionOption(
                            id=opt["id"],
                            text=opt["text"]
                            # Note: Not including is_correct to avoid exposing answers
                        )
                        for opt in detail.options
                    ]
                
                response_matching_pairs = None
                if detail and detail.matching_pairs:
                    response_matching_pairs = [
                        StudentMatchingPair(
                            id=pair["id"],
                            left=pair["left"],
                            right=pair["right"]
                            # Note: Not including correct matches to avoid exposing answers
                        )
                        for pair in detail.matching_pairs
                    ]
                
                response_sub_questions = None
                if detail and detail.sub_questions:
                    response_sub_questions = [
                        StudentSubQuestion(
                            id=sub["id"],
                            type=sub["type"],
                            question_text=sub["question_text"],
                            points=sub["points"]
                            # Note: Not including correct_answer, explanation, marking_guidelines
                        )
                        for sub in detail.sub_questions
                    ]
                
                question_response = StudentQuestionResponse(
                    id=question.id,
                    subject=question.subject,
                    class_name=question.class_name,
                    strand=question.strand,
                    topic=question.topic,
                    type=question.type,
                    question_text=question.question_text,
                    points=question.points,
                    created_at=question.created_at,
                    parent_id=parent_id,  # Set parent_id for subquestions
                    options=response_options,
                    matching_pairs=response_matching_pairs,
                    sub_questions=response_sub_questions
                )
                
                response_assessment_questions.append(StudentAssessmentQuestionResponse(
                    id=aq.id,
                    assessment_id=aq.assessment_id,
                    question_id=aq.question_id,
                    question_order=aq.question_order,
                    points=aq.points,
                    section_id=aq.section_id,
                    created_at=aq.created_at,
                    question=question_response
                ))
                
                logger.info(f"Added question to response: question_id={aq.question_id}, section_id={aq.section_id}")
        
        # Implement pagination logic
        # Group questions by sections to maintain proper section organization
        # First, get all sections and create a mapping
        section_query = select(AssessmentSection).where(AssessmentSection.assessment_id == assessment.id)
        section_result = await db.execute(section_query)
        sections = section_result.scalars().all()
        section_map = {section.id: section for section in sections}
        
        # Group questions by section
        sectioned_questions = {}
        unsectioned_questions = []
        
        for aq in response_assessment_questions:
            if aq.section_id and aq.section_id in section_map:
                if aq.section_id not in sectioned_questions:
                    sectioned_questions[aq.section_id] = []
                sectioned_questions[aq.section_id].append(aq)
            else:
                unsectioned_questions.append(aq)
        
        # Sort sectioned questions by section order and question order
        for section_id in sectioned_questions:
            sectioned_questions[section_id].sort(key=lambda x: x.question_order)
        
        # Sort sections by section_order
        sorted_section_ids = sorted(sectioned_questions.keys(), key=lambda x: section_map[x].section_order if x in section_map else 0)
        
        # Create a flat list of questions in the correct order (sections first, then unsectioned)
        ordered_questions = []
        for section_id in sorted_section_ids:
            ordered_questions.extend(sectioned_questions[section_id])
        ordered_questions.extend(unsectioned_questions)
        
        logger.info(f"Ordered questions count: {len(ordered_questions)}")
        for i, aq in enumerate(ordered_questions):
            logger.info(f"  Ordered question {i}: id={aq.question.id}, question_id={aq.question_id}, section_id={aq.section_id}, parent_id={aq.question.parent_id}")
        
        # Filter out subquestions for pagination calculation (only count main questions)
        main_questions = [aq for aq in ordered_questions if not aq.question.parent_id]
        
        logger.info(f"Main questions count: {len(main_questions)}")
        for i, aq in enumerate(main_questions):
            logger.info(f"  Main question {i}: id={aq.question.id}, question_id={aq.question_id}, section_id={aq.section_id}")
        
        # Calculate pagination based on the ordered list of main questions
        total_main_questions = len(main_questions)
        total_pages = (total_main_questions + page_size - 1) // page_size if page_size > 0 else 1
        
        # Paginate main questions
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_questions = main_questions[start_index:end_index]
        
        logger.info(f"Paginated questions count: {len(paginated_questions)}")
        for i, aq in enumerate(paginated_questions):
            logger.info(f"  Paginated question {i}: id={aq.question.id}, question_id={aq.question_id}, section_id={aq.section_id}")
        
        # Add pagination info to response
        pagination_info = {
            "current_page": page,
            "total_pages": total_pages,
            "total_questions": total_main_questions,
            "page_size": page_size
        }
        
        # info logging
        logger.info(f"Pagination info: {pagination_info}")
        logger.info(f"Total main questions: {total_main_questions}")
        logger.info(f"Total pages: {total_pages}")
        
        # Get sections for this assessment (moved here to use sections from above)
        response_sections = []
        for section in sections:
            response_sections.append(StudentAssessmentSectionResponse(
                id=section.id,
                name=section.name,
                section_order=section.section_order,
                description=section.description,
                created_at=section.created_at
            ))
        
        # Create response data dictionary to ensure all fields are included
        response_data = {
            "id": assignment.id,
            "title": assessment.title,
            "description": assessment.description,
            "subject": assessment.subject,
            "class_name": assessment.class_name,
            "assessment_type": assessment.assessment_type,
            "total_points": assessment.total_points,
            "teacher_id": str(assessment.teacher_id),
            "available_from": assignment.available_from,
            "available_until": assignment.available_until,
            "time_limit_minutes": assignment.time_limit_minutes,
            "show_results_timing": assignment.show_results_timing,
            "instructions": assignment.instructions,
            "security_settings": security_settings,
            "created_at": assessment.created_at,
            "updated_at": assessment.updated_at,
            "assessment_questions": paginated_questions,
            "sections": response_sections,
            "current_page": page,
            "total_pages": total_pages,
            "total_questions": total_main_questions,
            "page_size": page_size
        }
        
        # info logging to see what's in the response data
        logger.info(f"Response data. Current page: {response_data.get('current_page')}")
        logger.info(f"Response data. Total pages: {response_data.get('total_pages')}")
        logger.info(f"Response data. Total questions: {response_data.get('total_questions')}")
        logger.info(f"Response data. Page size: {response_data.get('page_size')}")
        
        response = StudentAssessmentDetailResponse(**response_data)
        
        # info logging to see what's actually in the response object
        logger.info(f"Response object created. Current page: {response.current_page}")
        logger.info(f"Response object created. Total pages: {response.total_pages}")
        logger.info(f"Response object created. Total questions: {response.total_questions}")
        logger.info(f"Response object created. Page size: {response.page_size}")
        
        # Log the response as a dictionary to see what will be serialized
        response_dict = response.dict()
        logger.info(f"Response dict keys: {list(response_dict.keys())}")
        logger.info(f"Response dict current_page: {response_dict.get('current_page')}")
        logger.info(f"Response dict total_pages: {response_dict.get('total_pages')}")
        logger.info(f"Response dict total_questions: {response_dict.get('total_questions')}")
        logger.info(f"Response dict page_size: {response_dict.get('page_size')}")
        
        logger.info(f"Returning assessment detail for assignment_id={assignment_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student assessment detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting assessment detail: {str(e)}")

@router.get("/student/assessments/{assignment_id}/initial-detail", response_model=StudentAssessmentInitialDetailResponse)
async def get_student_assessment_initial_detail(
    assignment_id: int,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get initial assessment details without questions for student preview"""
    logger.debug(f"Getting student assessment initial detail: assignment_id={assignment_id}, student_id={current_student.id}")
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
        
        # Get the assessment
        assessment_query = select(Assessment).where(Assessment.id == assignment.assessment_id)
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        if not assessment:
            logger.warning(f"Assessment details not found for assignment.assessment_id={assignment.assessment_id}")
            raise HTTPException(status_code=404, detail="Assessment details not found")
        
        # Get security settings
        security_query = select(SecuritySetting).where(SecuritySetting.assignment_id == assignment_id)
        security_result = await db.execute(security_query)
        security_setting = security_result.scalars().first()
        
        # Prepare security settings for response
        security_settings = {
            "strict_mode": security_setting.strict_mode if security_setting else False,
            "open_mode": security_setting.open_mode if security_setting else False,
            "free_mode": security_setting.free_mode if security_setting else False,
            "review": security_setting.review if security_setting else False
        }
        
        response = StudentAssessmentInitialDetailResponse(
            id=assignment.id,  # Return assignment ID for frontend reference
            title=assessment.title,
            description=assessment.description,
            subject=assessment.subject,
            class_name=assessment.class_name,
            assessment_type=assessment.assessment_type,
            total_points=assessment.total_points,
            available_from=assignment.available_from,
            available_until=assignment.available_until,
            time_limit_minutes=assignment.time_limit_minutes,
            show_results_timing=assignment.show_results_timing,
            instructions=assignment.instructions,
            teacher_id=str(assessment.teacher_id),
            security_settings=security_settings,
            created_at=assessment.created_at,
            updated_at=assessment.updated_at
        )
        
        logger.debug(f"Returning assessment initial detail for assignment_id={assignment_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student assessment initial detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting assessment initial detail: {str(e)}")
