from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List, Optional
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
import uuid
from model import Student, StudentEnrollment, SecuritySetting
from dependencies import get_current_student
from database import get_db
from logger import logger
from model import AssessmentAssignment, StudentAccessRule
from model import Assessment, Question, QuestionDetail, AssessmentQuestion, AssessmentSection, AssignmentStatus
from schemas import AssessmentCountResponse ,StudentAvailableAssessmentResponse, StudentAssessmentResponse, StudentEnrollmentResponse, StudentSubQuestion, DashboardDailyChallengeResponse
from schemas import StudentAssessmentQuestionResponse, StudentQuestionResponse, StudentAssignedAssessmentResponse, StudentAssessmentSectionResponse, StudentQuestionOption

router = APIRouter(tags=["Student Assessment Reader"])

async def get_student_accessible_assignments(db: AsyncSession, student_id: UUID, subject: Optional[str] = None, class_name: Optional[str] = None):
    """Get assignments that a student has access to"""
    # Get student enrollments (simplified - in real implementation would join with enrollment table)
    query = select(AssessmentAssignment).join(StudentAccessRule)
    
    # Add the base conditions
    conditions = [
        StudentAccessRule.student_id == student_id,
        StudentAccessRule.can_access == True,
        AssessmentAssignment.is_active == True,
        AssessmentAssignment.available_from <= datetime.utcnow(),
        AssessmentAssignment.available_until >= datetime.utcnow()
    ]
    
    # Add subject and class_name filters with a single join to Assessment
    if subject or class_name:
        query = query.join(Assessment)
        if subject:
            conditions.append(Assessment.subject == subject)
        if class_name:
            conditions.append(Assessment.class_name == class_name)
    
    query = query.where(*conditions)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_daily_challenge_assignments(db: AsyncSession, student_id: UUID):
    """Get assignments for daily challenges (recently published assessments)"""
    # Get assignments that are active and recently published (last 24 hours)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    query = select(AssessmentAssignment).join(StudentAccessRule).where(
        StudentAccessRule.student_id == student_id,
        StudentAccessRule.can_access == True,
        AssessmentAssignment.is_active == True,
        AssessmentAssignment.available_from <= datetime.utcnow(),
        AssessmentAssignment.available_until >= datetime.utcnow(),
        AssessmentAssignment.assigned_at >= twenty_four_hours_ago
    )
    
    result = await db.execute(query)
    return result.scalars().all()

def filter_question_for_student(question_detail: QuestionDetail) -> dict:
    """Filter question details to exclude sensitive information"""
    filtered_data = {
        "options": question_detail.options,
        "matching_pairs": question_detail.matching_pairs,
        "sub_questions": question_detail.sub_questions
    }
    
    # Remove sensitive information from sub_questions
    if filtered_data["sub_questions"]:
        for sub_q in filtered_data["sub_questions"]:
            sub_q.pop("correct_answer", None)
            sub_q.pop("explanation", None)
            sub_q.pop("marking_guidelines", None)
    
    # For matching questions, only show left side to students
    if filtered_data["matching_pairs"]:
        for pair in filtered_data["matching_pairs"]:
            pair.pop("right", None)  # Remove the right side (answers)
    
    # Remove correct answers from options
    if filtered_data["options"]:
        for option in filtered_data["options"]:
            option.pop("is_correct", None)
    
    return filtered_data


# IMPORTANT: The count endpoint must be defined BEFORE the assignment_id endpoint to avoid routing conflicts
@router.get("/assessment-counts", response_model=AssessmentCountResponse)
async def get_assessment_counts(
    current_student: Annotated[Student, Depends(get_current_student)],
    db: AsyncSession = Depends(get_db)
):
    """Get assessment counts for dashboard tiles:
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
        # Get all assessments student has access to
        access_query = select(AssessmentAssignment).where(
            AssessmentAssignment.id.in_(
                select(StudentAccessRule.assignment_id).where(
                    StudentAccessRule.student_id == current_student.id,
                    StudentAccessRule.can_access == True
                )
            )
        )
        
        access_result = await db.execute(access_query)
        assignments = access_result.scalars().all()
        assessment_ids = [assignment.assessment_id for assignment in assignments]
        
        enrolled_courses = 0
        if assessment_ids:
            # Get distinct subject/class combinations
            course_query = select(func.count(func.distinct(func.concat(Assessment.subject, '|', Assessment.class_name)))).where(
                Assessment.id.in_(assessment_ids)
            )
            
            course_result = await db.execute(course_query)
            enrolled_courses = course_result.scalar_one()
        
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