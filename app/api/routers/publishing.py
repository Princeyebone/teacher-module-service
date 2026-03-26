from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, select, Column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime
import uuid
from app.schemas.schemas import AssessmentAssignmentResponse, CompositePublishingDataCreate, SecuritySettingCreateWithoutAssignment, StudentAccessRuleCreateWithoutAssignment, SurveillanceDataResponse
from app.models.model import TeacherProfile, Student, AssessmentAssignment, Assessment, SecuritySetting, StudentAccessRule, AssessmentQuestion, AssignmentStatus, StudentEnrollment
from app.schemas.schemas import  AssessmentAssignmentUpdate, AssessmentAssignmentUpdateWithRelations, SecuritySettingResponse, StudentAccessRuleResponse
from app.core.dependencies import get_current_teacher
from app.core.database import get_db
from app.core.logger import logger
# Import the student WebSocket message function
from app.sch_ground.background import publish_student_ws_message

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
        
        logger.debug(f"Found assessment: id={assessment.id}, subject={getattr(assessment, 'subject', 'N/A')}, class_name={getattr(assessment, 'class_name', 'N/A')}")
        
        # Update the assessment to be published
        assessment.is_published = True
        # Ensure we have all required fields from publishing_data for the assessment
        if publishing_data.assignment_data:
            # Update only the specified fields from publishing_data.assignment_data
            update_data = publishing_data.assignment_data.dict(exclude_unset=True)
            for key, value in update_data.items():
                if key in ["title", "description", "subject", "class_name", "assessment_type", "total_points"]:
                    setattr(assessment, key, value)
        
        # Update the assessment's updated_at timestamp
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
        
        # Get subject and class_name from assessment with proper error handling
        assessment_subject = getattr(assessment, 'subject', 'Not specified')
        assessment_class_name = getattr(assessment, 'class_name', 'Not specified')
        
        # Handle time limit based on security mode
        time_limit_minutes = publishing_data.assignment_data.time_limit_minutes
        # If free mode is enabled, set time limit to None
        # Handle both object and dict representations
        free_mode_enabled = False
        if hasattr(publishing_data.security_settings, 'free_mode'):
            free_mode_enabled = publishing_data.security_settings.free_mode
        elif isinstance(publishing_data.security_settings, dict):
            free_mode_enabled = publishing_data.security_settings.get('free_mode', False)
        
        if free_mode_enabled:
            time_limit_minutes = None
        
        logger.debug(f"Creating assignment with subject={assessment_subject}, class_name={assessment_class_name}")
        
        assignment = AssessmentAssignment(
            assessment_id=publishing_data.assignment_data.assessment_id,
            assigned_by_teacher_id=current_teacher.id,
            assigned_at=assigned_at,
            available_from=available_from,
            available_until=available_until,
            time_limit_minutes=time_limit_minutes,
            max_attempts=publishing_data.assignment_data.max_attempts,  # Added max_attempts
            is_active=publishing_data.assignment_data.is_active,
            show_results_timing=publishing_data.assignment_data.show_results_timing,
            instructions=publishing_data.assignment_data.instructions,  # Added instructions
            created_at=created_at,
            updated_at=updated_at,
            subject=assessment_subject,
            class_name=assessment_class_name
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
            review=publishing_data.security_settings.review,  # Added review field
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
        # Since we don't have a direct mapping of class_id to students, we'll use the assignment's class_name
        # to find all students in that class through the StudentEnrollment table
        
        # Get all students in the assignment's class through StudentEnrollment
        students_in_class_query = select(Student).join(StudentEnrollment).where(
            StudentEnrollment.class_name == assignment.class_name,
            StudentEnrollment.teacher_id == assignment.assigned_by_teacher_id,
            StudentEnrollment.is_active == True,
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
                "subject": assignment.subject,
                "class_name": assignment.class_name,
                "available_from": assignment.available_from.isoformat(),
                "available_until": assignment.available_until.isoformat(),
                "assigned_at": assignment.assigned_at.isoformat(),
                "time_limit_minutes": assignment.time_limit_minutes,
                "max_attempts": assignment.max_attempts,  # Added max_attempts
                "message": f"New assessment '{assessment.title}' has been published for {assignment.subject}",
                # Add the new fields to the WebSocket message
                "subject": assignment.subject,
                "class_name": assignment.class_name
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
            updated_at=assignment.updated_at,
            # Include the new fields in the response
            subject=assignment.subject,
            class_name=assignment.class_name
        )
    except HTTPException:
        # Rollback the transaction
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error creating publishing: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        # 1. Delete SurveillanceLog entries
        from app.models.model import StudentSubmission, SubmissionAnswer, SurveillanceLog
        
        delete_surveillance_logs_query = select(SurveillanceLog).where(
            SurveillanceLog.assignment_id == assignment_id
        )
        surveillance_logs_result = await db.execute(delete_surveillance_logs_query)
        surveillance_logs = surveillance_logs_result.scalars().all()
        for log in surveillance_logs:
            await db.delete(log)
        await db.flush()  # Explicitly flush after deleting surveillance logs
        
        # 2. Delete SubmissionAnswer entries and StudentSubmission entries
        # Get all submissions for this assignment
        submissions_query = select(StudentSubmission).where(
            StudentSubmission.assignment_id == assignment_id
        )
        submissions_result = await db.execute(submissions_query)
        submissions = submissions_result.scalars().all()
        
        # For each submission, delete all related submission answers first, then the submission itself
        for submission in submissions:
            # Delete all submission answers for this submission
            submission_answers_query = select(SubmissionAnswer).where(
                SubmissionAnswer.submission_id == submission.id
            )
            submission_answers_result = await db.execute(submission_answers_query)
            submission_answers = submission_answers_result.scalars().all()
            
            for answer in submission_answers:
                await db.delete(answer)
            await db.flush()  # Explicitly flush after deleting submission answers
            
            # Now delete the submission itself
            await db.delete(submission)
            await db.flush()  # Explicitly flush after deleting submission
        
        # 3. Delete AssignmentStatus entries
        delete_assignment_status_query = select(AssignmentStatus).where(
            AssignmentStatus.assignment_id == assignment_id
        )
        assignment_status_result = await db.execute(delete_assignment_status_query)
        assignment_statuses = assignment_status_result.scalars().all()
        for assignment_status in assignment_statuses:
            await db.delete(assignment_status)
        await db.flush()  # Explicitly flush after deleting assignment statuses
        
        # 4. Delete access rules
        delete_access_rules_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id
        )
        access_rules_result = await db.execute(delete_access_rules_query)
        access_rules = access_rules_result.scalars().all()
        for access_rule in access_rules:
            await db.delete(access_rule)
        await db.flush()  # Explicitly flush after deleting access rules
        
        # 5. Delete security settings
        delete_security_settings_query = select(SecuritySetting).where(
            SecuritySetting.assignment_id == assignment_id
        )
        security_settings_result = await db.execute(delete_security_settings_query)
        security_settings = security_settings_result.scalars().all()
        for security_setting in security_settings:
            await db.delete(security_setting)
        await db.flush()  # Explicitly flush after deleting security settings
        
        # 6. Delete the assignment itself
        await db.delete(assignment)
        await db.flush()  # Explicitly flush after deleting assignment
        
        # 7. Update the assessment to be unpublished
        if assessment:
            assessment.is_published = False
            assessment.updated_at = datetime.utcnow()
            db.add(assessment)
            await db.flush()  # Explicitly flush after updating assessment
        
        # Commit all deletions
        await db.commit()
        
        # Send WebSocket notifications to students who had access to this assignment
        if student_ids and assessment:
            websocket_message = {
                "type": "DELETED_PUBLISHING",
                "assignment_id": assignment_id,
                "assessment_id": assessment.id,
                "title": assessment.title,
                "subject": assignment.subject,
                "class_name": assignment.class_name,
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
            # Get current security settings to check free_mode status
            security_query = select(SecuritySetting).where(
                SecuritySetting.assignment_id == assignment_id
            )
            security_result = await db.execute(security_query)
            security_setting = security_result.scalars().first()
            
            # Check if we're in free mode before updating time_limit_minutes
            is_free_mode = False
            if security_setting:
                is_free_mode = security_setting.free_mode
            
            # Check if security settings are also being updated in this request
            security_update_fields = {}
            if update_data.security_settings:
                # Handle both object and dict representations
                if hasattr(update_data.security_settings, 'dict'):
                    security_update_fields = update_data.security_settings.dict(exclude_unset=True)
                else:
                    security_update_fields = update_data.security_settings
                
                # Ensure update_fields is a dictionary
                if not isinstance(security_update_fields, dict):
                    security_update_fields = {}
            
            for field, value in update_fields.items():
                # Special handling for time_limit_minutes when security settings are also being updated
                if field == 'time_limit_minutes' and update_data.security_settings:
                    new_free_mode = security_update_fields.get('free_mode')
                    # If free_mode is being set to True, ignore time_limit_minutes
                    if new_free_mode is True:
                        continue
                    # If we're switching from free mode to another mode, allow time_limit_minutes to be set
                    elif is_free_mode and new_free_mode is False:
                        setattr(assignment, field, value)
                    # If we're in free mode and not explicitly switching to another mode, ignore time_limit_minutes
                    elif is_free_mode and new_free_mode is not False and value is not None:
                        continue
                    else:
                        # Normal case - set the value
                        setattr(assignment, field, value)
                else:
                    # For all other fields, or if security settings are not being updated
                    # If we're in free mode and trying to set time_limit_minutes, ignore it unless it's None
                    if field == 'time_limit_minutes' and is_free_mode and value is not None:
                        continue  # Skip setting time_limit_minutes in free mode (unless it's None)
                    # Ensure datetime fields are timezone-naive
                    if isinstance(value, datetime):
                        value = to_naive_datetime(value)
                    setattr(assignment, field, value)
            
            assignment.updated_at = datetime.utcnow()
            db.add(assignment)
        
        # Update security settings if provided
        if update_data.security_settings:
            # Get existing security settings (again, in case they were not retrieved above)
            if security_setting is None:
                security_query = select(SecuritySetting).where(
                    SecuritySetting.assignment_id == assignment_id
                )
                security_result = await db.execute(security_query)
                security_setting = security_result.scalars().first()
            
            if security_setting:
                # Handle both object and dict representations
                if hasattr(update_data.security_settings, 'dict'):
                    update_fields = update_data.security_settings.dict(exclude_unset=True)
                else:
                    update_fields = update_data.security_settings
                
                # Ensure update_fields is a dictionary
                if not isinstance(update_fields, dict):
                    update_fields = {}
                
                original_free_mode = security_setting.free_mode
                
                for field, value in update_fields.items():
                    if value is not None:
                        setattr(security_setting, field, value)
                
                # Check if free_mode has changed to True and clear time limit if so
                # Handle the case where free_mode might be None (not provided in the update)
                new_free_mode = update_fields.get('free_mode')
                if new_free_mode is True and original_free_mode is False:
                    assignment.time_limit_minutes = None
                    db.add(assignment)
                # If we're switching from free mode to another mode and time_limit_minutes is being explicitly set,
                # update the time limit with the submitted value
                elif original_free_mode is True and new_free_mode is False and 'time_limit_minutes' in update_fields:
                    # In this case, we're switching from free mode to another mode and explicitly setting time_limit_minutes
                    assignment.time_limit_minutes = update_fields['time_limit_minutes']
                    db.add(assignment)
                # If we're switching from free mode to another mode and time_limit_minutes is not being explicitly set,
                # we might want to set a default value or leave it as None
                elif original_free_mode is True and new_free_mode is False and 'time_limit_minutes' not in update_fields:
                    # In this case, we're switching from free mode to another mode but not explicitly setting time_limit_minutes
                    # We'll leave it as None and let the frontend handle setting a value
                    pass
                # If free_mode is being explicitly set to True, clear time limit regardless of previous state
                elif new_free_mode is True:
                    assignment.time_limit_minutes = None
                    db.add(assignment)
                
                security_setting.updated_at = datetime.utcnow()
                db.add(security_setting)
        
        # If both assignment data and security settings are being updated, we need to handle the coordination
        # between time_limit_minutes in assignment data and free_mode in security settings
        if update_data.assignment_data and update_data.security_settings:
            # Get the update fields for both
            assignment_update_fields = update_data.assignment_data.dict(exclude_unset=True)
            security_update_fields = {}
            if hasattr(update_data.security_settings, 'dict'):
                security_update_fields = update_data.security_settings.dict(exclude_unset=True)
            else:
                security_update_fields = update_data.security_settings
            
            # Ensure security_update_fields is a dictionary
            if not isinstance(security_update_fields, dict):
                security_update_fields = {}
            
            # If time_limit_minutes is being set in assignment data and free_mode is being changed,
            # we need to handle this coordination
            if 'time_limit_minutes' in assignment_update_fields and 'free_mode' in security_update_fields:
                time_limit_value = assignment_update_fields['time_limit_minutes']
                new_free_mode = security_update_fields['free_mode']
                original_free_mode = security_setting.free_mode if security_setting else False
                
                # If free_mode is being set to True, clear time_limit_minutes
                if new_free_mode is True:
                    assignment.time_limit_minutes = None
                    db.add(assignment)
                # If we're switching from free mode to another mode, set the time_limit_minutes
                elif original_free_mode is True and new_free_mode is False:
                    assignment.time_limit_minutes = time_limit_value
                    db.add(assignment)
        
        # Commit the transaction
        await db.commit()
        
        # Refresh objects to get updated data
        await db.refresh(assignment)
        # Also refresh security settings to get updated values
        if security_setting:
            await db.refresh(security_setting)
        
        # Get the associated assessment for WebSocket notification
        assessment_query = select(Assessment).where(Assessment.id == assignment.assessment_id)
        assessment_result = await db.execute(assessment_query)
        assessment = assessment_result.scalars().first()
        
        # Get student IDs who have access to this assignment
        student_ids = []
        access_rules_query = select(StudentAccessRule).where(
            StudentAccessRule.assignment_id == assignment_id
        )
        access_rules_result = await db.execute(access_rules_query)
        access_rules = access_rules_result.scalars().all()
        for access_rule in access_rules:
            if access_rule.student_id:
                student_ids.append(str(access_rule.student_id))
        
        # Send WebSocket notifications to students who have access to this assignment
        if student_ids and assessment:
            websocket_message = {
                "type": "UPDATE_PUBLISHING",
                "assignment_id": assignment_id,
                "assessment_id": assessment.id,
                "title": assessment.title,
                "subject": assignment.subject,
                "class_name": assignment.class_name,
                "available_from": assignment.available_from.isoformat(),
                "available_until": assignment.available_until.isoformat(),
                "assigned_at": assignment.assigned_at.isoformat(),
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
            updated_at=assignment.updated_at,
            subject=assignment.subject,
            class_name=assignment.class_name
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
                updated_at=assignment.updated_at,
                subject=assignment.subject,
                class_name=assignment.class_name
            ),
            "security_settings": SecuritySettingResponse(
                id=security_setting.id,
                assignment_id=security_setting.assignment_id,
                strict_mode=security_setting.strict_mode,
                open_mode=security_setting.open_mode,
                free_mode=security_setting.free_mode,
                review=security_setting.review,  # Added review field
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
    class_name: Optional[str] = None,
    subject: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all publishing data for surveillance dashboard"""
    logger.error(f"Reading all publishing data: teacher_id={current_teacher.id}, class_name={class_name}, subject={subject}")
    try:
        # Query for all published assessments belonging to this teacher
        # Use join to eagerly load assessment_questions to avoid lazy loading issues
        query = select(Assessment).where(
            Assessment.teacher_id == current_teacher.id,
            Assessment.is_published == True
        )
        
        # Add filters for class_name and subject if provided
        if class_name:
            query = query.where(Assessment.class_name == class_name)
        if subject:
            query = query.where(Assessment.subject == subject)
            
        query = query.order_by(Assessment.created_at.desc())
        
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
                subject=assignment.subject,  # Use assignment.subject instead of assessment.subject
                class_name=assignment.class_name,  # Use assignment.class_name instead of assessment.class_name
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
