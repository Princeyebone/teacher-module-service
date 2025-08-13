from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from model import TeacherProfile, AcademicCalendar, ClassSession, Strand, Substrand
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import select, delete
import uuid
from uuid import UUID
from typing import List
from fastapi import HTTPException
from datetime import timedelta, date
from schemas import StrandCreate, StrandResponse, SessionDetail, StrandUpdate, SubstrandResponse, SubstrandCreate, SubstrandUpdate
import logging
from datetime import datetime

router = APIRouter(tags=["Semester Mapper"])

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    if strand_data.original_strand_name and strand_data.original_strand_name != strand_data.strand_name:
        old_strands_to_delete_query = select(Strand).where(
            Strand.strand_name == strand_data.original_strand_name,
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        )
        await db.execute(delete(Strand).where(
            Strand.strand_name == strand_data.original_strand_name,
            Strand.subject == strand_data.subject,
            Strand.teacher_id == teacher_id
        ))
        existing_strands = [] # No existing strands to update, will create new ones
    else:
        # Fetch existing strands for the teacher, strand_name, and subject
        existing_strands_query = select(Strand).where(
            Strand.strand_name == strand_data.strand_name,
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
            strand.strand_name = strand_data.strand_name
            strand.session_ids = session_ids
            strand.session_details = session_details
            strand.updated_at = datetime.utcnow()
        else:
            strand = Strand(
                strand_name=strand_data.strand_name,
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
            strand_name=strand.strand_name,
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
    db: AsyncSession = Depends(get_db)
):
    teacher_id = current_teacher.id
    query = select(Strand).where(Strand.teacher_id == teacher_id)
    if subject:
        query = query.where(Strand.subject == subject)
    
    result = await db.execute(query)
    strands = result.scalars().all()

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
        # Find the strand
        strand = (await db.execute(
            select(Strand).where(
                Strand.strand_name == strand_name,
                Strand.subject == subject,
                Strand.teacher_id == current_teacher.id
            )
        )).scalars().first()
        if not strand:
            logger.error(f"Strand {strand_name} not found for subject {subject}")
            raise HTTPException(status_code=404, detail=f"Strand {strand_name} not found")

        # Query for substrands
        query = select(Substrand).where(
            Substrand.substrand_name == substrand_name,
            Substrand.subject == subject,
            Substrand.strand_id == strand.id,
            Substrand.teacher_id == current_teacher.id
        )
        result = await db.execute(query)
        substrands = result.scalars().all()

        if not substrands:
            logger.error(f"Substrand {substrand_name} not found for strand {strand_name} and subject {subject}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Substrand {substrand_name} not found"
            )

        # Delete all matching substrands
        for substrand in substrands:
            await db.delete(substrand)

        await db.commit()
        logger.debug(f"Successfully deleted substrand: {substrand_name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting substrand: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting substrand: {str(e)}"
        )