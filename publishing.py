from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, select, Column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from schemas import AssessmentAssignmentResponse, CompositePublishingDataCreate, SecuritySettingCreateWithoutAssignment, StudentAccessRuleCreateWithoutAssignment, SurveillanceDataResponse
from model import TeacherProfile, Student, AssessmentAssignment, Assessment, SecuritySetting, StudentAccessRule, AssessmentQuestion, AssignmentStatus
from schemas import  AssessmentAssignmentUpdate, AssessmentAssignmentUpdateWithRelations, SecuritySettingResponse, StudentAccessRuleResponse
from dependencies import get_current_teacher
from database import get_db
from logger import logger
# Import the student WebSocket message function
from sch_ground.background import publish_student_ws_message

router = APIRouter(tags=["Publishing"])

def to_naive_datetime(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive datetime for database consistency"""
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone info
        return dt.astimezone().replace(tzinfo=None)
    return dt

@router.post("/create-publishing", response_model=AssessmentAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_publishing(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    publishing_data: CompositePublishingDataCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new assessment assignment with security settings and access rules in one operation"""
    logger.debug(f"Creating publishing: teacher_id={current_teacher.id}")
    
    # Keep track of student IDs for WebSocket notifications
    student_ids = []
    
    try:
        # Validate that the assessment exists and belongs to the teacher
        query = select(Assessment).where(
            Assessment.id == publishing_data.assignment_data.assessment_id,
            Assessment.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assessment = result.scalars().first()
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Update the assessment to be published
        assessment.is_published = True
        assessment.updated_at = datetime.utcnow()
        db.add(assessment)
        
        # Create the assignment
        # Ensure all datetime fields are timezone-naive for consistency
        available_from = to_naive_datetime(publishing_data.assignment_data.available_from)
        available_until = to_naive_datetime(publishing_data.assignment_data.available_until)
        
        # Also ensure other datetime fields are timezone-naive
        assigned_at = datetime.utcnow()
        created_at = datetime.utcnow()
        updated_at = datetime.utcnow()
        
        assignment = AssessmentAssignment(
            assessment_id=publishing_data.assignment_data.assessment_id,
            assigned_by_teacher_id=current_teacher.id,
            assigned_at=assigned_at,
            available_from=available_from,
            available_until=available_until,
            time_limit_minutes=publishing_data.assignment_data.time_limit_minutes,
            max_attempts=publishing_data.assignment_data.max_attempts,  # Added max_attempts
            is_active=publishing_data.assignment_data.is_active,
            show_results_timing=publishing_data.assignment_data.show_results_timing,
            instructions=publishing_data.assignment_data.instructions,  # Added instructions
            created_at=created_at,
            updated_at=updated_at
        )
        
        db.add(assignment)
        await db.flush()  # Flush to get the assignment ID
        
        # Create security settings
        security_setting_created_at = datetime.utcnow()
        security_setting_updated_at = datetime.utcnow()  # Added updated_at
        
        security_setting = SecuritySetting(
            assignment_id=assignment.id,
            strict_mode=publishing_data.security_settings.strict_mode,
            open_mode=publishing_data.security_settings.open_mode,
            free_mode=publishing_data.security_settings.free_mode,
            created_at=security_setting_created_at,
            updated_at=security_setting_updated_at
        )
        
        db.add(security_setting)
        
        # Create access rules and populate AssignmentStatus table
        for access_rule_data in publishing_data.access_rules:
            access_rule_created_at = datetime.utcnow()
            access_rule_updated_at = datetime.utcnow()  # Added updated_at
            
            access_rule = StudentAccessRule(
                assignment_id=assignment.id,
                student_id=access_rule_data.student_id,
                class_id=access_rule_data.class_id,
                can_access=access_rule_data.can_access,
                created_at=access_rule_created_at,
                updated_at=access_rule_updated_at,
                access_granted_at=datetime.utcnow()
            )
            db.add(access_rule)
            
            # Add student ID to the list for WebSocket notifications (only if it's an individual student)
            if access_rule_data.student_id:
                student_ids.append(access_rule_data.student_id)
            # For class-wide assignments, we'll find all students in the class later
            
            # Create AssignmentStatus entry for each student with is_completed = False
            if access_rule_data.student_id:
                # Get student name
                student_query = select(Student).where(Student.id == access_rule_data.student_id)
                student_result = await db.execute(student_query)
                student = student_result.scalars().first()
                
                if student:
                    assignment_status = AssignmentStatus(
                        student_name=student.name,
                        student_id=access_rule_data.student_id,
                        assignment_id=assignment.id,
                        is_completed=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(assignment_status)
        
        # Handle class-wide assignments: find all students in the classes and add them to WebSocket notifications
        # For now, we'll use a simplified approach - in a real implementation, you might need a more complex query
        # to find students based on class_id or other criteria
        # Since we don't have a direct mapping of class_id to students, we'll use the assessment's class_name
        # to find all students in that class
        
        # Get all students in the assessment's class
        students_in_class_query = select(Student).where(
            Student.class_name == assessment.class_name,
            Student.teacher_id == current_teacher.id,
            Student.is_active == True
        )
        students_in_class_result = await db.execute(students_in_class_query)
        students_in_class = students_in_class_result.scalars().all()
        
        # Add these students to the WebSocket notification list (avoiding duplicates)
        for student in students_in_class:
            if student.id not in student_ids:
                student_ids.append(student.id)
        
        # Commit the transaction
        await db.commit()
        
        # Refresh objects to get updated data
        await db.refresh(assessment)
        await db.refresh(assignment)
        
        # Send WebSocket notifications to students
        if student_ids:
            websocket_message = {
                "type": "PUBLISHED_ASSESSMENT",
                "assignment_id": assignment.id,
                "assessment_id": assessment.id,
                "title": assessment.title,
                "subject": assessment.subject,
                "class_name": assessment.class_name,
                "available_from": assignment.available_from.isoformat(),
                "available_until": assignment.available_until.isoformat(),
                "assigned_at": assignment.assigned_at.isoformat(),
                "time_limit_minutes": assignment.time_limit_minutes,
                "max_attempts": assignment.max_attempts,  # Added max_attempts
                "message": f"New assessment '{assessment.title}' has been published for {assessment.subject}"
            }
            
            # Send WebSocket message to each student
            for student_id in student_ids:
                try:
                    await publish_student_ws_message(str(student_id), websocket_message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
        
        logger.debug(f"Successfully created publishing: assessment_id={publishing_data.assignment_data.assessment_id}, assignment_id={assignment.id}")
        
        return AssessmentAssignmentResponse(
            id=assignment.id,
            assessment_id=assignment.assessment_id,
            assigned_by_teacher_id=assignment.assigned_by_teacher_id,
            assigned_at=assignment.assigned_at,
            available_from=assignment.available_from,
            available_until=assignment.available_until,
            time_limit_minutes=assignment.time_limit_minutes,
            max_attempts=assignment.max_attempts,  # Added max_attempts
            is_active=assignment.is_active,
            show_results_timing=assignment.show_results_timing,
            instructions=assignment.instructions,  # Added instructions
            created_at=assignment.created_at,
            updated_at=assignment.updated_at
        )
    except HTTPException:
        # Rollback the transaction
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error creating publishing: {str(e)}")
        # Rollback the transaction
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating publishing: {str(e)}")


# Add new endpoints to the router
@router.delete("/delete-assignment-cascade/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment_cascade(
    assignment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Hard delete an assessment assignment and all related data (cascade delete)"""
    logger.debug(f"Deleting assignment cascade: assignment_id={assignment_id}, teacher_id={current_teacher.id}")
    
    try:
        # First, verify that the assignment exists and belongs to the teacher
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.assigned_by_teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assignment = result.scalars().first()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found or not authorized")
        
        # Get the associated assessment
        assessment_query = select(Assessment).where(Assessment.id == assignment.assessment_id)
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        # Get student IDs who had access to this assignment before deleting access rules
        student_ids = []
        access_rules_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id
        )
        access_rules_result = await db.execute(access_rules_query)
        access_rules = access_rules_result.scalars().all()
        for access_rule in access_rules:
            if access_rule.student_id:
                student_ids.append(str(access_rule.student_id))
        
        # Delete all related data in the correct order
        # 1. Delete AssignmentStatus entries
        delete_assignment_status_query = select(AssignmentStatus).where(
            AssignmentStatus.assignment_id == assignment_id
        )
        assignment_status_result = await db.execute(delete_assignment_status_query)
        assignment_statuses = assignment_status_result.scalars().all()
        for assignment_status in assignment_statuses:
            await db.delete(assignment_status)
        
        # 2. Delete access rules
        delete_access_rules_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id
        )
        access_rules_result = await db.execute(delete_access_rules_query)
        access_rules = access_rules_result.scalars().all()
        for access_rule in access_rules:
            await db.delete(access_rule)
        
        # 3. Delete security settings
        delete_security_settings_query = select(SecuritySetting).where(
            SecuritySetting.assignment_id == assignment_id
        )
        security_settings_result = await db.execute(delete_security_settings_query)
        security_settings = security_settings_result.scalars().all()
        for security_setting in security_settings:
            await db.delete(security_setting)
        
        # 4. Delete the assignment itself
        await db.delete(assignment)
        
        # 5. Update the assessment to be unpublished
        if assessment:
            assessment.is_published = False
            assessment.updated_at = datetime.utcnow()
            db.add(assessment)
        
        # Commit all deletions
        await db.commit()
        
        # Send WebSocket notifications to students who had access to this assignment
        if student_ids and assessment:
            websocket_message = {
                "type": "DELETED_PUBLISHING",
                "assignment_id": assignment_id,
                "assessment_id": assessment.id,
                "title": assessment.title,
                "subject": assessment.subject,
                "class_name": assessment.class_name,
                "message": f"Assessment '{assessment.title}' has been deleted"
            }
            
            # Send WebSocket message to each student
            for student_id in student_ids:
                try:
                    await publish_student_ws_message(student_id, websocket_message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message to student {student_id}: {str(e)}")
        
        logger.debug(f"Successfully deleted assignment cascade: assignment_id={assignment_id}")
        return None
    except HTTPException:
        # Rollback the transaction
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error deleting assignment cascade: {str(e)}")
        # Rollback the transaction
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting assignment cascade: {str(e)}")


@router.put("/update-assignment-with-relations/{assignment_id}", response_model=AssessmentAssignmentResponse)
async def update_assignment_with_relations(
    assignment_id: int,
    update_data: AssessmentAssignmentUpdateWithRelations,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Update an assessment assignment and its related security settings and access rules"""
    logger.debug(f"Updating assignment with relations: assignment_id={assignment_id}, teacher_id={current_teacher.id}")
    
    try:
        # First, verify that the assignment exists and belongs to the teacher
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.assigned_by_teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assignment = result.scalars().first()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found or not authorized")
        
        # Update assignment data if provided
        if update_data.assignment_data:
            update_fields = update_data.assignment_data.dict(exclude_unset=True)
            for field, value in update_fields.items():
                if value is not None:
                    # Ensure datetime fields are timezone-naive
                    if isinstance(value, datetime):
                        value = to_naive_datetime(value)
                    setattr(assignment, field, value)
            
            assignment.updated_at = datetime.utcnow()
            db.add(assignment)
        
        # Update security settings if provided
        if update_data.security_settings:
            # Get existing security settings
            security_query = select(SecuritySetting).where(
                SecuritySetting.assignment_id == assignment_id
            )
            security_result = await db.execute(security_query)
            security_setting = security_result.scalars().first()
            
            if security_setting:
                update_fields = update_data.security_settings.dict(exclude_unset=True)
                for field, value in update_fields.items():
                    if value is not None:
                        setattr(security_setting, field, value)
                
                security_setting.updated_at = datetime.utcnow()
                db.add(security_setting)
        
        # Update or add access rules if provided
        if update_data.access_rules is not None:
            # Delete existing AssignmentStatus entries
            delete_assignment_status_query = select(AssignmentStatus).where(
                AssignmentStatus.assignment_id == assignment_id
            )
            assignment_status_result = await db.execute(delete_assignment_status_query)
            existing_assignment_statuses = assignment_status_result.scalars().all()
            for assignment_status in existing_assignment_statuses:
                await db.delete(assignment_status)
            
            # Delete existing access rules
            delete_query = select(StudentAccessRule).where(
                StudentAccessRule.assignment_id == assignment_id
            )
            delete_result = await db.execute(delete_query)
            existing_rules = delete_result.scalars().all()
            for rule in existing_rules:
                await db.delete(rule)
            
            # Add new access rules and create new AssignmentStatus entries
            for access_rule_data in update_data.access_rules:
                access_rule = StudentAccessRule(
                    assignment_id=assignment_id,
                    student_id=access_rule_data.student_id,
                    class_id=access_rule_data.class_id,
                    can_access=access_rule_data.can_access,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    access_granted_at=datetime.utcnow()
                )
                db.add(access_rule)
                
                # Create AssignmentStatus entry for each student with is_completed = False
                if access_rule_data.student_id:
                    # Get student name
                    student_query = select(Student).where(Student.id == access_rule_data.student_id)
                    student_result = await db.execute(student_query)
                    student = student_result.scalars().first()
                    
                    if student:
                        assignment_status = AssignmentStatus(
                            student_name=student.name,
                            student_id=access_rule_data.student_id,
                            assignment_id=assignment_id,
                            is_completed=False,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(assignment_status)
        
        # Commit the transaction
        await db.commit()
        
        # Refresh objects to get updated data
        await db.refresh(assignment)
        
        logger.debug(f"Successfully updated assignment with relations: assignment_id={assignment_id}")
        
        return AssessmentAssignmentResponse(
            id=assignment.id,
            assessment_id=assignment.assessment_id,
            assigned_by_teacher_id=assignment.assigned_by_teacher_id,
            assigned_at=assignment.assigned_at,
            available_from=assignment.available_from,
            available_until=assignment.available_until,
            time_limit_minutes=assignment.time_limit_minutes,
            is_active=assignment.is_active,
            show_results_timing=assignment.show_results_timing,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at
        )
    except HTTPException:
        # Rollback the transaction
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error updating assignment with relations: {str(e)}")
        # Rollback the transaction
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating assignment with relations: {str(e)}")


@router.get("/read-assignment-with-relations/{assignment_id}", response_model=dict)
async def read_assignment_with_relations(
    assignment_id: int,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """Get an assessment assignment with its related security settings and access rules"""
    logger.debug(f"Reading assignment with relations: assignment_id={assignment_id}, teacher_id={current_teacher.id}")
    
    try:
        # First, verify that the assignment exists and belongs to the teacher
        query = select(AssessmentAssignment).where(
            AssessmentAssignment.id == assignment_id,
            AssessmentAssignment.assigned_by_teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        assignment = result.scalars().first()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found or not authorized")
        
        # Get security settings
        security_query = select(SecuritySetting).where(
            SecuritySetting.assignment_id == assignment_id
        )
        security_result = await db.execute(security_query)
        security_setting = security_result.scalars().first()
        
        # Get access rules
        access_rules_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id
        )
        access_rules_result = await db.execute(access_rules_query)
        access_rules = access_rules_result.scalars().all()
        
        # Return the combined data
        response_data = {
            "assignment": AssessmentAssignmentResponse(
                id=assignment.id,
                assessment_id=assignment.assessment_id,
                assigned_by_teacher_id=assignment.assigned_by_teacher_id,
                assigned_at=assignment.assigned_at,
                available_from=assignment.available_from,
                available_until=assignment.available_until,
                time_limit_minutes=assignment.time_limit_minutes,
                is_active=assignment.is_active,
                show_results_timing=assignment.show_results_timing,
                created_at=assignment.created_at,
                updated_at=assignment.updated_at
            ),
            "security_settings": SecuritySettingResponse(
                id=security_setting.id,
                assignment_id=security_setting.assignment_id,
                strict_mode=security_setting.strict_mode,
                open_mode=security_setting.open_mode,
                free_mode=security_setting.free_mode,
                created_at=security_setting.created_at,
                updated_at=security_setting.updated_at
            ) if security_setting else None,
            "access_rules": [
                StudentAccessRuleResponse(
                    id=rule.id,
                    assignment_id=rule.assignment_id,
                    student_id=rule.student_id,
                    class_id=rule.class_id,
                    can_access=rule.can_access,
                    access_granted_at=rule.access_granted_at,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at
                ) for rule in access_rules
            ]
        }
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading assignment with relations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading assignment with relations: {str(e)}")


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
            
            # Only include assessments that have an assignment (published with assignment)
            if not assignment:
                continue
                
            # Get question count through a separate query instead of accessing relationship directly
            question_count_query = select(func.count(AssessmentQuestion.id)).where(
                AssessmentQuestion.assessment_id == assessment.id
            )
            question_count_result = await db.execute(question_count_query)
            question_count = question_count_result.scalar_one()
            
            # Transform to response format
            surveillance_item = SurveillanceDataResponse(
                id=assignment.id,
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
