from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from uuid import UUID
import os
from app.core.logger import logger
from app.core.database import get_db
from typing import Annotated, Optional
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile, WeeklyTimeTable, KnowledgeMetadata, Strand, AcademicCalendar, ClassSession
from app.core.config import settings
from app.services.gcs_utils import generate_signed_url, generate_file_name, get_file_from_gcs
import asyncio
import uuid
from datetime import datetime
from app.semplan_ground.semplan_back import enqueue_semplan_processing  # Keep import for semester plan processing

# Import curriculum background processing
try:
    from app.curri_back.enqueue_curri import enqueue_curriculum_processing
    CURRI_PROCESSING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Curriculum processing not available: {e}")
    CURRI_PROCESSING_AVAILABLE = False

router = APIRouter(tags=["Curriculum File Handler"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/curriculum/upload")
async def upload_curriculum(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    subject: str = Form(...),  # Add subject parameter
    class_name: str = Form(...),  # Add class_name parameter
    education_system: str = Form(...),  # Add education_system parameter (required)
    education_level: str = Form(...),  # Add education_level parameter (required)
    country_name: Optional[str] = Form(None),  # Add optional country_name parameter
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    session: AsyncSession = Depends(get_db)
):
    """
    Upload curriculum file endpoint.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing curriculum upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        logger.info(f"📚 Subject: {subject}, Class: {class_name}")
        logger.info(f"🏫 Education System: {education_system}, Education Level: {education_level}")
        
        # Validate file type
        if not file_name:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls', 'txt', 'pptx', 'ppt']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Generate file name for GCS in the format: curriculum/teacher_id/class_name/subject.extension
        gcs_file_name = f"curriculum/{teacher_id}/{class_name}/{subject}.{file_ext}"
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Use the content_type from the uploaded file or default to application/octet-stream
        content_type = file_type if file_type else "application/octet-stream"
        logger.info(f"🏷️ File content type: {content_type}")
        
        # Update existing WeeklyTimeTable entries for this subject and class with the new education system and level
        # This ensures the data is overwritten each time a new file is uploaded
        stmt = (
            WeeklyTimeTable.__table__.update()
            .where(WeeklyTimeTable.teacher_id == UUID(teacher_id))
            .where(WeeklyTimeTable.subject == subject)
            .where(WeeklyTimeTable.pupils == class_name)
            .values(edu_sys=education_system, edu_lvl=education_level)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"✅ Updated WeeklyTimeTable entries with education system: {education_system}, education level: {education_level}")
        
        # Check for existing KnowledgeMetadata records to prevent duplicates
        # Use pillar and file_path for duplicate detection as per project specifications
        filename_without_ext = os.path.splitext(file_name)[0] if file_name else ""
        knowledge_id = None  # Initialize knowledge_id
        if filename_without_ext:
            logger.info(f"🔍 Checking for duplicate KnowledgeMetadata records for file: {file_name}")
            
            # Search for existing records with same teacher_id, subject, level, pillar, and file path pattern
            result = await session.execute(
                select(KnowledgeMetadata).where(
                    and_(
                        KnowledgeMetadata.teacher_id == UUID(teacher_id),
                        KnowledgeMetadata.subject == subject,
                        KnowledgeMetadata.level == class_name,
                        KnowledgeMetadata.pillar == "curriculum",
                        or_(
                            KnowledgeMetadata.file_path.ilike(f"%{filename_without_ext}%"),
                            KnowledgeMetadata.notes == filename_without_ext,
                            KnowledgeMetadata.notes.ilike(f"{filename_without_ext}%")
                        )
                    )
                )
            )
            existing_records = result.scalars().all()
            
            if existing_records:
                logger.info(f"⚠️ Found {len(existing_records)} existing KnowledgeMetadata record(s) for this file")
                # Use the first existing record instead of creating a new one
                knowledge_record = existing_records[0]
                knowledge_id = knowledge_record.id
                
                # Update the existing record with new information
                knowledge_record.teacher_id = UUID(teacher_id)
                knowledge_record.uploader_type = "teacher"
                knowledge_record.subject = subject
                knowledge_record.level = class_name
                knowledge_record.region = country_name
                knowledge_record.pillar = "curriculum"
                knowledge_record.file_path = gcs_file_name
                
                # OPTIMIZATION: Check if already embedded to avoid re-processing
                if knowledge_record.is_embedded:
                    logger.info(f"⏭️ File already embedded (is_embedded=True). Skipping re-processing status reset.")
                    # Keep is_embedded as True, so poller WON'T pick it up again
                else:
                    logger.info(f"🔄 File not yet embedded (is_embedded=False). Ensuring it gets processed.")
                    knowledge_record.is_embedded = False
                
                knowledge_record.notes = file_name
                knowledge_record.created_at = datetime.utcnow()
                
                session.add(knowledge_record)
                await session.commit()
                await session.refresh(knowledge_record)
                
                logger.info(f"✅ Updated existing KnowledgeMetadata record with ID: {knowledge_id}")
            else:
                # Create new KnowledgeMetadata entry before generating signed URLs
                knowledge_record = KnowledgeMetadata(
                    teacher_id=UUID(teacher_id),
                    uploader_type="teacher",
                    subject=subject,
                    level=class_name,
                    region=country_name,
                    pillar="curriculum",
                    file_path=gcs_file_name,
                    is_embedded=False,
                    notes=file_name
                )
                
                session.add(knowledge_record)
                await session.commit()
                await session.refresh(knowledge_record)
                
                knowledge_id = knowledge_record.id
                logger.info(f"✅ Created new KnowledgeMetadata record with ID: {knowledge_id}")
        else:
            # Create new KnowledgeMetadata entry before generating signed URLs (fallback)
            knowledge_record = KnowledgeMetadata(
                teacher_id=UUID(teacher_id),
                uploader_type="teacher",
                subject=subject,
                level=class_name,
                region=country_name,
                pillar="curriculum",
                file_path=gcs_file_name,
                is_embedded=False,
                notes=file_name
            )
            
            session.add(knowledge_record)
            await session.commit()
            await session.refresh(knowledge_record)
            
            knowledge_id = knowledge_record.id
            logger.info(f"✅ Created new KnowledgeMetadata record with ID: {knowledge_id}")
        
        # Generate signed URL for frontend to upload to GCS with correct content type
        # For file uploads, we need to use PUT method
        # Increase expiration time to 24 hours (86400 seconds) to prevent expiration issues
        signed_url_primary = generate_signed_url(
            settings.GCS_BUCKET_NAME, 
            gcs_file_name, 
            method="PUT",
            content_type=content_type,
            expiration=86400  # 24 hours
        )
        logger.info(f"🔗 Generated primary signed URL for GCS upload")
        
        # Check if strands already exist for this teacher, subject, and class
        # If strands exist, there's already a semester plan - skip immediate processing
        # If no strands exist, we need to create a semester plan from the curriculum
        strands_result = await session.execute(
            select(Strand).where(
                and_(
                    Strand.teacher_id == UUID(teacher_id),
                    Strand.subject == subject,
                    Strand.class_name == class_name
                )
            ).limit(1)
        )
        existing_strand = strands_result.scalar_one_or_none()
        
        processing_status = "deferred"  # Default: leave for scheduler
        job_id = None
        
        if existing_strand:
            logger.info(f"✅ Strands already exist for {subject} - {class_name}. Leaving file for scheduler processing.")
            processing_status = "deferred"
        elif CURRI_PROCESSING_AVAILABLE:
            logger.info(f"⚠️ No strands found for {subject} - {class_name}. Enqueueing for immediate processing.")
            
            # Gather session data for the AI processing (same format as semplan implementation)
            session_data = None
            try:
                # Get academic calendar
                calendar_result = await session.execute(
                    select(AcademicCalendar).where(AcademicCalendar.teacher_id == UUID(teacher_id))
                )
                calendar = calendar_result.scalar_one_or_none()
                
                if calendar:
                    semester_start_date = calendar.semester_start_date
                    semester_end_date = calendar.semester_end_date
                    
                    # Get class sessions for this subject and class (using ilike for flexible matching like semplan)
                    sessions_result = await session.execute(
                        select(ClassSession).where(
                            and_(
                                ClassSession.teacher_id == UUID(teacher_id),
                                ClassSession.subject.ilike(f"%{subject}%"),
                                ClassSession.class_name.ilike(f"%{class_name}%")
                            )
                        ).order_by(ClassSession.date, ClassSession.start_time)
                    )
                    class_sessions = sessions_result.scalars().all()
                    
                    logger.info(f"📅 Found {len(class_sessions)} class sessions for {subject} - {class_name}")
                    
                    if class_sessions:
                        # Build weekly_sessions structure (exactly like semplan implementation)
                        weekly_sessions = {}
                        for cs in class_sessions:
                            # Calculate week number from session date
                            if semester_start_date and cs.date:
                                days_diff = (cs.date - semester_start_date).days
                                week_num = (days_diff // 7) + 1
                                
                                # Ensure week number is within valid range (1-16)
                                if 1 <= week_num <= 16:
                                    week_key = f"Week {week_num}"
                                    
                                    if week_key not in weekly_sessions:
                                        weekly_sessions[week_key] = {
                                            "week_number": week_num,
                                            "sessions": []
                                        }
                                    
                                    # Create session info with only essential fields (same as semplan)
                                    weekly_sessions[week_key]["sessions"].append({
                                        "id": cs.id,
                                        "date": str(cs.date),
                                        "start_time": str(cs.start_time),
                                        "end_time": str(cs.end_time),
                                        "week_number": week_num
                                    })
                        
                        # Build session_data in the same format as semplan
                        session_data = {
                            "semester_start_date": str(semester_start_date),
                            "semester_end_date": str(semester_end_date),
                            "weekly_sessions": weekly_sessions
                        }
                        logger.info(f"📅 Built session data with {len(weekly_sessions)} weeks (semplan format)")
                        
                        # Log which weeks we have
                        week_numbers = list(weekly_sessions.keys())
                        logger.info(f"📅 Weeks available: {week_numbers}")
                    else:
                        logger.warning(f"⚠️ No class sessions found for {subject} - {class_name}")
                else:
                    logger.warning(f"⚠️ No academic calendar found for teacher {teacher_id}")
            except Exception as session_err:
                logger.error(f"❌ Error gathering session data: {session_err}")
            
            # Enqueue for immediate processing with 60 second delay (to allow file upload to complete)
            try:
                job = await enqueue_curriculum_processing(
                    teacher_id=teacher_id,
                    gcs_file_name=gcs_file_name,
                    subject=subject,
                    class_name=class_name,
                    session_data=session_data,
                    knowledge_id=knowledge_id,
                    education_system=education_system,  # Pass from endpoint
                    education_level=education_level,    # Pass from endpoint
                    delay=60  # 60 second delay to allow file upload to complete
                )
                if job:
                    job_id = job.job_id
                    processing_status = "enqueued"
                    logger.info(f"✅ Curriculum processing enqueued with job ID: {job_id}")
                else:
                    processing_status = "enqueue_failed"
                    logger.error(f"❌ Failed to enqueue curriculum processing")
            except Exception as enqueue_err:
                logger.error(f"❌ Error enqueueing curriculum processing: {enqueue_err}")
                processing_status = "enqueue_failed"
        else:
            logger.info(f"⏰ Curriculum processing not available. Leaving for scheduler.")
            processing_status = "deferred"
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_urls": {
                "primary": signed_url_primary
            },
            "gcs_file_names": {
                "primary": gcs_file_name
            },
            "content_type": content_type,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "education_system": education_system,
            "education_level": education_level,
            "knowledge_id": str(knowledge_id),
            "processing_status": processing_status,
            "job_id": job_id,
            "note": "Use the signed_url to upload your file directly to Google Cloud Storage." + (
                " Semester plan processing has been enqueued and will begin shortly." if processing_status == "enqueued" 
                else " Processing will be handled by the background scheduler."
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Curriculum upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")