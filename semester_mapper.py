from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Dict
from pydantic import BaseModel, Field
from model import TeacherProfile, AcademicCalendar, ClassSession, Strand, Substrand, ContentStandard
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

    # Handle strand renaming: if original_strand_name is provided and different, delete old strands
    if strand_data.original_strand_name and strand_data.original_strand_name.strip() != strand_data.strand_name.strip():
        old_strands_to_delete_query = select(Strand).where(
            Strand.strand_name == strand_data.original_strand_name.strip(),
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        )
        await db.execute(delete(Strand).where(
            Strand.strand_name == strand_data.original_strand_name.strip(),
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        ))
        await db.commit() # Commit the deletion immediately
        existing_strands = [] # No existing strands to update, will create new ones
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

        # Delete strands for weeks that are no longer part of the updated weeks_sessions
        for strand in existing_strands:
            if strand.week_number in weeks_to_delete:
                await db.delete(strand)
        await db.commit() # Commit deletion of old weeks immediately

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

        # Delete all matching strands
        for strand in strands:
            await db.delete(strand)

        await db.commit()
        logger.debug(f"Successfully deleted strand: strand_name={strand_name}, subject={subject}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strand: {str(e)}")
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

    # Delete substrands for weeks that are no longer part of the updated weeks_sessions
    for substrand in existing_substrands:
        if substrand.substrand_name == substrand_to_query and any(week in weeks_to_delete for week in substrand.week_numbers):
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

        # Delete associated content standards
        content_standards = (await db.execute(
            select(ContentStandard).where(
                ContentStandard.substrand_id == substrand.id,
                ContentStandard.teacher_id == current_teacher.id
            )
        )).scalars().all()
        for cs in content_standards:
            logger.debug(f"Deleting content standard: code={cs.content_standard_code}, substrand_id={substrand.id}")
            await db.delete(cs)

        # Delete the substrand
        await db.delete(substrand)
        await db.commit()
        logger.debug(f"Successfully deleted substrand: {substrand_name}, substrand_id: {substrand.id}")
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
            
            # Convert session_details back to weeks_sessions format for frontend
            weeks_sessions = None
            if cs.session_details:
                weeks_sessions = {}
                for session_detail in cs.session_details:
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
               existing_code = (await db.execute(
                select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_data.content_standard_code,
                    ContentStandard.substrand_id == substrand.id,
                    ContentStandard.teacher_id == current_teacher.id
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
           duplicate_check = (await db.execute(
            select(ContentStandard).where(
                    ContentStandard.content_standard_code == content_standard_data.original_content_standard_code,
                ContentStandard.substrand_id == substrand.id,
                ContentStandard.teacher_id == current_teacher.id
            )
        )).scalars().all()
           if len(duplicate_check) > 0:
                logger.warning(f"Duplicate content standard found for code {content_standard_data.original_content_standard_code}, substrand_id: {substrand.id}. This should not happen.")

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

        await db.delete(content_standard)
        await db.commit()
        
        # Log the successful deletion with appropriate identifier
        if content_standard_code:
           logger.debug(f"Successfully deleted content standard: code={content_standard_code}, substrand_id: {substrand.id}")
        elif content_standard_text:
            logger.debug(f"Successfully deleted content standard: text='{content_standard_text}', substrand_id: {substrand.id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting content standard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting content standard: {str(e)}")
