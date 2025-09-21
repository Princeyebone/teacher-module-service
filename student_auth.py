from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import func
from model import Student, TeacherProfile, StudentEnrollment
from schemas import StudentTokenData, StudentRegistrationRequest, StudentPasswordChangeRequest, StudentProfileResponse, PaginatedStudentResponse, StudentRegistrationResponse, StudentEnrollmentResponse
from config import settings
from fastapi import APIRouter, UploadFile, HTTPException, Depends, status, Query
from logger import logger
from database import get_db
from dependencies import get_current_teacher, get_current_student
import csv
import io
import secrets
import string
from pydantic import EmailStr

# Create router for student management endpoints
router = APIRouter(tags=["Student Management"])

# Password hashing context
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using Argon2"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES or 30)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # Refresh token valid for 7 days
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def authenticate_student(email: str, password: str, db: AsyncSession) -> Optional[Student]:
    """Authenticate a student by email and password"""
    logger.info(f"Attempting to authenticate student with email: {email}")
    
    statement = select(Student).where(Student.email == email)
    result = await db.execute(statement)
    student = result.scalar_one_or_none()
    
    if not student:
        logger.warning(f"No student found with email: {email}")
        return None
    
    if not verify_password(password, student.hashed_password):
        logger.warning(f"Invalid password for student with email: {email}")
        return None
    
    logger.info(f"Student authenticated successfully: {email}")
    return student

async def authenticate_student_by_id(index_number: str, password: str, db: AsyncSession) -> Optional[Student]:
    """Authenticate a student by index number and password"""
    logger.info(f"Attempting to authenticate student with index number: {index_number}")
    
    try:
        statement = select(Student).where(Student.index_number == index_number)
        result = await db.execute(statement)
        student = result.scalar_one_or_none()
        
        if not student:
            logger.warning(f"No student found with index number: {index_number}")
            return None
        
        if not verify_password(password, student.hashed_password):
            logger.warning(f"Invalid password for student with index_number: {index_number}")
            return None
        
        logger.info(f"Student authenticated successfully: {index_number}")
        return student
    except Exception as e:
        logger.error(f"Error authenticating student with index_number {index_number}: {str(e)}")
        return None

async def get_student_by_id(student_id: UUID, db: AsyncSession) -> Optional[Student]:
    """Get a student by ID"""
    statement = select(Student).where(Student.id == student_id)
    result = await db.execute(statement)
    return result.scalar_one_or_none()

async def get_student_by_email(email: str, db: AsyncSession) -> Optional[Student]:
    """Get a student by email"""
    statement = select(Student).where(Student.email == email)
    result = await db.execute(statement)
    return result.scalar_one_or_none()

