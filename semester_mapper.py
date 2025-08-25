from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Dict
from pydantic import BaseModel, Field
from model import TeacherProfile, AcademicCalendar, ClassSession, Strand, Substrand, ContentStandard, Indicator
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import select, delete, Field
import uuid
from uuid import UUID
from typing import List
from fastapi import HTTPException
from datetime import timedelta, date
from schemas import StrandCreate, StrandResponse, SessionDetail, StrandUpdate, SubstrandResponse, SubstrandCreate 
from schemas import ContentStandardCreate, ContentStandardUpdate, ContentStandardResponse ,SubstrandUpdate
from schemas import IndicatorCreate, IndicatorUpdate, IndicatorResponse
from datetime import datetime
from logger import logger


router = APIRouter(tags=["Semester Mapper"])

@router.get("/class-sessions-in-week")
async def get_class_sessions_in_week(
    week_duration: str,
    subject: str,
    class_name: str,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Fetching class sessions for teacher_id: {current_teacher.id}, week_duration: {week_duration}, subject: {subject}, class_name: {class_name}")
    try:
        acc = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        if not acc:
            logger.error("Academic calendar not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Academic calendar not found for this teacher"
            )

        acc_start_date = acc.semester_start_date
        acc_end_date = acc.semester_end_date
        logger.debug(f"Academic calendar: start_date={acc_start_date}, end_date={acc_end_date}")

        try:
            start_week, end_week = map(int, week_duration.lower().replace("week", "").split("-"))
        except ValueError:
            logger.error(f"Invalid week_duration format: {week_duration}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid week duration format. Use 'weekX-weekY'."
            )

        start_date = acc_start_date + timedelta(weeks=start_week - 1)
        end_date = acc_start_date + timedelta(weeks=end_week)
        logger.debug(f"Calculated date range: start_date={start_date}, end_date={end_date}")

        subject = subject.strip()
        class_name = class_name.strip()

        class_sessions = (await db.execute(
            select(ClassSession).where(
                (ClassSession.date >= start_date) &
                (ClassSession.date <= end_date) &
                (ClassSession.subject.ilike(f"%{subject}%")) &
                (ClassSession.class_name.ilike(f"%{class_name}%")) &
                (ClassSession.teacher_id == current_teacher.id)
            )
        )).scalars().all()
        logger.debug(f"Found {len(class_sessions)} class sessions")

        return {
            "week_duration": week_duration,
            "start_date": start_date,
            "end_date": end_date,
            "subject": subject,
            "class_name": class_name,
            "class_sessions": [
                {
                    "id": session.id,
                    "date": session.date,
                    "subject": session.subject,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "class_name": session.class_name,
                    "location": session.location,
                    "session_number": session.session_number
                }
                for session in class_sessions
            ],
        }
    except Exception as e:
        logger.error(f"Error retrieving class sessions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving class sessions: {str(e)}")

async def validate_session_ids(db: AsyncSession, session_ids: List[int], teacher_id: uuid.UUID, subject: str):
    logger.debug(f"Validating session_ids: {session_ids}, teacher_id: {teacher_id}, subject: {subject}")
    query = select(ClassSession).where(
        ClassSession.id.in_(session_ids),
        ClassSession.teacher_id == teacher_id,
        ClassSession.subject.ilike(subject)
    )
    result = await db.execute(query)
    valid_sessions = result.scalars().all()
    valid_session_ids = {session.id for session in valid_sessions}
    logger.debug(f"Found valid sessions: {[s.id for s in valid_sessions]}")
    invalid_ids = [sid for sid in session_ids if sid not in valid_session_ids]
    if invalid_ids:
        logger.error(f"Invalid session IDs: {invalid_ids}")
        raise HTTPException(status_code=404, detail=f"Invalid session IDs: {invalid_ids}")
    return session_ids

@router.put("/update-strand", response_model=List[StrandResponse], status_code=status.HTTP_200_OK)
async def update_strand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    strand_data: StrandUpdate,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = current_teacher.id

    if not strand_data.strand_name.strip():
        raise HTTPException(status_code=400, detail="Strand name cannot be empty")
    if not strand_data.weeks_sessions:
        raise HTTPException(status_code=400, detail="At least one week must be selected")
    if any(not sessions for week, sessions in strand_data.weeks_sessions.items()):
        raise HTTPException(status_code=400, detail="Each week must have at least one session")

    # Handle strand renaming: if original_strand_name is provided and different, update existing strands
    if strand_data.original_strand_name and strand_data.original_strand_name.strip() != strand_data.strand_name.strip():
        # Instead of deleting, update the strand_name of existing strands
        existing_strands_query = select(Strand).where(
            Strand.strand_name == strand_data.original_strand_name.strip(),
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        )
        existing_strands_result = await db.execute(existing_strands_query)
        existing_strands = existing_strands_result.scalars().all()
        
        # Update the strand_name for all existing strands
        for strand in existing_strands:
            strand.strand_name = strand_data.strand_name.strip()
            strand.updated_at = datetime.utcnow()
    else:
        # Fetch existing strands for the teacher, strand_name, and subject
        existing_strands_query = select(Strand).where(
            Strand.strand_name == strand_data.strand_name.strip(),
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        )
        existing_strands_result = await db.execute(existing_strands_query)
        existing_strands = existing_strands_result.scalars().all()

        # Determine weeks to update and weeks to delete
        updated_weeks = set(int(week.replace("Week ", "")) for week in strand_data.weeks_sessions.keys())
        existing_weeks = set(strand.week_number for strand in existing_strands)
        weeks_to_delete = existing_weeks - updated_weeks

        # Instead of deleting strands, just mark them as not part of the current selection
        # This preserves the foreign key relationships
        for strand in existing_strands:
            if strand.week_number in weeks_to_delete:
                # Remove sessions but keep the strand record
                strand.session_ids = []
                strand.session_details = []
                strand.updated_at = datetime.utcnow()

    updated_strands = []
    for week, session_ids in strand_data.weeks_sessions.items():
        week_number = int(week.replace("Week ", ""))
        if not (1 <= week_number <= 16):
            raise HTTPException(status_code=400, detail=f"Invalid week number: {week}")

        query = select(ClassSession).where(ClassSession.id.in_(session_ids))
        result = await db.execute(query)
        class_sessions = result.scalars().all()
        session_details = [
            {
                "id": session.id,
                "date": session.date.isoformat() if isinstance(session.date, date) else session.date,
                "subject": session.subject,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "class_name": session.class_name,
                "location": session.location,
                "week_number": week_number
            } for session in class_sessions
        ]

        if len(session_details) != len(session_ids):
            raise HTTPException(status_code=400, detail=f"Some session IDs not found: {session_ids}")

        # Update existing strand or create a new one
        strand = next((s for s in existing_strands if s.week_number == week_number), None)
        if strand:
            strand.strand_name = strand_data.strand_name.strip()
            strand.session_ids = session_ids
            strand.session_details = session_details
            strand.updated_at = datetime.utcnow()
        else:
            strand = Strand(
                strand_name=strand_data.strand_name.strip(),
                subject=strand_data.subject,
                teacher_id=teacher_id,
                week_number=week_number,
                session_ids=session_ids,
                session_details=session_details
            )
            db.add(strand)

        updated_strands.append(strand)

    await db.commit()
    for strand in updated_strands:
        await db.refresh(strand)

    return [
        StrandResponse(
            strand_name=strand.strand_name.strip(),
            subject=strand.subject,
            teacher_id=strand.teacher_id,
            weeks_sessions={f"Week {strand.week_number}": [
                SessionDetail(**detail) for detail in strand.session_details
            ]},
            created_at=strand.created_at,
            updated_at=strand.updated_at
        ) for strand in updated_strands
    ]

@router.post("/create-strands", response_model=List[StrandResponse], status_code=status.HTTP_201_CREATED)
async def create_strand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    strand_data: StrandCreate,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = current_teacher.id
    if not strand_data.strand_name.strip():
        raise HTTPException(status_code=400, detail="Strand name cannot be empty")
    if not strand_data.weeks_sessions:
        raise HTTPException(status_code=400, detail="At least one week must be selected")
    if any(not sessions for week, sessions in strand_data.weeks_sessions.items()):
        raise HTTPException(status_code=400, detail="Each week must have at least one session")

    created_strands = []
    for week, session_ids in strand_data.weeks_sessions.items():
        week_number = int(week.replace("Week ", ""))
        if not (1 <= week_number <= 16):
            raise HTTPException(status_code=400, detail=f"Invalid week number: {week}")

        query = select(ClassSession).where(ClassSession.id.in_(session_ids))
        result = await db.execute(query)
        class_sessions = result.scalars().all()
        session_details = [
            {
                "id": session.id,
                "date": session.date.isoformat() if isinstance(session.date, date) else session.date,
                "subject": session.subject,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "class_name": session.class_name,
                "location": session.location,
                "week_number": week_number
            } for session in class_sessions
        ]

        if len(session_details) != len(session_ids):
            raise HTTPException(status_code=400, detail=f"Some session IDs not found: {session_ids}")

        strand = Strand(
            strand_name=strand_data.strand_name,
            subject=strand_data.subject,
            teacher_id=teacher_id,
            week_number=week_number,
            session_ids=session_ids,
            session_details=session_details
        )
        db.add(strand)
        created_strands.append(strand)

    await db.commit()
    for strand in created_strands:
        await db.refresh(strand)

    return [
        StrandResponse(
            strand_name=strand.strand_name,
            subject=strand.subject,
            teacher_id=strand.teacher_id,
            weeks_sessions={f"Week {strand.week_number}": [
                SessionDetail(**detail) for detail in strand.session_details
            ]},
            created_at=strand.created_at,
            updated_at=strand.updated_at
        ) for strand in created_strands
    ]

@router.get("/read-strands", response_model=List[StrandResponse])
async def read_strands(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: str | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = current_teacher.id
    query = select(Strand).where(Strand.teacher_id == teacher_id)
    if subject:
        query = query.where(Strand.subject == subject)
    
    result = await db.execute(query)
    strands = result.scalars().all()

    # Filter by class_name if provided
    if class_name:
        filtered_strands = []
        for strand in strands:
            # Check if any session in this strand belongs to the specified class
            strand_has_class = any(
                detail.get('class_name') == class_name 
                for detail in strand.session_details
            )
            if strand_has_class:
                filtered_strands.append(strand)
        strands = filtered_strands

    grouped_strands = {}
    for strand in sorted(strands, key=lambda x: x.week_number):
        key = (strand.strand_name, strand.subject)
        if key not in grouped_strands:
            grouped_strands[key] = {
                "strand_name": strand.strand_name,
                "subject": strand.subject,
                "teacher_id": strand.teacher_id,
                "weeks_sessions": {},
                "created_at": strand.created_at,
                "updated_at": strand.updated_at
            }
        grouped_strands[key]["weeks_sessions"][f"Week {strand.week_number}"] = [
            SessionDetail(**detail) for detail in strand.session_details
        ]
        grouped_strands[key]["created_at"] = min(grouped_strands[key]["created_at"], strand.created_at)
        grouped_strands[key]["updated_at"] = max(grouped_strands[key]["updated_at"], strand.updated_at)

    return [StrandResponse(**data) for data in grouped_strands.values()]

async def _delete_strand_in_transaction(db: AsyncSession, strands: List[Strand], strand_name: str, subject: str):
    """
    Helper function to perform strand deletion within an existing transaction.
    FIXED: Restructured to avoid async context issues that cause "greenlet_spawn has not been called" errors.
    """
    logger.debug(f"=== STRAND DELETION PROCESS START ===")
    logger.debug(f"Processing {len(strands)} strand(s) for deletion")
    
    try:
        # FIXED: Use bulk operations and avoid nested async loops to prevent greenlet_spawn errors
        
        # Step 1: Collect all items to delete using bulk queries
        logger.debug("Step 1: Collecting items to delete using bulk queries...")
        
        strand_ids = [strand.id for strand in strands]
        logger.debug(f"Strand IDs to process: {strand_ids}")
        
        # Bulk query for all substrands
        substrands_query = select(Substrand).where(Substrand.strand_id.in_(strand_ids))
        substrands_result = await db.execute(substrands_query)
        all_substrands = substrands_result.scalars().all()
        substrand_ids = [s.id for s in all_substrands]
        logger.debug(f"Found {len(all_substrands)} substrands: {substrand_ids}")
        
        # Bulk query for all content standards
        all_content_standards = []
        if substrand_ids:
            content_standards_query = select(ContentStandard).where(ContentStandard.substrand_id.in_(substrand_ids))
            content_standards_result = await db.execute(content_standards_query)
            all_content_standards = content_standards_result.scalars().all()
            content_standard_ids = [cs.id for cs in all_content_standards]
            logger.debug(f"Found {len(all_content_standards)} content standards: {content_standard_ids}")
        else:
            content_standard_ids = []
            logger.debug("No substrands found, so no content standards to delete")
        
        # Bulk query for all indicators
        all_indicators = []
        if content_standard_ids:
            indicators_query = select(Indicator).where(Indicator.content_standard_id.in_(content_standard_ids))
            indicators_result = await db.execute(indicators_query)
            all_indicators = indicators_result.scalars().all()
            indicator_ids = [i.id for i in all_indicators]
            logger.debug(f"Found {len(all_indicators)} indicators: {indicator_ids}")
        else:
            indicator_ids = []
            logger.debug("No content standards found, so no indicators to delete")
        
        logger.debug(f"Collection complete:")
        logger.debug(f"  - Indicators to delete: {len(all_indicators)}")
        logger.debug(f"  - Content standards to delete: {len(all_content_standards)}")
        logger.debug(f"  - Substrands to delete: {len(all_substrands)}")
        logger.debug(f"  - Strands to delete: {len(strands)}")
        
        # Step 2: Delete in correct order (respecting foreign key constraints)
        logger.debug("Step 2: Performing deletions in correct order...")
        
        # CRITICAL: Delete indicators first (they reference content standards)
        if all_indicators:
            logger.debug(f"Deleting {len(all_indicators)} indicators...")
            for indicator in all_indicators:
                await db.delete(indicator)
                logger.debug(f"✓ Deleted indicator {indicator.id}")
            
            # CRITICAL: Flush to ensure indicators are actually deleted before proceeding
            await db.flush()
            logger.debug("✓ Flushed indicators deletion to database")
            
            # VERIFICATION: Check that indicators are actually gone
            remaining_indicators = await db.execute(select(Indicator).where(Indicator.id.in_(indicator_ids)))
            remaining_count = len(remaining_indicators.scalars().all())
            if remaining_count > 0:
                logger.warning(f"⚠️ {remaining_count} indicators still exist after deletion!")
            else:
                logger.debug("✅ All indicators successfully deleted and verified")
        else:
            logger.debug("No indicators to delete")
        
        # CRITICAL: Delete content standards (they reference substrands)
        if all_content_standards:
            logger.debug(f"Deleting {len(all_content_standards)} content standards...")
            
            # SAFETY CHECK: Verify no indicators still reference these content standards
            for content_standard in all_content_standards:
                # Check if any indicators still reference this content standard
                indicator_check = await db.execute(
                    select(Indicator).where(Indicator.content_standard_id == content_standard.id)
                )
                remaining_indicators = indicator_check.scalars().all()
                if remaining_indicators:
                    logger.warning(f"⚠️ Content standard {content_standard.id} still has {len(remaining_indicators)} indicators referencing it!")
                    logger.warning(f"Indicator IDs: {[i.id for i in remaining_indicators]}")
                    # Force delete the remaining indicators first
                    for indicator in remaining_indicators:
                        await db.delete(indicator)
                        logger.debug(f"✓ Force deleted remaining indicator {indicator.id}")
                    await db.flush()
                    logger.debug("✓ Flushed force deletion of remaining indicators")
            
            # Now delete the content standards
            for content_standard in all_content_standards:
                await db.delete(content_standard)
                logger.debug(f"✓ Deleted content standard {content_standard.id}")
            
            # CRITICAL: Flush to ensure content standards are actually deleted before proceeding
            await db.flush()
            logger.debug("✓ Flushed content standards deletion to database")
            
            # VERIFICATION: Check that content standards are actually gone
            remaining_content_standards = await db.execute(select(ContentStandard).where(ContentStandard.id.in_(content_standard_ids)))
            remaining_count = len(remaining_content_standards.scalars().all())
            if remaining_count > 0:
                logger.warning(f"⚠️ {remaining_count} content standards still exist after deletion!")
            else:
                logger.debug("✅ All content standards successfully deleted and verified")
        else:
            logger.debug("No content standards to delete")
        
        # CRITICAL: Delete substrands (they reference strands)
        if all_substrands:
            logger.debug(f"Deleting {len(all_substrands)} substrands...")
            
            # SAFETY CHECK: Verify no content standards still reference these substrands
            for substrand in all_substrands:
                # Check if any content standards still reference this substrand
                content_standard_check = await db.execute(
                    select(ContentStandard).where(ContentStandard.substrand_id == substrand.id)
                )
                remaining_content_standards = content_standard_check.scalars().all()
                if remaining_content_standards:
                    logger.warning(f"⚠️ Substrand {substrand.id} still has {len(remaining_content_standards)} content standards referencing it!")
                    logger.warning(f"Content standard IDs: {[cs.id for cs in remaining_content_standards]}")
                    
                    # Check and force delete any remaining indicators first
                    for content_standard in remaining_content_standards:
                        indicator_check = await db.execute(
                            select(Indicator).where(Indicator.content_standard_id == content_standard.id)
                        )
                        remaining_indicators = indicator_check.scalars().all()
                        if remaining_indicators:
                            logger.warning(f"⚠️ Content standard {content_standard.id} still has {len(remaining_indicators)} indicators!")
                            for indicator in remaining_indicators:
                                await db.delete(indicator)
                                logger.debug(f"✓ Force deleted remaining indicator {indicator.id}")
                    
                    # Now force delete the remaining content standards
                    for content_standard in remaining_content_standards:
                        await db.delete(content_standard)
                        logger.debug(f"✓ Force deleted remaining content standard {content_standard.id}")
                    
                    await db.flush()
                    logger.debug("✓ Flushed force deletion of remaining content standards and indicators")
            
            # Now delete the substrands
            for substrand in all_substrands:
                await db.delete(substrand)
                logger.debug(f"✓ Deleted substrand {substrand.id}")
            
            # CRITICAL: Flush to ensure substrands are actually deleted before proceeding
            await db.flush()
            logger.debug("✓ Flushed substrands deletion to database")
            
            # VERIFICATION: Check that substrands are actually gone
            remaining_substrands = await db.execute(select(Substrand).where(Substrand.id.in_(substrand_ids)))
            remaining_count = len(remaining_substrands.scalars().all())
            if remaining_count > 0:
                logger.warning(f"⚠️ {remaining_count} substrands still exist after deletion!")
            else:
                logger.debug("✅ All substrands successfully deleted and verified")
        else:
            logger.debug("No substrands to delete")
        
        # Finally delete strands
        logger.debug(f"Deleting {len(strands)} strands...")
        
        # SAFETY CHECK: Verify no substrands still reference these strands
        for strand in strands:
            # Check if any substrands still reference this strand
            substrand_check = await db.execute(
                select(Substrand).where(Substrand.strand_id == strand.id)
            )
            remaining_substrands = substrand_check.scalars().all()
            if remaining_substrands:
                logger.warning(f"⚠️ Strand {strand.id} still has {len(remaining_substrands)} substrands referencing it!")
                logger.warning(f"Substrand IDs: {[s.id for s in remaining_substrands]}")
                
                # This shouldn't happen if our deletion logic is working, but let's handle it
                for substrand in remaining_substrands:
                    await db.delete(substrand)
                    logger.debug(f"✓ Force deleted remaining substrand {substrand.id}")
                
                await db.flush()
                logger.debug("✓ Flushed force deletion of remaining substrands")
        
        # Now delete the strands
        for strand in strands:
            await db.delete(strand)
            logger.debug(f"✓ Deleted strand {strand.id}")
        
        # CRITICAL: Final flush to ensure all deletions are processed
        await db.flush()
        logger.debug("✓ Final flush completed - all deletions processed")

        # Log the deletion summary
        logger.info(f"=== STRAND DELETION PROCESS COMPLETE ===")
        logger.info(f"Successfully deleted strand: strand_name={strand_name}, subject={subject}")
        logger.info(f"Total items deleted: {len(all_indicators)} indicators, {len(all_content_standards)} content standards, {len(all_substrands)} substrands, {len(strands)} strand(s)")
        
        # CRITICAL: Verify deletions were registered in the session
        logger.debug("Verifying deletions in database session...")
        logger.debug(f"Session dirty objects: {len(db.dirty)}")
        logger.debug(f"Session new objects: {len(db.new)}")
        logger.debug(f"Session deleted objects: {len(db.deleted)}")
        
    except Exception as e:
        logger.error(f"Error in _delete_strand_in_transaction: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise e


@router.delete("/delete-strand", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    strand_name: str,
    subject: str,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting strand: strand_name={strand_name}, subject={subject}, teacher_id={current_teacher.id}")
    
    try:
        # Query for strands matching the strand_name, subject, and teacher_id
        query = select(Strand).where(
            Strand.strand_name == strand_name,
            Strand.subject == subject,
            Strand.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        strands = result.scalars().all()

        if not strands:
            logger.error(f"Strand not found: strand_name={strand_name}, subject={subject}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strand '{strand_name}' for subject '{subject}' not found"
            )

        logger.debug(f"Starting strand deletion process for {len(strands)} strand(s)")
        
        # FIXED: Simplified transaction handling to avoid greenlet_spawn errors
        # Use the existing session directly without complex transaction management
        logger.debug("Performing deletions using existing session...")
        
        try:
            # Perform deletions directly
            await _delete_strand_in_transaction(db, strands, strand_name, subject)
            logger.debug("All deletions completed successfully")
            
            # Commit the changes
            await db.commit()
            logger.debug("Changes committed successfully")
            
        except Exception as deletion_error:
            logger.error(f"Deletion error: {str(deletion_error)}")
            # Rollback on error
            try:
                await db.rollback()
                logger.info("Rollback successful after deletion error")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {str(rollback_error)}")
            
            # Re-raise the error
            raise deletion_error
        
        # Verify the deletion actually happened by querying the database
        logger.debug("Verifying deletion in database...")
        
        # Use a fresh session for verification to avoid transaction state issues
        try:
            verification_query = select(Strand).where(
                Strand.strand_name == strand_name,
                Strand.subject == subject,
                Strand.teacher_id == current_teacher.id
            )
            verification_result = await db.execute(verification_query)
            remaining_strands = verification_result.scalars().all()
            
            if remaining_strands:
                logger.error(f"❌ DELETION VERIFICATION FAILED: {len(remaining_strands)} strand(s) still exist in database!")
                logger.error(f"Remaining strand IDs: {[s.id for s in remaining_strands]}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Strand deletion failed - {len(remaining_strands)} strand(s) still exist in database"
                )
            else:
                logger.info("✅ DELETION VERIFICATION SUCCESSFUL: All strands removed from database")
                
        except Exception as verification_error:
            logger.error(f"Verification query failed: {str(verification_error)}")
            # Don't fail the deletion if verification fails - the deletion might have succeeded
            logger.warning("Deletion completed but verification failed - strand may or may not have been deleted")
        
    except HTTPException:
        # Re-raise HTTP exceptions without rollback
        raise
    except Exception as e:
        logger.error(f"Error deleting strand: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        
        # Handle transaction-related errors specifically
        if "transaction is already begun" in str(e).lower():
            logger.error("Transaction conflict detected - attempting rollback and retry")
            try:
                await db.rollback()
                logger.info("Rollback successful")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {str(rollback_error)}")
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database transaction conflict. Please try again."
            )
        
        # For other errors, attempt rollback
        try:
            await db.rollback()
            logger.info("Rollback successful for general error")
        except Exception as rollback_error:
            logger.error(f"Rollback failed: {str(rollback_error)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting strand: {str(e)}"
        )
    
# CRUD Endpoints
@router.post("/create-substrand", response_model=List[SubstrandResponse], status_code=status.HTTP_201_CREATED)
async def create_substrand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    substrand_data: SubstrandCreate,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = str(current_teacher.id)  # Ensure teacher_id is a string
    if not substrand_data.substrand_name.strip():
        raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
    if not substrand_data.weeks_sessions:
        raise HTTPException(status_code=400, detail="At least one week must be selected")
    if any(not sessions for week, sessions in substrand_data.weeks_sessions.items()):
        raise HTTPException(status_code=400, detail="Each week must have at least one session")

    # Find all Strand records for the strand_name, subject, and teacher_id
    strands = (await db.execute(
        select(Strand).where(
            Strand.strand_name == substrand_data.strand_name,
            Strand.subject == substrand_data.subject,
            Strand.teacher_id == teacher_id
        )
    )).scalars().all()
    if not strands:
        logger.error(f"Strand {substrand_data.strand_name} not found for subject {substrand_data.subject}")
        raise HTTPException(status_code=404, detail=f"Strand {substrand_data.strand_name} not found")

    # Collect all strand IDs and week numbers
    strand_ids = [strand.id for strand in strands]
    strand_weeks = [strand.week_number for strand in strands]

    created_substrands = []
    for week, session_ids in substrand_data.weeks_sessions.items():
        week_number = int(week.replace("Week ", ""))
        if not (1 <= week_number <= 16):
            raise HTTPException(status_code=400, detail=f"Invalid week number: {week}")

        # Verify week belongs to the strand
        if week_number not in strand_weeks:
            raise HTTPException(status_code=400, detail=f"Week {week_number} not assigned to strand {substrand_data.strand_name}")

        # Find the specific strand for this week
        strand = next((s for s in strands if s.week_number == week_number), None)
        if not strand:
            raise HTTPException(status_code=400, detail=f"No strand found for week {week_number}")

        # Validate sessions
        valid_sessions = await validate_session_ids_for_substrand(
            db, session_ids, teacher_id, substrand_data.subject, substrand_data.strand_name
        )
        session_details = [
            {
                "id": session.id,
                "date": session.date.isoformat() if isinstance(session.date, date) else session.date,
                "subject": session.subject,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "class_name": session.class_name,
                "location": session.location,
                "week_number": week_number
            } for session in valid_sessions
        ]

        if len(session_details) != len(session_ids):
            raise HTTPException(status_code=400, detail=f"Some session IDs not found: {session_ids}")

        substrand = Substrand(
            substrand_name=substrand_data.substrand_name,
            strand_id=strand.id,
            subject=substrand_data.subject,
            teacher_id=teacher_id,
            week_numbers=[week_number],
            session_ids=session_ids,
            session_details=session_details
        )
        db.add(substrand)
        created_substrands.append(substrand)

    await db.commit()
    for substrand in created_substrands:
        await db.refresh(substrand)

    return [
        SubstrandResponse(
            substrand_name=substrand.substrand_name,
            strand_name=strand.strand_name,
            subject=substrand.subject,
            teacher_id=substrand.teacher_id,
            weeks_sessions={f"Week {week_number}": [
                SessionDetail(**detail) for detail in substrand.session_details
            ] for week_number in substrand.week_numbers},
            created_at=substrand.created_at,
            updated_at=substrand.updated_at
        ) for substrand in created_substrands
    ]


@router.get("/read-substrands", response_model=List[SubstrandResponse])
async def read_substrands(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: str | None = None,
    strand_name: str | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = current_teacher.id
    query = select(Substrand).where(Substrand.teacher_id == teacher_id)
    if subject:
        query = query.where(Substrand.subject == subject)
    if strand_name:
        strand = (await db.execute(
            select(Strand).where(
                Strand.strand_name == strand_name,
                Strand.teacher_id == teacher_id
            )
        )).scalars().first()
        if not strand:
            raise HTTPException(status_code=404, detail=f"Strand {strand_name} not found")
        query = query.where(Substrand.strand_id == strand.id)

    result = await db.execute(query)
    substrands = result.scalars().all()

    # Filter by class_name if provided
    if class_name:
        filtered_substrands = []
        for substrand in substrands:
            # Check if any session in this substrand belongs to the specified class
            substrand_has_class = any(
                detail.get('class_name') == class_name 
                for detail in substrand.session_details
            )
            if substrand_has_class:
                filtered_substrands.append(substrand)
        substrands = filtered_substrands

    grouped_substrands = {}
    for substrand in sorted(substrands, key=lambda x: min(x.week_numbers)):
        strand = (await db.execute(
            select(Strand).where(Strand.id == substrand.strand_id)
        )).scalar_one()
        key = (substrand.substrand_name, substrand.subject, substrand.strand_id)
        if key not in grouped_substrands:
            grouped_substrands[key] = {
                "substrand_name": substrand.substrand_name,
                "strand_name": strand.strand_name,
                "subject": substrand.subject,
                "teacher_id": substrand.teacher_id,
                "weeks_sessions": {},
                "created_at": substrand.created_at,
                "updated_at": substrand.updated_at
            }
        for week_number in substrand.week_numbers:
            grouped_substrands[key]["weeks_sessions"][f"Week {week_number}"] = [
                SessionDetail(**detail) for detail in substrand.session_details
            ]
        grouped_substrands[key]["created_at"] = min(grouped_substrands[key]["created_at"], substrand.created_at)
        grouped_substrands[key]["updated_at"] = max(grouped_substrands[key]["updated_at"], substrand.updated_at)

    return [SubstrandResponse(**data) for data in grouped_substrands.values()]

async def validate_session_ids_for_substrand(
    db: AsyncSession,
    session_ids: List[int],
    teacher_id: str,
    subject: str,
    strand_name: str,
    exclude_substrand_name: str | None = None
):
    # Convert teacher_id to UUID if it's a string
    try:
        teacher_id = str(UUID(teacher_id)) if isinstance(teacher_id, str) else str(teacher_id)
    except ValueError:
        logger.error(f"Invalid teacher_id format: {teacher_id}")
        raise HTTPException(status_code=400, detail="Invalid teacher_id format")

    # Find all Strand records matching the strand_name, subject, and teacher_id
    strands = (await db.execute(
        select(Strand).where(
            Strand.strand_name == strand_name,
            Strand.subject.ilike(subject),
            Strand.teacher_id == teacher_id
        )
    )).scalars().all()

    if not strands:
        logger.error(f"No strands found for strand_name {strand_name}, subject {subject}, teacher_id {teacher_id}")
        raise HTTPException(status_code=404, detail=f"Strand {strand_name} not found")

    # Collect all session_ids from matching strands
    valid_strand_session_ids = set()
    for strand in strands:
        valid_strand_session_ids.update(strand.session_ids)

    invalid_ids = [sid for sid in session_ids if sid not in valid_strand_session_ids]
    if invalid_ids:
        logger.error(f"Session IDs {invalid_ids} not in strand {strand_name}")
        raise HTTPException(status_code=400, detail=f"Session IDs {invalid_ids} not in strand {strand_name}")

    # Check if sessions are already assigned to another substrand, excluding the specified substrand
    query = select(Substrand).where(
        Substrand.strand_id.in_([strand.id for strand in strands]),
        Substrand.teacher_id == teacher_id
    )
    if exclude_substrand_name:
        query = query.where(Substrand.substrand_name != exclude_substrand_name)

    existing_substrands = (await db.execute(query)).scalars().all()
    assigned_session_ids = set()
    for substrand in existing_substrands:
        assigned_session_ids.update(substrand.session_ids)
    
    conflicting_ids = [sid for sid in session_ids if sid in assigned_session_ids]
    if conflicting_ids:
        logger.error(f"Session IDs {conflicting_ids} already assigned to another substrand")
        raise HTTPException(status_code=400, detail=f"Session IDs {conflicting_ids} already assigned to another substrand")

    # Validate sessions exist and belong to teacher and subject
    query = select(ClassSession).where(
        ClassSession.id.in_(session_ids),
        ClassSession.teacher_id == teacher_id,
        ClassSession.subject.ilike(subject)
    )
    result = await db.execute(query)
    valid_sessions = result.scalars().all()
    valid_session_ids = {session.id for session in valid_sessions}
    invalid_ids = [sid for sid in session_ids if sid not in valid_session_ids]
    if invalid_ids:
        logger.error(f"Invalid session IDs: {invalid_ids}")
        raise HTTPException(status_code=404, detail=f"Invalid session IDs: {invalid_ids}")
    
    return valid_sessions

@router.put("/update-substrand", response_model=List[SubstrandResponse], status_code=status.HTTP_200_OK)
async def update_substrand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    substrand_data: SubstrandUpdate,
    db: AsyncSession = Depends(get_db)
):
    teacher_id = str(current_teacher.id)  # Ensure teacher_id is a string
    if not substrand_data.substrand_name.strip():
        raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
    if not substrand_data.weeks_sessions:
        raise HTTPException(status_code=400, detail="At least one week must be selected")
    if any(not sessions for week, sessions in substrand_data.weeks_sessions.items()):
        raise HTTPException(status_code=400, detail="Each week must have at least one session")

    # Find all Strand records for the strand_name, subject, and teacher_id
    strands = (await db.execute(
        select(Strand).where(
            Strand.strand_name == substrand_data.strand_name,
            Strand.subject == substrand_data.subject,
            Strand.teacher_id == teacher_id
        )
    )).scalars().all()
    if not strands:
        logger.error(f"Strand {substrand_data.strand_name} not found for subject {substrand_data.subject}")
        raise HTTPException(status_code=404, detail=f"Strand {substrand_data.strand_name} not found")

    # Collect all strand IDs and week numbers
    strand_ids = [strand.id for strand in strands]
    strand_weeks = [strand.week_number for strand in strands]

    # Fetch existing substrands
    substrand_to_query = substrand_data.original_substrand_name or substrand_data.substrand_name
    existing_substrands_query = select(Substrand).where(
        Substrand.substrand_name == substrand_to_query,
        Substrand.subject == substrand_data.subject,
        Substrand.strand_id.in_(strand_ids),
        Substrand.teacher_id == teacher_id
    )
    existing_substrands_result = await db.execute(existing_substrands_query)
    existing_substrands = existing_substrands_result.scalars().all()

    # Determine weeks to update and weeks to delete
    updated_weeks = set(int(week.replace("Week ", "")) for week in substrand_data.weeks_sessions.keys())
    existing_weeks = set(week for substrand in existing_substrands if substrand.substrand_name == substrand_to_query for week in substrand.week_numbers)
    weeks_to_delete = existing_weeks - updated_weeks

    # Instead of deleting substrands directly, handle foreign key constraints
    for substrand in existing_substrands:
        if substrand.substrand_name == substrand_to_query and any(week in weeks_to_delete for week in substrand.week_numbers):
            # Delete associated content standards and indicators first
            content_standards = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == teacher_id
                )
            )).scalars().all()
            
            for cs in content_standards:
                try:
                    # Delete indicators associated with this content standard first
                    indicators = (await db.execute(
                        select(Indicator).where(
                            Indicator.content_standard_id == cs.id,
                            Indicator.teacher_id == teacher_id
                        )
                    )).scalars().all()
                    for indicator in indicators:
                        await db.delete(indicator)
                    
                    # Now delete the content standard
                    await db.delete(cs)
                except Exception as e:
                    logger.error(f"Error deleting content standard {cs.id}: {str(e)}")
                    raise
            
            # Now delete the substrand
            await db.delete(substrand)

    updated_substrands = []
    for week, session_ids in substrand_data.weeks_sessions.items():
        week_number = int(week.replace("Week ", ""))
        if not (1 <= week_number <= 16):
            raise HTTPException(status_code=400, detail=f"Invalid week number: {week}")

        # Verify week belongs to the strand
        if week_number not in strand_weeks:
            raise HTTPException(status_code=400, detail=f"Week {week_number} not assigned to strand {substrand_data.strand_name}")

        # Find the specific strand for this week
        strand = next((s for s in strands if s.week_number == week_number), None)
        if not strand:
            raise HTTPException(status_code=400, detail=f"No strand found for week {week_number}")

        # Validate sessions, excluding the current substrand
        valid_sessions = await validate_session_ids_for_substrand(
            db, session_ids, teacher_id, substrand_data.subject, substrand_data.strand_name,
            exclude_substrand_name=substrand_data.original_substrand_name or substrand_data.substrand_name
        )
        session_details = [
            {
                "id": session.id,
                "date": session.date.isoformat() if isinstance(session.date, date) else session.date,
                "subject": session.subject,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "class_name": session.class_name,
                "location": session.location,
                "week_number": week_number
            } for session in valid_sessions
        ]

        if len(session_details) != len(session_ids):
            raise HTTPException(status_code=400, detail=f"Some session IDs not found: {session_ids}")

        # Update existing substrand or create a new one
        substrand = next((s for s in existing_substrands if s.substrand_name == substrand_to_query and week_number in s.week_numbers), None)
        if substrand:
            substrand.substrand_name = substrand_data.substrand_name
            substrand.session_ids = session_ids
            substrand.session_details = session_details
            substrand.updated_at = datetime.utcnow()
        else:
            substrand = Substrand(
                substrand_name=substrand_data.substrand_name,
                strand_id=strand.id,
                subject=substrand_data.subject,
                teacher_id=teacher_id,
                week_numbers=[week_number],
                session_ids=session_ids,
                session_details=session_details,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(substrand)

        updated_substrands.append(substrand)

    await db.commit()
    for substrand in updated_substrands:
        await db.refresh(substrand)

    return [
        SubstrandResponse(
            substrand_name=substrand.substrand_name,
            strand_name=strand.strand_name,
            subject=substrand.subject,
            teacher_id=substrand.teacher_id,
            weeks_sessions={f"Week {week_number}": [
                SessionDetail(**detail) for detail in substrand.session_details
            ] for week_number in substrand.week_numbers},
            created_at=substrand.created_at,
            updated_at=substrand.updated_at
        ) for substrand in updated_substrands
    ]

@router.delete("/delete-substrand", status_code=status.HTTP_204_NO_CONTENT)
async def delete_substrand(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    substrand_name: str,
    strand_name: str,
    subject: str,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting substrand: substrand_name={substrand_name}, strand_name={strand_name}, subject={subject}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == strand_name,
                Strand.subject == subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        logger.debug(f"Query result for strands: {[(s.id, s.strand_name, s.week_number) for s in strands]}")

        if not strands:
            logger.error(f"No strands found for strand_name: {strand_name}, subject: {subject}")
            raise HTTPException(status_code=404, detail=f"Strand {strand_name} not found")

        # Iterate through strands to find a matching substrand
        substrand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}, week_number: {strand.week_number}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Query result for substrand: {result}")
            if result:
                substrand = result
                break  # Exit loop once a matching substrand is found

        if not substrand:
            logger.error(f"Substrand {substrand_name} not found for strand_name: {strand_name}, subject: {subject}")
            raise HTTPException(status_code=404, detail=f"Substrand {substrand_name} not found")

        # Delete associated content standards and their indicators
        content_standards = (await db.execute(
            select(ContentStandard).where(
                ContentStandard.substrand_id == substrand.id,
                ContentStandard.teacher_id == current_teacher.id
            )
        )).scalars().all()
        
        total_indicators_deleted = 0
        total_content_standards_deleted = 0
        
        # Step 1: Delete ALL indicators first
        logger.debug(f"Step 1: Deleting all indicators for {len(content_standards)} content standards")
        for cs in content_standards:
            try:
                # Find and delete indicators for this content standard
                indicators = (await db.execute(
                    select(Indicator).where(
                        Indicator.content_standard_id == cs.id,
                        Indicator.teacher_id == current_teacher.id
                    )
                )).scalars().all()
                
                if indicators:
                    logger.debug(f"Found {len(indicators)} indicators to delete for content standard {cs.id}")
                    for indicator in indicators:
                        await db.delete(indicator)
                        logger.debug(f"Deleted indicator {indicator.id} ({indicator.indicator_text})")
                    total_indicators_deleted += len(indicators)
                else:
                    logger.debug(f"No indicators found for content standard {cs.id}")
                    
            except Exception as e:
                logger.error(f"Error deleting indicators for content standard {cs.id}: {str(e)}")
                await db.rollback()
                raise
        
        # Commit indicator deletions first
        await db.commit()
        logger.debug(f"Step 1 complete: Committed deletion of {total_indicators_deleted} indicators")
        
        # Step 2: Delete ALL content standards
        logger.debug(f"Step 2: Deleting all content standards")
        for cs in content_standards:
            try:
                logger.debug(f"Deleting content standard: code={cs.content_standard_code}, substrand_id={substrand.id}")
                await db.delete(cs)
                total_content_standards_deleted += 1
                logger.debug(f"Deleted content standard {cs.id}")
                
            except Exception as e:
                logger.error(f"Error deleting content standard {cs.id}: {str(e)}")
                await db.rollback()
                raise
        
        # Commit content standard deletions
        await db.commit()
        logger.debug(f"Step 2 complete: Committed deletion of {total_content_standards_deleted} content standards")

        # Step 3: Delete the substrand
        logger.debug(f"Step 3: Deleting substrand")
        await db.delete(substrand)
        await db.commit()
        
        logger.info(f"Successfully deleted substrand: {substrand_name}, substrand_id: {substrand.id}")
        logger.info(f"Total items deleted: {total_content_standards_deleted} content standards, {total_indicators_deleted} indicators, 1 substrand")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting substrand: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting substrand: {str(e)}")


# New CRUD endpoints for ContentStandard
@router.post("/create-content-standard", response_model=ContentStandardResponse, status_code=status.HTTP_201_CREATED)
async def create_content_standard(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    content_standard_data: ContentStandardCreate,
    db: AsyncSession = Depends(get_db)
):
    # CREATE CONTENT STANDARD FUNCTION - unique identifier for create function
    logger.debug(f"Received content standard data: {content_standard_data.model_dump_json()}")
    logger.debug(f"Creating content standard: code={content_standard_data.content_standard_code}, substrand_name={content_standard_data.substrand_name}, strand_name={content_standard_data.strand_name}, subject={content_standard_data.subject}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not content_standard_data.content_standard.strip():
            logger.error("Content standard description cannot be empty")
            raise HTTPException(status_code=400, detail="Content standard description cannot be empty")
        if not content_standard_data.substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not content_standard_data.strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not content_standard_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == content_standard_data.strand_name,
                Strand.subject == content_standard_data.subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        logger.debug(f"Query result for strands: {[(s.id, s.strand_name, s.week_number) for s in strands]}")

        if not strands:
            logger.error(f"No strands found for strand_name: {content_standard_data.strand_name}, subject: {content_standard_data.subject}")
            raise HTTPException(status_code=404, detail=f"Strand {content_standard_data.strand_name} not found")

        # Iterate through strands to find a matching substrand
        substrand = None
        selected_strand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}, week_number: {strand.week_number}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == content_standard_data.substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == content_standard_data.subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Query result for substrand: {result}")
            if result:
                substrand = result
                selected_strand = strand
                break  # Exit loop once a matching substrand is found

        if not substrand:
            logger.error(f"Substrand {content_standard_data.substrand_name} not found for strand_name: {content_standard_data.strand_name}, subject: {content_standard_data.subject}")
            raise HTTPException(status_code=404, detail=f"Substrand {content_standard_data.substrand_name} not found")

        # Check for duplicate content_standard_code within the same substrand (only if code is provided)
        if content_standard_data.content_standard_code:
            existing_content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_data.content_standard_code,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
            if existing_content_standard:
                logger.error(f"Content standard code {content_standard_data.content_standard_code} already exists for substrand {content_standard_data.substrand_name}, substrand_id: {substrand.id}")
                raise HTTPException(status_code=400, detail=f"Content standard code {content_standard_data.content_standard_code} already exists for this substrand")

        # Create new content standard
        content_standard = ContentStandard(
            content_standard_code=content_standard_data.content_standard_code.strip() if content_standard_data.content_standard_code else None,
            content_standard=content_standard_data.content_standard.strip(),
            substrand_id=substrand.id,
            subject=content_standard_data.subject.strip(),
            teacher_id=current_teacher.id
        )
        
        # Handle session storage if weeks_sessions is provided
        if content_standard_data.weeks_sessions:
            # Extract all session IDs from the weeks_sessions
            all_session_ids = []
            for week_sessions in content_standard_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            # Store session IDs
            content_standard.session_ids = all_session_ids
            
            # Get session details from ClassSession table
            if all_session_ids:
                session_details = (await db.execute(
                    select(ClassSession).where(ClassSession.id.in_(all_session_ids))
                )).scalars().all()
                
                # Convert to the format expected by the frontend
                # We need to map sessions back to their weeks based on the weeks_sessions input
                # Since ClassSession doesn't have week_number, we calculate it from the input
                weeks_sessions = {}
                for week, session_ids in content_standard_data.weeks_sessions.items():
                    week_number = int(week.replace("Week ", ""))
                    # Find sessions that belong to this week
                    week_sessions = [s for s in session_details if s.id in session_ids]
                    if week_sessions:
                        weeks_sessions[week] = [
                            {
                                "id": session.id,
                                "date": str(session.date),
                                "subject": session.subject,
                                "start_time": str(session.start_time),
                                "end_time": str(session.end_time),
                                "class_name": session.class_name,
                                "location": session.location,
                                "week_number": week_number
                            } for session in week_sessions
                        ]
                
                # Flatten all sessions for storage
                content_standard.session_details = [session for week_sessions in weeks_sessions.values() for session in week_sessions]
        
        db.add(content_standard)
        await db.commit()
        await db.refresh(content_standard)

        logger.debug(f"Successfully created content standard: code={content_standard.content_standard_code}, substrand_id: {substrand.id}")
        
        # Convert session_details back to weeks_sessions format for frontend
        weeks_sessions = None
        if content_standard.session_details:
            weeks_sessions = {}
            for session_detail in content_standard.session_details:
                week_key = f"Week {session_detail.get('week_number', 1)}"
                if week_key not in weeks_sessions:
                    weeks_sessions[week_key] = []
                weeks_sessions[week_key].append(session_detail)
        
        return ContentStandardResponse(
            content_standard_code=content_standard.content_standard_code,
            content_standard=content_standard.content_standard,
            substrand_name=substrand.substrand_name,
            strand_name=selected_strand.strand_name,
            subject=content_standard.subject,
            teacher_id=content_standard.teacher_id,
            weeks_sessions=weeks_sessions,  # Return the properly formatted weeks_sessions
            created_at=content_standard.created_at,
            updated_at=content_standard.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating content standard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating content standard: {str(e)}")  
      
@router.get("/read-content-standards", response_model=List[ContentStandardResponse])
async def read_content_standards(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: str | None = None,
    strand_name: str | None = None,
    substrand_name: str | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading content standards: subject={subject}, strand_name={strand_name}, substrand_name={substrand_name}, teacher_id={current_teacher.id}")
    try:
        query = select(ContentStandard).where(ContentStandard.teacher_id == current_teacher.id)
        if subject:
            query = query.where(ContentStandard.subject == subject)
        if strand_name or substrand_name:
            strand_query = select(Strand).where(
                Strand.teacher_id == current_teacher.id
            )
            if strand_name:
                strand_query = strand_query.where(Strand.strand_name == strand_name)
            if subject:
                strand_query = strand_query.where(Strand.subject == subject)
            strands = (await db.execute(strand_query)).scalars().all()
            if not strands:
                logger.error(f"No strands found for strand_name={strand_name}, subject={subject}")
                raise HTTPException(status_code=404, detail=f"No strands found")
            strand_ids = [strand.id for strand in strands]

            substrand_query = select(Substrand).where(
                Substrand.strand_id.in_(strand_ids),
                Substrand.teacher_id == current_teacher.id
            )
            if substrand_name:
                substrand_query = substrand_query.where(Substrand.substrand_name == substrand_name)
            if subject:
                substrand_query = substrand_query.where(Substrand.subject == subject)
            substrands = (await db.execute(substrand_query)).scalars().all()
            if not substrands:
                logger.error(f"No substrands found for strand_name={strand_name}, substrand_name={substrand_name}")
                raise HTTPException(status_code=404, detail=f"No substrands found")
            substrand_ids = [substrand.id for substrand in substrands]

            query = query.where(ContentStandard.substrand_id.in_(substrand_ids))

        result = await db.execute(query)
        content_standards = result.scalars().all()
        if not content_standards:
            logger.debug("No content standards found")
            return []

        # Filter by class_name if provided
        if class_name:
            filtered_content_standards = []
            for cs in content_standards:
                # Get the substrand for this content standard
                substrand = (await db.execute(
                    select(Substrand).where(Substrand.id == cs.substrand_id)
                )).scalars().first()
                if substrand:
                    # Check if any session in this substrand belongs to the specified class
                    substrand_has_class = any(
                        detail.get('class_name') == class_name 
                        for detail in substrand.session_details
                    )
                    if substrand_has_class:
                        filtered_content_standards.append(cs)
            content_standards = filtered_content_standards

        response = []
        for cs in content_standards:
            substrand = (await db.execute(
                select(Substrand).where(Substrand.id == cs.substrand_id)
            )).scalars().first()
            strand = (await db.execute(
                select(Strand).where(Strand.id == substrand.strand_id)
            )).scalars().first()
            
            # Convert session_ids back to weeks_sessions format for frontend
            # This returns ALL sessions that belong to the content standard, not just unassigned ones
            weeks_sessions = None
            
            if cs.session_ids:
                weeks_sessions = {}
                # Get the full session details from the substrand
                if substrand.session_details:
                    for session_detail in substrand.session_details:
                        if session_detail.get('id') in cs.session_ids:
                            week_key = f"Week {session_detail.get('week_number', 1)}"
                            if week_key not in weeks_sessions:
                                weeks_sessions[week_key] = []
                            weeks_sessions[week_key].append(session_detail)
            
            response.append(ContentStandardResponse(
                content_standard_code=cs.content_standard_code,
                content_standard=cs.content_standard,
                substrand_name=substrand.substrand_name,
                strand_name=strand.strand_name,
                subject=cs.subject,
                teacher_id=cs.teacher_id,
                weeks_sessions=weeks_sessions,
                created_at=cs.created_at,
                updated_at=cs.updated_at
            ))

        logger.debug(f"Returning {len(response)} content standards")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading content standards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading content standards: {str(e)}")
    
@router.post("/create-indicator", response_model=IndicatorResponse, status_code=status.HTTP_201_CREATED)
async def create_indicator(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    indicator_data: IndicatorCreate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Creating indicator: code={indicator_data.indicator_code}, text={indicator_data.indicator_text}, content_standard_code={indicator_data.content_standard_code}, content_standard_text={indicator_data.content_standard_text}, substrand_name={indicator_data.substrand_name}, strand_name={indicator_data.strand_name}, subject={indicator_data.subject}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs
        if not indicator_data.indicator_text.strip():
            logger.error("Indicator text cannot be empty")
            raise HTTPException(status_code=400, detail="Indicator text cannot be empty")
        if not indicator_data.substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not indicator_data.strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not indicator_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == indicator_data.strand_name,
                Strand.subject == indicator_data.subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        logger.debug(f"Query result for strands: {[(s.id, s.strand_name, s.week_number) for s in strands]}")

        if not strands:
            logger.error(f"No strands found for strand_name: {indicator_data.strand_name}, subject: {indicator_data.subject}")
            raise HTTPException(status_code=404, detail=f"Strand {indicator_data.strand_name} not found")

        # Iterate through strands to find a matching substrand
        substrand = None
        selected_strand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}, week_number: {strand.week_number}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == indicator_data.substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == indicator_data.subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Query result for substrand: {result}")
            if result:
                substrand = result
                selected_strand = strand
                break  # Exit loop once a matching substrand is found

        if not substrand:
            logger.error(f"Substrand {indicator_data.substrand_name} not found for strand_name: {indicator_data.strand_name}, subject: {indicator_data.subject}")
            raise HTTPException(status_code=404, detail=f"Substrand {indicator_data.substrand_name} not found")

        # Find the content standard using either content_standard_code or content_standard_text
        content_standard = None
        if indicator_data.content_standard_code:
            content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard_code == indicator_data.content_standard_code,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        elif indicator_data.content_standard_text:
            content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard == indicator_data.content_standard_text,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if not content_standard:
            error_msg = f"Content standard not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            if indicator_data.content_standard_code:
                error_msg = f"Content standard {indicator_data.content_standard_code} not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            elif indicator_data.content_standard_text:
                error_msg = f"Content standard with text '{indicator_data.content_standard_text}' not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Check for duplicate indicator_code within the same content standard (only if code is provided)
        if indicator_data.indicator_code:
            existing_indicator = (await db.execute(
                select(Indicator).where(
                    Indicator.indicator_code == indicator_data.indicator_code,
                    Indicator.content_standard_id == content_standard.id,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().first()
            if existing_indicator:
                logger.error(f"Indicator code {indicator_data.indicator_code} already exists for content standard {content_standard.content_standard}, content_standard_id: {content_standard.id}")
                raise HTTPException(status_code=400, detail=f"Indicator code {indicator_data.indicator_code} already exists for this content standard")

        # Check if any sessions are already assigned to other indicators
        if indicator_data.weeks_sessions:
            all_session_ids = []
            for week_sessions in indicator_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            if all_session_ids:
                # Check for sessions already assigned to other indicators
                # Use a more compatible approach that doesn't rely on JSONB overlap
                all_existing_indicators = (await db.execute(
                    select(Indicator).where(
                        Indicator.teacher_id == current_teacher.id
                    )
                )).scalars().all()
                
                # Check for session conflicts manually
                conflicting_sessions = []
                for existing_indicator in all_existing_indicators:
                    if existing_indicator.session_ids:
                        # Check if any sessions overlap
                        for session_id in all_session_ids:
                            if session_id in existing_indicator.session_ids:
                                conflicting_sessions.append(session_id)
                
                if conflicting_sessions:
                    # Get session details for better error message
                    session_details = (await db.execute(
                        select(ClassSession).where(ClassSession.id.in_(conflicting_sessions))
                    )).scalars().all()
                    
                    session_info = [f"{s.date} {s.start_time}-{s.end_time}" for s in session_details]
                    error_msg = f"The following sessions are already assigned to other indicators and cannot be reassigned: {', '.join(session_info)}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=400, detail=error_msg)

        # Create new indicator
        indicator = Indicator(
            indicator_code=indicator_data.indicator_code.strip() if indicator_data.indicator_code else None,
            indicator_text=indicator_data.indicator_text.strip(),
            content_standard_id=content_standard.id,
            subject=indicator_data.subject.strip(),
            teacher_id=current_teacher.id
        )
        
        # Handle session storage if weeks_sessions is provided
        if indicator_data.weeks_sessions:
            # Extract all session IDs from the weeks_sessions
            all_session_ids = []
            for week_sessions in indicator_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            # Store session IDs
            indicator.session_ids = all_session_ids
            
            # Get session details from ClassSession table
            if all_session_ids:
                session_details = (await db.execute(
                    select(ClassSession).where(ClassSession.id.in_(all_session_ids))
                )).scalars().all()
                
                # Convert to the format expected by the frontend
                # We need to map sessions back to their weeks based on the weeks_sessions input
                # Since ClassSession doesn't have week_number, we calculate it from the input
                weeks_sessions = {}
                for week, session_ids in indicator_data.weeks_sessions.items():
                    week_number = int(week.replace("Week ", ""))
                    # Find sessions that belong to this week
                    week_sessions = [s for s in session_details if s.id in session_ids]
                    if week_sessions:
                        weeks_sessions[week] = [
                            {
                                "id": session.id,
                                "date": str(session.date),
                                "subject": session.subject,
                                "start_time": str(session.start_time),
                                "end_time": str(session.end_time),
                                "class_name": session.class_name,
                                "location": session.location,
                                "week_number": week_number
                            } for session in week_sessions
                        ]
                
                # Flatten all sessions for storage
                indicator.session_details = [session for week_sessions in weeks_sessions.values() for session in week_sessions]
        
        db.add(indicator)
        await db.commit()
        await db.refresh(indicator)

        logger.debug(f"Successfully created indicator: code={indicator.indicator_code}, content_standard_id: {content_standard.id}")
        
        # Convert session_details back to weeks_sessions format for frontend
        weeks_sessions = None
        if indicator.session_details:
            weeks_sessions = {}
            for session_detail in indicator.session_details:
                week_key = f"Week {session_detail.get('week_number', 1)}"
                if week_key not in weeks_sessions:
                    weeks_sessions[week_key] = []
                weeks_sessions[week_key].append(session_detail)
        
        return IndicatorResponse(
            indicator_code=indicator.indicator_code,
            indicator_text=indicator.indicator_text,
            content_standard_code=content_standard.content_standard_code,
            content_standard_text=content_standard.content_standard,
            substrand_name=substrand.substrand_name,
            strand_name=selected_strand.strand_name,
            subject=indicator.subject,
            teacher_id=indicator.teacher_id,
            weeks_sessions=weeks_sessions,
            created_at=indicator.created_at,
            updated_at=indicator.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating indicator: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating indicator: {str(e)}")


@router.put("/update-indicator", response_model=IndicatorResponse, status_code=status.HTTP_200_OK)
async def update_indicator(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    indicator_data: IndicatorUpdate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Updating indicator: code={indicator_data.indicator_code}, text={indicator_data.indicator_text}, content_standard_code={indicator_data.content_standard_code}, content_standard_text={indicator_data.content_standard_text}, substrand_name={indicator_data.substrand_name}, strand_name={indicator_data.strand_name}, subject={indicator_data.subject}, teacher_id={current_teacher.id}, original_code={indicator_data.original_indicator_code}, original_text={indicator_data.original_indicator_text}")
    try:
        # Validate inputs
        if not indicator_data.indicator_text.strip():
            logger.error("Indicator text cannot be empty")
            raise HTTPException(status_code=400, detail="Indicator text cannot be empty")
        if not indicator_data.substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not indicator_data.strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not indicator_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        
        # For updates, we need either original_indicator_code OR original_indicator_text
        if (not indicator_data.original_indicator_code or not indicator_data.original_indicator_code.strip()) and (not indicator_data.original_indicator_text or not indicator_data.original_indicator_text.strip()):
            logger.error("Either original indicator code or text is required for updates")
            raise HTTPException(status_code=400, detail="Either original indicator code or text is required for updates")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == indicator_data.strand_name,
                Strand.subject == indicator_data.subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        logger.debug(f"Query result for strands: {[(s.id, s.strand_name, s.week_number) for s in strands]}")

        if not strands:
            logger.error(f"No strands found for strand_name: {indicator_data.strand_name}, subject: {indicator_data.subject}")
            raise HTTPException(status_code=404, detail=f"Strand {indicator_data.strand_name} not found")

        # Iterate through strands to find a matching substrand
        substrand = None
        selected_strand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}, week_number: {strand.week_number}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == indicator_data.substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == indicator_data.subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Query result for substrand: {result}")
            if result:
                substrand = result
                selected_strand = strand
                break  # Exit loop once a matching substrand is found

        if not substrand:
            logger.error(f"Substrand {indicator_data.substrand_name} not found for strand_name: {indicator_data.strand_name}, subject: {indicator_data.subject}")
            raise HTTPException(status_code=404, detail=f"Substrand {indicator_data.substrand_name} not found")

        # Find the content standard using a more reliable approach
        # For updates, we'll find the existing indicator first, then get its content standard
        content_standard = None
        
        # Debug logging to see what fields we're receiving
        logger.debug(f"Debug - indicator_data fields: {indicator_data.__dict__}")
        logger.debug(f"Debug - original_indicator_code: {indicator_data.original_indicator_code}")
        logger.debug(f"Debug - original_indicator_text: {indicator_data.original_indicator_text}")
        
        # First, try to find the existing indicator to get its content_standard_id
        existing_indicator = None
        if indicator_data.original_indicator_code:
            logger.debug(f"Looking for indicator with original_code: {indicator_data.original_indicator_code}")
            existing_indicator = (await db.execute(
                select(Indicator).where(
                    Indicator.indicator_code == indicator_data.original_indicator_code,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().first()
        elif indicator_data.original_indicator_text:
            logger.debug(f"Looking for indicator with original_text: {indicator_data.original_indicator_text}")
            existing_indicator = (await db.execute(
                select(Indicator).where(
                    Indicator.indicator_text == indicator_data.original_indicator_text,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if existing_indicator:
            logger.debug(f"Found existing indicator with content_standard_id: {existing_indicator.content_standard_id}")
            # Get the content standard using the existing indicator's content_standard_id
            content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.id == existing_indicator.content_standard_id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Found content standard: {content_standard}")
        else:
            logger.debug("No existing indicator found, falling back to content standard lookup by name/code")
            # Fallback: try to find content standard by name/code
            if indicator_data.content_standard_code:
                logger.debug(f"Fallback to content_standard_code: {indicator_data.content_standard_code}")
                content_standard = (await db.execute(
                    select(ContentStandard).where(
                        ContentStandard.content_standard_code == indicator_data.content_standard_code,
                        ContentStandard.substrand_id == substrand.id,
                        ContentStandard.teacher_id == current_teacher.id
                    )
                )).scalars().first()
            elif indicator_data.content_standard_text:
                logger.debug(f"Fallback to content_standard_text: {indicator_data.content_standard_text}")
                content_standard = (await db.execute(
                    select(ContentStandard).where(
                        ContentStandard.content_standard == indicator_data.content_standard_text,
                        ContentStandard.substrand_id == substrand.id,
                        ContentStandard.teacher_id == current_teacher.id
                    )
                )).scalars().first()
        
        if not content_standard:
            error_msg = f"Content standard not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            if indicator_data.content_standard_code:
                error_msg = f"Content standard {indicator_data.content_standard_code} not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            elif indicator_data.content_standard_text:
                error_msg = f"Content standard with text '{indicator_data.content_standard_text}' not found for substrand: {indicator_data.substrand_name}, strand_id: {selected_strand.id}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Use the existing indicator we already found
        indicator = existing_indicator
        
        if not indicator:
            error_msg = f"Indicator not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            if indicator_data.original_indicator_code:
                error_msg = f"Indicator with code {indicator_data.original_indicator_code} not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            elif indicator_data.original_indicator_text:
                error_msg = f"Indicator with text '{indicator_data.original_indicator_text}' not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        # Check for duplicate indicator_code if changed (only if new code is provided)
        if indicator_data.indicator_code:
            # Get the original code for comparison
            original_code = indicator_data.original_indicator_code
            if original_code and indicator_data.indicator_code != original_code:
                duplicate_indicator = (await db.execute(
                    select(Indicator).where(
                        Indicator.indicator_code == indicator_data.indicator_code,
                        Indicator.content_standard_id == content_standard.id,
                        Indicator.teacher_id == current_teacher.id
                    )
                )).scalars().first()
                if duplicate_indicator:
                    logger.error(f"Indicator code {indicator_data.indicator_code} already exists for content standard {content_standard.content_standard}, content_standard_id: {content_standard.id}")
                    raise HTTPException(status_code=400, detail=f"Indicator code {indicator_data.indicator_code} already exists for this content standard")

        # Check if any sessions are already assigned to other indicators (excluding current indicator)
        if indicator_data.weeks_sessions:
            all_session_ids = []
            for week_sessions in indicator_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            if all_session_ids:
                # Check for sessions already assigned to other indicators
                # Use a more compatible approach that doesn't rely on JSONB overlap
                all_other_indicators = (await db.execute(
                    select(Indicator).where(
                        Indicator.id != indicator.id,  # Exclude current indicator
                        Indicator.teacher_id == current_teacher.id
                    )
                )).scalars().all()
                
                # Check for session conflicts manually
                conflicting_sessions = []
                for other_indicator in all_other_indicators:
                    if other_indicator.session_ids:
                        # Check if any sessions overlap
                        for session_id in all_session_ids:
                            if session_id in other_indicator.session_ids:
                                conflicting_sessions.append(session_id)
                
                if conflicting_sessions:
                    # Get session details for better error message
                    session_details = (await db.execute(
                        select(ClassSession).where(ClassSession.id.in_(conflicting_sessions))
                    )).scalars().all()
                    
                    session_info = [f"{s.date} {s.start_time}-{s.end_time}" for s in session_details]
                    error_msg = f"The following sessions are already assigned to other indicators and cannot be reassigned: {', '.join(session_info)}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=400, detail=error_msg)

        # Update indicator
        indicator.indicator_code = indicator_data.indicator_code.strip() if indicator_data.indicator_code else None
        indicator.indicator_text = indicator_data.indicator_text.strip()
        indicator.updated_at = datetime.utcnow()
        
        # Handle session updates if weeks_sessions is provided
        if indicator_data.weeks_sessions is not None:
            # Extract all session IDs from the weeks_sessions
            all_session_ids = []
            for week_sessions in indicator_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            # Store session IDs
            indicator.session_ids = all_session_ids
            
            # Get session details from ClassSession table
            if all_session_ids:
                session_details = (await db.execute(
                    select(ClassSession).where(ClassSession.id.in_(all_session_ids))
                )).scalars().all()
                
                # Convert to the format expected by the frontend
                # We need to map sessions back to their weeks based on the weeks_sessions input
                # Since ClassSession doesn't have week_number, we calculate it from the input
                weeks_sessions = {}
                for week, session_ids in indicator_data.weeks_sessions.items():
                    week_number = int(week.replace("Week ", ""))
                    # Find sessions that belong to this week
                    week_sessions = [s for s in session_details if s.id in session_ids]
                    if week_sessions:
                        weeks_sessions[week] = [
                            {
                                "id": session.id,
                                "date": str(session.date),
                                "subject": session.subject,
                                "start_time": str(session.start_time),
                                "end_time": str(session.end_time),
                                "class_name": session.class_name,
                                "location": session.location,
                                "week_number": week_number
                            } for session in week_sessions
                        ]
                
                # Flatten all sessions for storage
                indicator.session_details = [session for week_sessions in weeks_sessions.values() for session in week_sessions]
            else:
                # Clear sessions if empty
                indicator.session_ids = []
                indicator.session_details = []

        await db.commit()
        await db.refresh(indicator)

        logger.debug(f"Successfully updated indicator: code={indicator.indicator_code}, content_standard_id: {content_standard.id}")
        
        # Convert session_details back to weeks_sessions format for frontend
        weeks_sessions = None
        if indicator.session_details:
            weeks_sessions = {}
            for session_detail in indicator.session_details:
                week_key = f"Week {session_detail.get('week_number', 1)}"
                if week_key not in weeks_sessions:
                    weeks_sessions[week_key] = []
                weeks_sessions[week_key].append(session_detail)
        
        return IndicatorResponse(
            indicator_code=indicator.indicator_code,
            indicator_text=indicator.indicator_text,
            content_standard_code=content_standard.content_standard_code,
            content_standard_text=content_standard.content_standard,
            substrand_name=substrand.substrand_name,
            strand_name=selected_strand.strand_name,
            subject=indicator.subject,
            teacher_id=indicator.teacher_id,
            weeks_sessions=weeks_sessions,
            created_at=indicator.created_at,
            updated_at=indicator.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating indicator: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating indicator: {str(e)}")


@router.get("/read-indicators", response_model=List[IndicatorResponse])
async def read_indicators(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    subject: str | None = None,
    strand_name: str | None = None,
    substrand_name: str | None = None,
    content_standard_code: str | None = None,
    content_standard_text: str | None = None,
    class_name: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Reading indicators: subject={subject}, strand_name={strand_name}, substrand_name={substrand_name}, content_standard_code={content_standard_code}, content_standard_text={content_standard_text}, teacher_id={current_teacher.id}")
    try:
        query = select(Indicator).where(Indicator.teacher_id == current_teacher.id)
        if subject:
            query = query.where(Indicator.subject == subject)
        
        # If filtering by content standard, strand, or substrand, we need to join with related tables
        if content_standard_code or content_standard_text or strand_name or substrand_name:
            # Start with content standard filtering
            content_standard_query = select(ContentStandard).where(
                ContentStandard.teacher_id == current_teacher.id
            )
            if subject:
                content_standard_query = content_standard_query.where(ContentStandard.subject == subject)
            if content_standard_code:
                content_standard_query = content_standard_query.where(ContentStandard.content_standard_code == content_standard_code)
            if content_standard_text:
                content_standard_query = content_standard_query.where(ContentStandard.content_standard == content_standard_text)
            
            content_standards = (await db.execute(content_standard_query)).scalars().all()
            if not content_standards:
                logger.debug("No content standards found for the specified criteria")
                return []
            
            content_standard_ids = [cs.id for cs in content_standards]
            query = query.where(Indicator.content_standard_id.in_(content_standard_ids))
            
            # If filtering by strand or substrand, we need to filter content standards further
            if strand_name or substrand_name:
                filtered_content_standard_ids = []
                for cs in content_standards:
                    # Get the substrand for this content standard
                    substrand = (await db.execute(
                        select(Substrand).where(Substrand.id == cs.substrand_id)
                    )).scalars().first()
                    if substrand:
                        # Check strand name if specified
                        if strand_name and substrand.strand_id:
                            strand = (await db.execute(
                                select(Strand).where(Strand.id == substrand.strand_id)
                            )).scalars().first()
                            if strand and strand.strand_name != strand_name:
                                continue
                        
                        # Check substrand name if specified
                        if substrand_name and substrand.substrand_name != substrand_name:
                            continue
                        
                        filtered_content_standard_ids.append(cs.id)
                
                if not filtered_content_standard_ids:
                    logger.debug("No content standards found after strand/substrand filtering")
                    return []
                
                query = query.where(Indicator.content_standard_id.in_(filtered_content_standard_ids))

        result = await db.execute(query)
        indicators = result.scalars().all()
        if not indicators:
            logger.debug("No indicators found")
            return []

        # Filter by class_name if provided
        if class_name:
            filtered_indicators = []
            for indicator in indicators:
                # Check if any session in this indicator belongs to the specified class
                indicator_has_class = any(
                    detail.get('class_name') == class_name 
                    for detail in indicator.session_details
                )
                if indicator_has_class:
                    filtered_indicators.append(indicator)
            indicators = filtered_indicators

        response = []
        for indicator in indicators:
            # Get related data for the response
            content_standard = (await db.execute(
                select(ContentStandard).where(ContentStandard.id == indicator.content_standard_id)
            )).scalars().first()
            
            if not content_standard:
                logger.warning(f"Content standard not found for indicator {indicator.id}")
                continue
            
            substrand = (await db.execute(
                select(Substrand).where(Substrand.id == content_standard.substrand_id)
            )).scalars().first()
            
            if not substrand:
                logger.warning(f"Substrand not found for content standard {content_standard.id}")
                continue
            
            strand = (await db.execute(
                select(Strand).where(Strand.id == substrand.strand_id)
            )).scalars().first()
            
            if not strand:
                logger.warning(f"Strand not found for substrand {substrand.id}")
                continue
            
            # Convert session_details back to weeks_sessions format for frontend
            weeks_sessions = None
            if indicator.session_details:
                weeks_sessions = {}
                for session_detail in indicator.session_details:
                    week_key = f"Week {session_detail.get('week_number', 1)}"
                    if week_key not in weeks_sessions:
                        weeks_sessions[week_key] = []
                    weeks_sessions[week_key].append(session_detail)
            
            response.append(IndicatorResponse(
                indicator_code=indicator.indicator_code,
                indicator_text=indicator.indicator_text,
                content_standard_code=content_standard.content_standard_code,
                content_standard_text=content_standard.content_standard,
                substrand_name=substrand.substrand_name,
                strand_name=strand.strand_name,
                subject=indicator.subject,
                teacher_id=indicator.teacher_id,
                weeks_sessions=weeks_sessions,
                created_at=indicator.created_at,
                updated_at=indicator.updated_at
            ))

        logger.debug(f"Returning {len(response)} indicators")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading indicators: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading indicators: {str(e)}")
    
@router.delete("/delete-indicator", status_code=status.HTTP_204_NO_CONTENT)
async def delete_indicator(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    indicator_code: str | None = None,
    indicator_text: str | None = None,
    content_standard_code: str | None = None,
    content_standard_text: str | None = None,
    substrand_name: str | None = None,
    strand_name: str | None = None,
    subject: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting indicator: code={indicator_code}, text={indicator_text}, content_standard_code={content_standard_code}, content_standard_text={content_standard_text}, substrand_name={substrand_name}, strand_name={strand_name}, subject={subject}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs - we need at least one identifier
        if not indicator_code and not indicator_text:
            logger.error("Either indicator_code or indicator_text is required")
            raise HTTPException(status_code=400, detail="Either indicator_code or indicator_text is required")
        
        if not substrand_name or not strand_name or not subject:
            logger.error("Substrand name, strand name, and subject are required")
            raise HTTPException(status_code=400, detail="Substrand name, strand name, and subject are required")

        # Find the content standard first
        content_standard = None
        if content_standard_code:
            content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_code,
                    ContentStandard.subject == subject,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        elif content_standard_text:
            content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard == content_standard_text,
                    ContentStandard.subject == subject,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if not content_standard:
            error_msg = f"Content standard not found for substrand: {substrand_name}, strand: {strand_name}, subject: {subject}"
            if content_standard_code:
                error_msg = f"Content standard {content_standard_code} not found for substrand: {substrand_name}, strand: {strand_name}, subject: {subject}"
            elif content_standard_text:
                error_msg = f"Content standard with text '{content_standard_text}' not found for substrand: {substrand_name}, strand: {strand_name}, subject: {subject}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Find the indicator to delete
        indicator = None
        if indicator_code:
            indicator = (await db.execute(
                select(Indicator).where(
                    Indicator.indicator_code == indicator_code,
                    Indicator.content_standard_id == content_standard.id,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().first()
        elif indicator_text:
            indicator = (await db.execute(
                select(Indicator).where(
                    Indicator.indicator_text == indicator_text,
                    Indicator.content_standard_id == content_standard.id,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if not indicator:
            error_msg = f"Indicator not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            if indicator_code:
                error_msg = f"Indicator with code {indicator_code} not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            elif indicator_text:
                error_msg = f"Indicator with text '{indicator_text}' not found for content standard: {content_standard.content_standard or content_standard.content_standard_code}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Delete the indicator
        await db.delete(indicator)
        await db.commit()
        
        logger.debug(f"Successfully deleted indicator: id={indicator.id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting indicator: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting indicator: {str(e)}")
    
@router.put("/update-content-standard", response_model=ContentStandardResponse, status_code=status.HTTP_200_OK)
async def update_content_standard(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    content_standard_data: ContentStandardUpdate,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Updating content standard: code={content_standard_data.content_standard_code}, substrand_name={content_standard_data.substrand_name}, strand_name={content_standard_data.strand_name}, subject={content_standard_data.subject}, teacher_id={current_teacher.id}, original_code={content_standard_data.original_content_standard_code}, original_text={content_standard_data.original_content_standard_text}, new_text={content_standard_data.content_standard}")
    try:
        # Validate inputs
        if not content_standard_data.content_standard.strip():
            logger.error("Content standard description cannot be empty")
            raise HTTPException(status_code=400, detail="Content standard description cannot be empty")
        if not content_standard_data.substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not content_standard_data.strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not content_standard_data.subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")
        # For updates, we need either original_content_standard_code OR original_content_standard_text
        if (not content_standard_data.original_content_standard_code or not content_standard_data.original_content_standard_code.strip()) and (not content_standard_data.original_content_standard_text or not content_standard_data.original_content_standard_text.strip()):
            logger.error("Either original content standard code or text is required for updates")
            raise HTTPException(status_code=400, detail="Either original content standard code or text is required for updates")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == content_standard_data.strand_name,
                Strand.subject == content_standard_data.subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        if not strands:
            logger.error(f"No strands found for strand_name: {content_standard_data.strand_name}, subject: {content_standard_data.subject}")
            raise HTTPException(status_code=404, detail=f"Strand {content_standard_data.strand_name} not found")

        # Find the substrand and track the associated strand
        substrand = None
        selected_strand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == content_standard_data.substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == content_standard_data.subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            if result:
                substrand = result
                selected_strand = strand
                break

        if not substrand:
            logger.error(f"Substrand {content_standard_data.substrand_name} not found for strand_name: {content_standard_data.strand_name}")
            raise HTTPException(status_code=404, detail=f"Substrand {content_standard_data.substrand_name} not found")

        # Find the existing content standard using either original_content_standard_code or original_content_standard_text
        content_standard = None
        if content_standard_data.original_content_standard_code:
           logger.debug(f"Looking for content standard with code: {content_standard_data.original_content_standard_code}")
           content_standard = (await db.execute(
            select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_data.original_content_standard_code,
                ContentStandard.substrand_id == substrand.id,
                ContentStandard.teacher_id == current_teacher.id
            )
        )).scalars().first()
        elif content_standard_data.original_content_standard_text:
             logger.debug(f"Looking for content standard with text: '{content_standard_data.original_content_standard_text}'")
             content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard == content_standard_data.original_content_standard_text,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if content_standard:
            logger.debug(f"Found content standard: id={content_standard.id}, code='{content_standard.content_standard_code}', text='{content_standard.content_standard}'")
        else:
            logger.debug("No content standard found in database")
        
        if not content_standard:
            error_msg = f"Content standard not found for substrand: {content_standard_data.substrand_name}, strand_id: {selected_strand.id}"
            if content_standard_data.original_content_standard_code:
                error_msg = f"Content standard {content_standard_data.original_content_standard_code} not found for substrand: {content_standard_data.substrand_name}, strand_id: {selected_strand.id}"
            elif content_standard_data.original_content_standard_text:
                error_msg = f"Content standard with text '{content_standard_data.original_content_standard_text}' not found for substrand: {content_standard_data.substrand_name}, strand_id: {selected_strand.id}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Check for duplicate code if changed (only if new code is provided)
        if content_standard_data.content_standard_code:
            # Get the original code for comparison
            original_code = content_standard_data.original_content_standard_code
            if original_code and content_standard_data.content_standard_code != original_code:
                # FIXED: Check for duplicate code but EXCLUDE the current record being updated
                existing_code = (await db.execute(
                    select(ContentStandard).where(
                        ContentStandard.content_standard_code == content_standard_data.content_standard_code,
                        ContentStandard.substrand_id == substrand.id,
                        ContentStandard.teacher_id == current_teacher.id,
                        ContentStandard.id != content_standard.id  # EXCLUDE current record
                    )
                )).scalars().first()
                if existing_code:
                    logger.error(f"Content standard code {content_standard_data.content_standard_code} already exists for substrand {content_standard_data.substrand_name}")
                    raise HTTPException(status_code=400, detail=f"Content standard code {content_standard_data.content_standard_code} already exists for this substrand")
            else:
                # No original code, so check if the new code already exists
                # FIXED: Check for duplicate code but EXCLUDE the current record being updated
                existing_code = (await db.execute(
                    select(ContentStandard).where(
                        ContentStandard.content_standard_code == content_standard_data.content_standard_code,
                        ContentStandard.substrand_id == substrand.id,
                        ContentStandard.teacher_id == current_teacher.id,
                        ContentStandard.id != content_standard.id  # EXCLUDE current record
                    )
                )).scalars().first()
                if existing_code:
                    logger.error(f"Content standard code {content_standard_data.content_standard_code} already exists for substrand {content_standard_data.substrand_name}")
                    raise HTTPException(status_code=400, detail=f"Content standard code {content_standard_data.content_standard_code} already exists for this substrand")

        # Update content standard
        content_standard.content_standard_code = content_standard_data.content_standard_code.strip() if content_standard_data.content_standard_code else None
        content_standard.content_standard = content_standard_data.content_standard.strip()
        content_standard.updated_at = datetime.utcnow()
        
        # Handle session updates if weeks_sessions is provided
        if content_standard_data.weeks_sessions is not None:
            # Extract all session IDs from the weeks_sessions
            all_session_ids = []
            for week_sessions in content_standard_data.weeks_sessions.values():
                all_session_ids.extend(week_sessions)
            
            # Store session IDs
            content_standard.session_ids = all_session_ids
            
            # Get session details from ClassSession table
            if all_session_ids:
                session_details = (await db.execute(
                    select(ClassSession).where(ClassSession.id.in_(all_session_ids))
                )).scalars().all()
                
                # Convert to the format expected by the frontend
                # We need to map sessions back to their weeks based on the weeks_sessions input
                # Since ClassSession doesn't have week_number, we calculate it from the input
                weeks_sessions = {}
                for week, session_ids in content_standard_data.weeks_sessions.items():
                    week_number = int(week.replace("Week ", ""))
                    # Find sessions that belong to this week
                    week_sessions = [s for s in session_details if s.id in session_ids]
                    if week_sessions:
                        weeks_sessions[week] = [
                            {
                                "id": session.id,
                                "date": str(session.date),
                                "subject": session.subject,
                                "start_time": str(session.start_time),
                                "end_time": str(session.end_time),
                                "class_name": session.class_name,
                                "location": session.location,
                                "week_number": week_number
                            } for session in week_sessions
                        ]
                
                # Flatten all sessions for storage
                content_standard.session_details = [session for week_sessions in weeks_sessions.values() for session in week_sessions]
            else:
                # Clear sessions if empty
                content_standard.session_ids = []
                content_standard.session_details = []

        await db.commit()
        await db.refresh(content_standard)

        # Verify no duplicate records remain (only if we had an original code)
        if content_standard_data.original_content_standard_code:
            # FIXED: Check for duplicates but EXCLUDE the current record being updated
            duplicate_check = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_data.original_content_standard_code,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id,
                    ContentStandard.id != content_standard.id  # EXCLUDE current record
                )
            )).scalars().all()
            if len(duplicate_check) > 0:
                logger.warning(f"Duplicate content standard found for code {content_standard_data.original_content_standard_code}, substrand_id: {substrand.id}. This should not happen.")
        else:
            # If there was no original code, verify the new code is unique
            if content_standard_data.content_standard_code:
                # FIXED: Check for duplicates but EXCLUDE the current record being updated
                duplicate_check = (await db.execute(
                    select(ContentStandard).where(
                        ContentStandard.content_standard_code == content_standard_data.content_standard_code,
                        ContentStandard.substrand_id == substrand.id,
                        ContentStandard.teacher_id == current_teacher.id,
                        ContentStandard.id != content_standard.id  # EXCLUDE current record
                    )
                )).scalars().all()
                if len(duplicate_check) > 1:  # Should be exactly 1 (the one we just updated)
                    logger.warning(f"Multiple content standards found for code {content_standard_data.content_standard_code}, substrand_id: {substrand.id}. This should not happen.")

        logger.debug(f"Successfully updated content standard: code={content_standard.content_standard_code}, substrand_id: {substrand.id}")
        
        # Convert session_details back to weeks_sessions format for frontend
        weeks_sessions = None
        if content_standard.session_details:
            weeks_sessions = {}
            for session_detail in content_standard.session_details:
                week_key = f"Week {session_detail.get('week_number', 1)}"
                if week_key not in weeks_sessions:
                    weeks_sessions[week_key] = []
                weeks_sessions[week_key].append(session_detail)
        
        return ContentStandardResponse(
            content_standard_code=content_standard.content_standard_code,
            content_standard=content_standard.content_standard,
            substrand_name=substrand.substrand_name,
            strand_name=selected_strand.strand_name,
            subject=content_standard.subject,
            teacher_id=content_standard.teacher_id,
            weeks_sessions=weeks_sessions,
            created_at=content_standard.created_at,
            updated_at=content_standard.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating content standard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating content standard: {str(e)}")


@router.delete("/delete-content-standard", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_standard(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    substrand_name: str,
    strand_name: str,
    subject: str,
    content_standard_code: str | None = None,
    content_standard_text: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    logger.debug(f"Deleting content standard: code={content_standard_code}, text={content_standard_text}, substrand_name={substrand_name}, strand_name={strand_name}, subject={subject}, teacher_id={current_teacher.id}")
    try:
        # Validate inputs - we need either content_standard_code OR content_standard_text
        if (not content_standard_code or not content_standard_code.strip()) and (not content_standard_text or not content_standard_text.strip()):
            logger.error("Either content standard code or text is required")
            raise HTTPException(status_code=400, detail="Either content standard code or text is required")
        if not substrand_name.strip():
            logger.error("Substrand name cannot be empty")
            raise HTTPException(status_code=400, detail="Substrand name cannot be empty")
        if not strand_name.strip():
            logger.error("Strand name cannot be empty")
            raise HTTPException(status_code=400, detail="Strand name cannot be empty")
        if not subject.strip():
            logger.error("Subject cannot be empty")
            raise HTTPException(status_code=400, detail="Subject cannot be empty")

        # Find all strands matching the strand_name, subject, and teacher_id
        strands = (await db.execute(
            select(Strand).where(
                Strand.strand_name == strand_name,
                Strand.subject == subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().all()
        logger.debug(f"Query result for strands: {[(s.id, s.strand_name, s.week_number) for s in strands]}")

        if not strands:
            logger.error(f"No strands found for strand_name: {strand_name}, subject: {subject}")
            raise HTTPException(status_code=404, detail=f"Strand {strand_name} not found")

        # Iterate through strands to find a matching substrand
        substrand = None
        for strand in strands:
            logger.debug(f"Checking strand with id: {strand.id}, week_number: {strand.week_number}")
            result = (await db.execute(
                select(Substrand).where(
                    Substrand.substrand_name == substrand_name,
                    Substrand.strand_id == strand.id,
                    Substrand.subject == subject,
                    Substrand.teacher_id == current_teacher.id
                )
            )).scalars().first()
            logger.debug(f"Query result for substrand: {result}")
            if result:
                substrand = result
                break  # Exit loop once a matching substrand is found

        if not substrand:
            logger.error(f"Substrand {substrand_name} not found for strand_name: {strand_name}, subject: {subject}")
            raise HTTPException(status_code=404, detail=f"Substrand {substrand_name} not found")

        # Find the content standard by either code or text
        content_standard = None
        if content_standard_code:
           content_standard = (await db.execute(
            select(ContentStandard).where(
                ContentStandard.content_standard_code == content_standard_code,
                ContentStandard.substrand_id == substrand.id,
                ContentStandard.teacher_id == current_teacher.id
            )
        )).scalars().first()
        elif content_standard_text:
             content_standard = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard == content_standard_text,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
                )
            )).scalars().first()
        
        if not content_standard:
            error_msg = f"Content standard not found for substrand {substrand_name}, substrand_id: {substrand.id}"
            if content_standard_code:
                error_msg = f"Content standard {content_standard_code} not found for substrand {substrand_name}, substrand_id: {substrand.id}"
            elif content_standard_text:
                error_msg = f"Content standard with text '{content_standard_text}' not found for substrand {substrand_name}, substrand_id: {substrand.id}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        # Delete associated indicators first
        try:
            indicators = (await db.execute(
                select(Indicator).where(
                    Indicator.content_standard_id == content_standard.id,
                    Indicator.teacher_id == current_teacher.id
                )
            )).scalars().all()
            
            if indicators:
                logger.debug(f"Found {len(indicators)} indicators to delete for content standard {content_standard.id}")
                for indicator in indicators:
                    await db.delete(indicator)
                    logger.debug(f"Deleted indicator {indicator.id} ({indicator.indicator_text})")
                
                # Commit indicator deletions first to satisfy foreign key constraints
                await db.commit()
                logger.debug("Successfully committed indicator deletions")
            else:
                logger.debug(f"No indicators found for content standard {content_standard.id}")
        except Exception as e:
            logger.error(f"Error deleting indicators for content standard {content_standard.id}: {str(e)}")
            await db.rollback()
            raise

        # Now delete the content standard
        try:
            await db.delete(content_standard)
            await db.commit()
            logger.debug(f"Successfully deleted content standard {content_standard.id}")
        except Exception as e:
            logger.error(f"Error deleting content standard {content_standard.id}: {str(e)}")
            await db.rollback()
            raise
        
        # Log the successful deletion with appropriate identifier
        if content_standard_code:
           logger.info(f"Successfully deleted content standard: code={content_standard_code}, substrand_id: {substrand.id}")
        elif content_standard_text:
            logger.info(f"Successfully deleted content standard: text='{content_standard_text}', substrand_id: {substrand.id}")
        
        logger.info(f"Content standard deletion completed successfully. Deleted {len(indicators) if indicators else 0} indicators.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting content standard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting content standard: {str(e)}")