def create_student_tokens(student: Student) -> dict:
    """Create access and refresh tokens for a student"""
    # Create access token data
    access_token_data = {
        "sub": str(student.id),  # student_id (UUID)
        "role": "student",
        "index_number": student.index_number,
        "email": student.email
    }
    
    # Create refresh token data
    refresh_token_data = {
        "sub": str(student.id),
        "role": "student"
    }
    
    # Create tokens
    access_token = create_access_token(
        data=access_token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES or 30)
    )
    
    refresh_token = create_refresh_token(
        data=refresh_token_data,
        expires_delta=timedelta(days=7)
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

async def create_student(student_data: dict, db: AsyncSession) -> Student:
    """Create a new student with hashed password (using name as temporary password)"""
    # Hash the name as temporary password
    hashed_password = get_password_hash(student_data["name"])  # Use name as temporary password
    
    # Use provided class_name or default
    class_name = student_data.get("class_name", "Not assigned")
    
    # Create student object
    student = Student(
        teacher_id=student_data["teacher_id"],
        email=student_data["email"] or '',  # Empty string if no email
        index_number=student_data["index_number"],
        hashed_password=hashed_password,
        name=student_data["name"],
        class_name=class_name,
        password_changed=False  # Password not changed yet
    )
    
    # Add to database
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
    # Create enrollment if subject is provided
    if "subject" in student_data and student_data["subject"]:
        enrollment = StudentEnrollment(
            student_id=student.id,
            subject=student_data["subject"],
            class_name=class_name,
            teacher_display_name=student_data.get("teacher_display_name") or getattr(student_data.get("teacher"), 'display_name', None),
            is_active=True
        )
        db.add(enrollment)
        await db.commit()
        await db.refresh(enrollment)
    
    return student

async def refresh_access_token(refresh_token: str, db: AsyncSession) -> dict:
    """Create a new access token using a refresh token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        student_id: str = payload.get("sub")
        role: str = payload.get("role")
        
        if student_id is None or role != "student":
            raise credentials_exception
            
        token_data = StudentTokenData(student_id=UUID(student_id), role=role)
    except JWTError:
        raise credentials_exception
    
    student = await get_student_by_id(token_data.student_id, db)
    if student is None:
        raise credentials_exception
    
    # Create new access token
    access_token_data = {
        "sub": str(student.id),
        "role": "student",
        "index_number": student.index_number,
        "email": student.email
    }
    
    access_token = create_access_token(
        data=access_token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES or 30)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

async def change_student_password(student_id: UUID, new_password: str, db: AsyncSession) -> bool:
    """Change student password and mark as changed"""
    try:
        statement = select(Student).where(Student.id == student_id)
        result = await db.execute(statement)
        student = result.scalar_one_or_none()
        
        if not student:
            return False
        
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Update student record
        student.hashed_password = hashed_password
        student.password_changed = True
        student.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(student)
        
        logger.info(f"Password changed successfully for student: {student.email}")
        return True
    except Exception as e:
        logger.error(f"Error changing password for student {student_id}: {str(e)}")
        await db.rollback()
        return False

def generate_index_number(name: str) -> str:
    """Generate a unique index number based on student name"""
    name_part = ''.join(c for c in name if c.isalnum())[:5].upper()
    return f"STU{name_part}{secrets.randbelow(9999):04d}"

def parse_csv_file(file_content: bytes) -> List[Dict[str, Any]]:
    """Parse CSV file content and extract student data"""
    try:
        # Decode bytes to string
        content = file_content.decode('utf-8')
        
        # Use StringIO to treat string as file-like object
        csv_file = io.StringIO(content)
        
        # Parse CSV
        reader = csv.DictReader(csv_file)
        
        # Validate required columns
        if 'name' not in reader.fieldnames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required column: name"
            )
        
        # Check that at least one of email or index_number/student_id is provided
        has_email = 'email' in reader.fieldnames
        has_index = 'index_number' in reader.fieldnames
        has_student_id = 'student_id' in reader.fieldnames
        
        if not (has_email or has_index or has_student_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of email, index_number, or student_id must be provided"
            )
        
        students_data = []
        for row_num, row in enumerate(reader, start=2):  # Start at 2 because header is row 1
            # Skip empty rows
            if not any(row.values()):
                continue
                
            # Validate required fields
            if not row.get('name'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {row_num}: Name is required"
                )
            
            # Check if at least one of email or index_number/student_id is provided
            email = row.get('email', '').strip() if row.get('email') else ''
            index_number = row.get('index_number', '').strip() if row.get('index_number') else ''
            student_id = row.get('student_id', '').strip() if row.get('student_id') else ''
            
            # Use student_id as index_number if index_number is not provided
            if not index_number and student_id:
                index_number = student_id
            
            # Must have at least email or index_number
            if not email and not index_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {row_num}: At least email or index_number must be provided"
                )
            
            # Validate email format if provided
            if email and '@' not in email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {row_num}: Invalid email format"
                )
            
            # Get optional fields
            class_name = row.get('class_name', '').strip() if row.get('class_name') else ''
            subject = row.get('subject', '').strip() if row.get('subject') else ''
            
            # Determine login ID based on provided data:
            # 1. If only email provided -> use email as login ID
            # 2. If index_number provided (with or without email) -> use index_number as login ID
            login_id = index_number if index_number else email
            
            student_data = {
                'name': row['name'].strip(),
                'email': email,
                'index_number': index_number,
                'class_name': class_name,
                'subject': subject,
                'login_id': login_id  
            }
            
            students_data.append(student_data)
        
        return students_data
    except csv.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing CSV file: {str(e)}"
        )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid CSV file."
        )

@router.get("/students/{student_id}", response_model=StudentProfileResponse)
async def get_student(
    student_id: UUID,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get student profile by ID for students enrolled in current teacher's courses.
    
    Args:
        student_id: UUID of the student
        current_teacher: Authenticated teacher
        db: Database session
    
    Returns:
        Student profile information
    """
    logger.info(f"Fetching student profile for ID: {student_id}")
    
    try:
        # Check if student exists and is enrolled in any of the current teacher's courses
        teacher_display_name = getattr(current_teacher, 'display_name', None)
        statement = select(Student).join(StudentEnrollment).where(
            Student.id == student_id,
            StudentEnrollment.teacher_display_name == teacher_display_name
        )
        result = await db.execute(statement)
        student = result.scalar_one_or_none()
        
        if not student:
            logger.warning(f"Student profile not found or not enrolled in teacher's courses for ID: {student_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found or not enrolled in your courses"
            )
        
        logger.info(f"Student profile fetched successfully for ID: {student_id}")
        return student
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching student profile for ID {student_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch student profile"
        )

@router.get("/list-students", response_model=PaginatedStudentResponse)
async def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("created_at", regex="^(name|email|index_number|created_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    search: Optional[str] = Query(None, description="Search term for student name, email, or index number"),
    class_name: Optional[str] = Query(None, description="Filter by class name"),
    subject: Optional[str] = Query(None, description="Filter by subject"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    List all students enrolled in the current teacher's courses with pagination and sorting.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (max 500)
        sort_by: Field to sort by (name, email, index_number, created_at)
        sort_order: Sort order (asc or desc)
        search: Search term for student name, email, or index number (optional)
        class_name: Filter students by class name (optional)
        subject: Filter students by subject (optional)
        current_teacher: Authenticated teacher
        db: Database session
    
    Returns:
        Dict containing students list, pagination info, and total count
    """
    logger.info(f"Fetching students enrolled in courses for teacher: {current_teacher.id}")
    
    try:
        # Build the base query for filtering
        teacher_display_name = getattr(current_teacher, 'display_name', None)
        
        # Build count query with optional filters
        count_query = select(func.count(Student.id.distinct())).select_from(Student).join(StudentEnrollment)
        count_conditions = [StudentEnrollment.teacher_display_name == teacher_display_name]
        
        # Add search filter if provided
        if search:
            search_pattern = f"%{search}%"
            count_conditions.append(
                (Student.name.ilike(search_pattern)) |
                (Student.email.ilike(search_pattern)) |
                (Student.index_number.ilike(search_pattern))
            )
        
        # Add optional filters
        if class_name:
            count_conditions.append(StudentEnrollment.class_name == class_name)
        if subject:
            count_conditions.append(StudentEnrollment.subject == subject)
            
        count_statement = count_query.where(*count_conditions)
        count_result = await db.execute(count_statement)
        total_count = count_result.scalar()
        
        # Handle case where skip is beyond total count
        if skip >= total_count and total_count > 0:
            # Return empty list with proper pagination
            has_next = False
            has_prev = skip > 0
            next_skip = None
            prev_skip = max(0, skip - limit) if skip > limit else (0 if skip > 0 else None)
            
            logger.info(f"Skip ({skip}) is beyond total count ({total_count}), returning empty list")
            
            return {
                "students": [],
                "pagination": {
                    "total": total_count,
                    "skip": skip,
                    "limit": limit,
                    "has_next": has_next,
                    "has_prev": has_prev,
                    "next_skip": next_skip,
                    "prev_skip": prev_skip,
                    "pages": (total_count + limit - 1) // limit  # Ceiling division
                },
                "sort": {
                    "by": sort_by,
                    "order": sort_order
                },
                "filters": {
                    "search": search,
                    "class_name": class_name,
                    "subject": subject
                }
            }
        
        # Build dynamic query with sorting and join
        sort_column = getattr(Student, sort_by)
        if sort_order == "desc":
            sort_column = sort_column.desc()
        
        # Build main query with optional filters
        query = select(Student).join(StudentEnrollment).where(*count_conditions).order_by(sort_column).offset(skip).limit(limit).distinct()
        
        result = await db.execute(query)
        students = result.scalars().all()
        
        # Calculate pagination info
        has_next = skip + limit < total_count
        has_prev = skip > 0
        next_skip = skip + limit if has_next else None
        prev_skip = skip - limit if skip > limit else 0 if skip > 0 else None
        
        logger.info(f"Fetched {len(students)} students enrolled in teacher's courses")
        
        return {
            "students": students,
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "has_next": has_next,
                "has_prev": has_prev,
                "next_skip": next_skip,
                "prev_skip": prev_skip,
                "pages": (total_count + limit - 1) // limit  # Ceiling division
            },
            "sort": {
                "by": sort_by,
                "order": sort_order
            },
            "filters": {
                "search": search,
                "class_name": class_name,
                "subject": subject
            }
        }
    except Exception as e:
        logger.error(f"Error fetching students for teacher ID {current_teacher.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch students"
        )

@router.get("/students/me", response_model=StudentProfileResponse)
async def get_current_student_profile(
    current_student: Student = Depends(get_current_student)
):
    """
    Get profile of the currently authenticated student.
    
    Args:
        current_student: Authenticated student from token
    
    Returns:
        Current student's profile information
    """
    logger.info(f"Fetching profile for current student ID: {current_student.id}")
    return current_student

@router.get("/students/me/subjects", response_model=List[str])
async def get_current_student_subjects(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all distinct subjects for the currently authenticated student.
    
    Args:
        current_student: Authenticated student from token
        db: Database session
    
    Returns:
        List of distinct subject names
    """
    logger.info(f"Fetching subjects for current student ID: {current_student.id}")
    
    try:
        statement = select(StudentEnrollment.subject).where(
            StudentEnrollment.student_id == current_student.id,
            StudentEnrollment.is_active == True
        ).distinct()
        
        result = await db.execute(statement)
        subjects = [row[0] for row in result.fetchall()]
        
        logger.info(f"Fetched {len(subjects)} distinct subjects for student ID: {current_student.id}")
        return subjects
    except Exception as e:
        logger.error(f"Error fetching subjects for student ID {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subjects"
        )

@router.get("/students/me/classes", response_model=List[str])
async def get_current_student_classes(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all distinct classes for the currently authenticated student.
    
    Args:
        current_student: Authenticated student from token
        db: Database session
    
    Returns:
        List of distinct class names
    """
    logger.info(f"Fetching classes for current student ID: {current_student.id}")
    
    try:
        statement = select(StudentEnrollment.class_name).where(
            StudentEnrollment.student_id == current_student.id,
            StudentEnrollment.is_active == True
        ).distinct()
        
        result = await db.execute(statement)
        classes = [row[0] for row in result.fetchall()]
        
        logger.info(f"Fetched {len(classes)} distinct classes for student ID: {current_student.id}")
        return classes
    except Exception as e:
        logger.error(f"Error fetching classes for student ID {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch classes"
        )

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

@router.get("/students/me/enrollments/{enrollment_id}", response_model=StudentEnrollmentResponse)
async def get_student_enrollment(
    enrollment_id: int,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific enrollment for the currently authenticated student.
    
    Args:
        enrollment_id: ID of the enrollment
        current_student: Authenticated student from token
        db: Database session
    
    Returns:
        Student enrollment information
    """
    logger.info(f"Fetching enrollment {enrollment_id} for student ID: {current_student.id}")
    
    try:
        statement = select(StudentEnrollment).where(
            StudentEnrollment.id == enrollment_id,
            StudentEnrollment.student_id == current_student.id,
            StudentEnrollment.is_active == True
        )
        
        result = await db.execute(statement)
        enrollment = result.scalar_one_or_none()
        
        if not enrollment:
            logger.warning(f"Enrollment {enrollment_id} not found for student ID: {current_student.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enrollment not found"
            )
        
        logger.info(f"Fetched enrollment {enrollment_id} for student ID: {current_student.id}")
        return enrollment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching enrollment {enrollment_id} for student ID {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch enrollment"
        )

# Student Management Endpoints
@router.post("/students/bulk-upload")
async def bulk_create_students(
    class_name: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    teacher_display_name: Optional[str] = Query(None),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    file: UploadFile = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a CSV file containing student information and create accounts with temporary passwords.
    
    CSV Format:
    Required columns: name
    At least one of: email, index_number, student_id
    Optional columns: class_name, subject (these will be overridden by query parameters if provided)
    
    Query Parameters:
    - class_name: Class name for all students (optional)
    - subject: Subject for enrollment (optional)
    - teacher_display_name: Teacher display name for enrollment (optional)
    
    Example CSV:
    name,email,index_number
    John Doe,john@example.com,STU001
    Jane Smith,,STU002
    Bob Johnson,bob@example.com,
    
    Students can be enrolled in a specific subject and class if provided via query parameters.
    If a student already exists (by email or index_number), they will be enrolled in the teacher's course
    without creating a duplicate account.
    
    Returns:
    - List of created students with enrollment information
    - List of errors for failed creations
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Parse CSV data
        students_data = parse_csv_file(file_content)
        
        if not students_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid student data found in the CSV file"
            )
        
        # Process students
        created_students = []
        enrolled_students = []
        errors = []
        
        for student_data in students_data:
            try:
                # Check if student already exists (by email or index_number) across ALL teachers
                existing_student_stmt = select(Student).where(
                    ((Student.email == student_data['email']) & (Student.email != '')) | 
                    ((Student.index_number == student_data['index_number']) & (Student.index_number != ''))
                )
                existing_result = await db.execute(existing_student_stmt)
                existing_student = existing_result.scalar_one_or_none()
                
                if existing_student:
                    # Student exists - enroll them in this teacher's course
                    login_id = existing_student.index_number if existing_student.index_number else existing_student.email
                    
                    # Prepare existing student response data
                    existing_student_response = {
                        "id": str(existing_student.id),
                        "name": existing_student.name,
                        "email": existing_student.email,
                        "index_number": existing_student.index_number,
                        "class_name": existing_student.class_name,
                        "login_id": login_id,
                        "created_at": existing_student.created_at.isoformat() if existing_student.created_at else None,
                        "enrolled": True,
                        "reason": "Student enrolled in your course"
                    }
                    
                    # Check if student is already enrolled in this teacher's course with the same subject
                    enrollment_stmt = select(StudentEnrollment).where(
                        StudentEnrollment.student_id == existing_student.id,
                        StudentEnrollment.subject == (subject or student_data.get('subject', '')),
                        StudentEnrollment.teacher_display_name == (teacher_display_name or getattr(current_teacher, 'display_name', None))
                    )
                    enrollment_result = await db.execute(enrollment_stmt)
                    existing_enrollment = enrollment_result.scalar_one_or_none()
                    
                    # If not already enrolled in this specific course, create enrollment
                    student_subject = subject or student_data.get('subject')
                    if student_subject and not existing_enrollment:
                        student_class_name = class_name or student_data.get('class_name') or getattr(current_teacher, 'work_institution', 'Not assigned')
                        enrollment = StudentEnrollment(
                            student_id=existing_student.id,
                            subject=student_subject,
                            class_name=student_class_name,
                            teacher_display_name=teacher_display_name or getattr(current_teacher, 'display_name', None),
                            is_active=True
                        )
                        db.add(enrollment)
                        await db.commit()
                        await db.refresh(enrollment)
                        
                        # Add enrollment information to response
                        existing_student_response["enrollment"] = {
                            "subject": enrollment.subject,
                            "class_name": enrollment.class_name,
                            "teacher_display_name": enrollment.teacher_display_name,
                            "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None
                        }
                        existing_student_response["newly_enrolled"] = True
                    elif existing_enrollment:
                        # Add existing enrollment information to response
                        existing_student_response["enrollment"] = {
                            "subject": existing_enrollment.subject,
                            "class_name": existing_enrollment.class_name,
                            "teacher_display_name": existing_enrollment.teacher_display_name,
                            "enrollment_date": existing_enrollment.enrollment_date.isoformat() if existing_enrollment.enrollment_date else None
                        }
                        existing_student_response["newly_enrolled"] = False
                    
                    enrolled_students.append(existing_student_response)
                    logger.info(f"Enrolled existing student: {existing_student.name} in teacher's course")
                    continue
                
                # Student doesn't exist - create new student account
                # Use provided class_name or default to teacher's institution
                student_class_name = class_name or student_data.get('class_name') or getattr(current_teacher, 'work_institution', 'Not assigned')
                
                # Hash the name as temporary password
                hashed_password = get_password_hash(student_data['name'])  # Use name as temporary password
                
                # Create student object
                student = Student(
                    teacher_id=current_teacher.id,
                    email=student_data['email'] or '',  # Empty string if no email
                    index_number=student_data['index_number'],
                    hashed_password=hashed_password,
                    name=student_data['name'],
                    class_name=student_class_name,
                    password_changed=False  # Password not changed yet
                )
                
                # Add to database
                db.add(student)
                await db.commit()
                await db.refresh(student)
                
                # Prepare student response data
                # Determine login ID for response:
                # 1. If only email provided -> use email as login ID
                # 2. If index_number provided (with or without email) -> use index_number as login ID
                login_id = student_data['index_number'] if student_data['index_number'] else student_data['email']
                
                student_response = {
                    "id": str(student.id),
                    "name": student.name,
                    "email": student.email,
                    "index_number": student.index_number,
                    "class_name": student.class_name,
                    "login_id": login_id,
                    "created_at": student.created_at.isoformat() if student.created_at else None
                }
                
                # Create enrollment if subject is provided (via query parameters or CSV)
                student_subject = subject or student_data.get('subject')
                if student_subject:
                    enrollment = StudentEnrollment(
                        student_id=student.id,
                        subject=student_subject,
                        class_name=student_class_name,
                        teacher_display_name=teacher_display_name or getattr(current_teacher, 'display_name', None),
                        is_active=True
                    )
                    db.add(enrollment)
                    await db.commit()
                    await db.refresh(enrollment)
                    
                    # Add enrollment information to response
                    student_response["enrollment"] = {
                        "subject": enrollment.subject,
                        "class_name": enrollment.class_name,
                        "teacher_display_name": enrollment.teacher_display_name,
                        "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None
                    }
                
                created_students.append(student_response)
                logger.info(f"Created student account for {student.name}")
                
            except Exception as e:
                await db.rollback()
                errors.append({
                    "name": student_data['name'],
                    "email": student_data['email'],
                    "index_number": student_data['index_number'],
                    "error": str(e)
                })
                logger.error(f"Error creating student {student_data['name']}: {str(e)}")
        
        return {
            "message": f"Processed {len(students_data)} students",
            "created": len(created_students),
            "enrolled": len(enrolled_students),
            "failed": len(errors),
            "students": created_students + enrolled_students,
            "errors": errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk student creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.post("/students/register", response_model=StudentRegistrationResponse)
async def register_single_student(
    student_data: StudentRegistrationRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a single student with name as temporary password.
    
    Registration logic:
    - If only email and name provided -> student logs in with email and name (password)
    - If only index_number and name provided -> student logs in with index_number and name (password)
    - If both email, index_number and name provided -> student logs in with index_number and name (password)
    
    If a student already exists (by email or index_number), they will be enrolled in the teacher's course
    without creating a duplicate account.
    
    Students can be enrolled in a specific subject and class if provided.
    
    Returns:
    - Student information
    - Login ID that student will use to login
    - Enrollment information (if subject provided)
    """
    # Validate that at least one of email or index_number is provided
    if not student_data.email and not student_data.index_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of email or index_number must be provided"
        )
    
    try:
        # Check if student already exists (by email or index_number) across ALL teachers
        existing_student_stmt = select(Student).where(
            ((Student.email == student_data.email) & (Student.email != '')) | 
            ((Student.index_number == student_data.index_number) & (Student.index_number != ''))
        )
        existing_result = await db.execute(existing_student_stmt)
        existing_student = existing_result.scalar_one_or_none()
        
        # If student already exists, enroll them in this teacher's course
        if existing_student:
            # Prepare response data for existing student
            login_id = existing_student.index_number if existing_student.index_number else existing_student.email
            
            response_data = {
                "id": str(existing_student.id),
                "name": existing_student.name,
                "email": existing_student.email,
                "index_number": existing_student.index_number,
                "class_name": existing_student.class_name,
                "login_id": login_id,
                "created_at": existing_student.created_at.isoformat() if existing_student.created_at else None
            }
            
            # Check if student is already enrolled in this teacher's course with the same subject
            enrollment_stmt = select(StudentEnrollment).where(
                StudentEnrollment.student_id == existing_student.id,
                StudentEnrollment.subject == (student_data.subject or ''),
                StudentEnrollment.teacher_display_name == (student_data.teacher_display_name or getattr(current_teacher, 'display_name', None))
            )
            enrollment_result = await db.execute(enrollment_stmt)
            existing_enrollment = enrollment_result.scalar_one_or_none()
            
            # If subject is provided and student is not already enrolled in this specific course, create enrollment
            if student_data.subject and not existing_enrollment:
                enrollment = StudentEnrollment(
                    student_id=existing_student.id,
                    subject=student_data.subject,
                    class_name=student_data.class_name or existing_student.class_name or getattr(current_teacher, 'work_institution', 'Not assigned'),
                    teacher_display_name=student_data.teacher_display_name or getattr(current_teacher, 'display_name', None),
                    is_active=True
                )
                db.add(enrollment)
                await db.commit()
                await db.refresh(enrollment)
                
                # Add enrollment information to response
                response_data["enrollment"] = {
                    "subject": enrollment.subject,
                    "class_name": enrollment.class_name,
                    "teacher_display_name": enrollment.teacher_display_name,
                    "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None
                }
                response_data["newly_enrolled"] = True
            elif existing_enrollment:
                # Add existing enrollment information to response
                response_data["enrollment"] = {
                    "subject": existing_enrollment.subject,
                    "class_name": existing_enrollment.class_name,
                    "teacher_display_name": existing_enrollment.teacher_display_name,
                    "enrollment_date": existing_enrollment.enrollment_date.isoformat() if existing_enrollment.enrollment_date else None
                }
                response_data["newly_enrolled"] = False
            else:
                response_data["newly_enrolled"] = False
            
            # Return existing student information with 200 status
            return StudentRegistrationResponse(**response_data)
        
        # Student doesn't exist - create new student account
        # Determine login ID:
        # 1. If only email provided -> use email as login ID
        # 2. If index_number provided (with or without email) -> use index_number as login ID
        login_id = student_data.index_number if student_data.index_number else student_data.email
        
        # Use provided class_name or default to teacher's institution
        class_name = student_data.class_name or getattr(current_teacher, 'work_institution', 'Not assigned')
        
        # Hash the name as temporary password
        hashed_password = get_password_hash(student_data.name)  # Use name as temporary password
        
        # Create student object
        student = Student(
            teacher_id=current_teacher.id,
            email=student_data.email or '',  # Empty string if no email
            index_number=student_data.index_number,
            hashed_password=hashed_password,
            name=student_data.name,
            class_name=class_name,
            password_changed=False  # Password not changed yet
        )
        
        # Add to database
        db.add(student)
        await db.commit()
        await db.refresh(student)
        
        # Prepare response data
        response_data = {
            "id": str(student.id),
            "name": student.name,
            "email": student.email,
            "index_number": student.index_number,
            "class_name": student.class_name,
            "login_id": login_id,
            "created_at": student.created_at.isoformat() if student.created_at else None
        }
        
        # Create enrollment if subject is provided
        if student_data.subject:
            enrollment = StudentEnrollment(
                student_id=student.id,
                subject=student_data.subject,
                class_name=class_name,
                teacher_display_name=student_data.teacher_display_name or getattr(current_teacher, 'display_name', None),
                is_active=True
            )
            db.add(enrollment)
            await db.commit()
            await db.refresh(enrollment)
            
            # Add enrollment information to response
            response_data["enrollment"] = {
                "subject": enrollment.subject,
                "class_name": enrollment.class_name,
                "teacher_display_name": enrollment.teacher_display_name,
                "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None
            }
        
        # Return student information
        return StudentRegistrationResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single student registration failed: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register student: {str(e)}"
        )

@router.post("/students/change-password")
async def change_password(
    password_data: StudentPasswordChangeRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Change student password from temporary to new password.
    
    This endpoint requires student authentication and is used to change
    the temporary password (which is the student's name) to a new password.
    """
    try:
        # Verify current password (which should be the student's name)
        if not verify_password(password_data.current_password, current_student.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Check password strength (at least 8 characters)
        if len(password_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long"
            )
        
        # Change password
        success = await change_student_password(current_student.id, password_data.new_password, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password"
            )
        
        return {
            "message": "Password changed successfully",
            "password_changed": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed for student {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Password change failed for student {current_student.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

@router.delete("/students/{student_id}")
async def delete_student(
    student_id: UUID,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a student's enrollment from the current teacher's course.
    
    This endpoint removes the student's enrollment in the current teacher's course/subject.
    If this is the only enrollment for the student, the student account will be deleted entirely.
    If the student has enrollments with other teachers, only the enrollment for this teacher
    will be removed.
    
    Args:
        student_id: UUID of the student to remove from course
        current_teacher: Authenticated teacher
        db: Database session
    
    Returns:
        Success message indicating what was deleted
    """
    logger.info(f"Removing student {student_id} from teacher {current_teacher.id}'s course")
    
    try:
        # Check if student exists (regardless of teacher)
        logger.info(f"Checking if student {student_id} exists")
        all_student_stmt = select(Student).where(Student.id == student_id)
        all_student_result = await db.execute(all_student_stmt)
        student = all_student_result.scalar_one_or_none()
        
        if not student:
            logger.warning(f"Student {student_id} does not exist")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Find enrollments for this student with the current teacher's course
        logger.info(f"Finding enrollments for student {student_id} with teacher's courses")
        teacher_display_name = getattr(current_teacher, 'display_name', None)
        enrollment_statement = select(StudentEnrollment).where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.teacher_display_name == teacher_display_name
        )
        enrollment_result = await db.execute(enrollment_statement)
        enrollments = enrollment_result.scalars().all()
        
        if not enrollments:
            logger.warning(f"Student {student_id} is not enrolled in any of teacher {current_teacher.id}'s courses")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student is not enrolled in any of your courses"
            )
        
        logger.info(f"Found {len(enrollments)} enrollments to remove for student {student_id}")
        
        # Delete the enrollments for this teacher's courses
        deleted_enrollments = 0
        for enrollment in enrollments:
            try:
                logger.info(f"Deleting enrollment {enrollment.id} for student {student_id}")
                await db.delete(enrollment)
                deleted_enrollments += 1
            except Exception as e:
                error_msg = f"Error deleting enrollment {enrollment.id} for student {student_id}: {str(e)}"
                logger.error(error_msg)
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
        
        # Commit enrollment deletions
        logger.info(f"Committing enrollment deletions for student {student_id}")
        try:
            await db.commit()
            logger.info(f"Successfully committed enrollment deletions for student {student_id}")
        except Exception as e:
            error_msg = f"Error committing enrollment deletions for student {student_id}: {str(e)}"
            logger.error(error_msg)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        
        # Check if student has any remaining enrollments
        logger.info(f"Checking if student {student_id} has any remaining enrollments")
        remaining_enrollment_stmt = select(StudentEnrollment).where(StudentEnrollment.student_id == student_id)
        remaining_enrollment_result = await db.execute(remaining_enrollment_stmt)
        remaining_enrollments = remaining_enrollment_result.scalars().all()
        
        # If no remaining enrollments, delete the student account entirely
        if not remaining_enrollments:
            logger.info(f"Student {student_id} has no remaining enrollments, deleting account")
            try:
                await db.delete(student)
                await db.commit()
                logger.info(f"Student account {student_id} deleted successfully")
                return {
                    "message": f"Student account and all enrollments deleted successfully",
                    "deleted_student_id": str(student_id),
                    "enrollments_removed": deleted_enrollments,
                    "student_account_deleted": True
                }
            except Exception as e:
                error_msg = f"Error deleting student account {student_id}: {str(e)}"
                logger.error(error_msg)
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
        else:
            # Student still has enrollments with other teachers
            logger.info(f"Student {student_id} still has {len(remaining_enrollments)} enrollments with other teachers")
            return {
                "message": f"Student removed from your course(s). Student still has {len(remaining_enrollments)} enrollments with other teachers.",
                "deleted_student_id": str(student_id),
                "enrollments_removed": deleted_enrollments,
                "student_account_deleted": False,
                "remaining_enrollments": len(remaining_enrollments)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Unexpected error removing student {student_id}: {str(e)}"
        logger.error(error_msg)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
