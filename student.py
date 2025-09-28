from fastapi import APIRouter, UploadFile, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from schemas import AssessmentCountResponse
import io
import csv
import secrets
import string
from logger import logger
from database import get_db
from model import Student, TeacherProfile
from dependencies import get_current_teacher, get_current_student
from student_auth import get_password_hash, change_student_password, create_student_tokens, verify_password

router = APIRouter(tags=["Student Management"])

# Pydantic models
class StudentRegistrationRequest(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    index_number: Optional[str] = None

class StudentPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

def generate_index_number(name: str, db: AsyncSession) -> str:
    """Generate a unique index number based on student name"""
    name_part = ''.join(c for c in name if c.isalnum())[:5].upper()
    base_index = f"STU{name_part}"
    index_number = base_index
    counter = 1
    
    # Check if this index number already exists
    while True:
        stmt = select(Student).where(Student.index_number == index_number)
        result = db.execute(stmt)
        if not result.scalar_one_or_none():
            break
        index_number = f"{base_index}{counter:03d}"
        counter += 1
    
    return index_number

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
            
            # If no index_number provided but we have email, generate index_number
            if not index_number and email:
                # Generate a simple index number based on name and row number
                name_part = ''.join(c for c in row['name'] if c.isalnum())[:5].upper()
                index_number = f"STU{name_part}{row_num:03d}"
            
            student_data = {
                'name': row['name'].strip(),
                'email': email,
                'index_number': index_number
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

@router.post("/students/bulk-upload")
async def bulk_create_students(
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    file: UploadFile = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a CSV file containing student information and create accounts with temporary passwords.
    
    CSV Format:
    Required columns: name
    At least one of: email, index_number, student_id
    
    Example CSV:
    name,email,index_number
    John Doe,john@example.com,STU001
    Jane Smith,,STU002
    Bob Johnson,bob@example.com,
    
    Returns:
    - List of created students
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
        errors = []
        
        for student_data in students_data:
            try:
                # Check if student already exists (by email or index_number)
                existing_student_stmt = select(Student).where(
                    (Student.email == student_data['email']) | 
                    (Student.index_number == student_data['index_number'])
                )
                existing_result = await db.execute(existing_student_stmt)
                existing_student = existing_result.scalar_one_or_none()
                
                if existing_student:
                    errors.append({
                        "name": student_data['name'],
                        "email": student_data['email'],
                        "index_number": student_data['index_number'],
                        "error": "Student with this email or index number already exists"
                    })
                    continue
                
                # Hash the name as temporary password
                hashed_password = get_password_hash(student_data['name'])  # Use name as temporary password
                
                # Create student object
                student = Student(
                    teacher_id=current_teacher.id,
                    email=student_data['email'] or '',  # Empty string if no email
                    index_number=student_data['index_number'],
                    hashed_password=hashed_password,
                    name=student_data['name'],
                    student_id=0,  # Default to 0
                    class_name=student_data.get('class_name', 'Not assigned'),  # Default class
                    password_changed=False  # Password not changed yet
                )
                
                # Add to database
                db.add(student)
                await db.commit()
                await db.refresh(student)
                
                # Add to created students list
                created_students.append({
                    "id": str(student.id),
                    "name": student.name,
                    "email": student.email,
                    "index_number": student.index_number,
                    "login_id": student.index_number,  # Students will login with index_number
                    "created_at": student.created_at.isoformat() if student.created_at else None
                })
                
                logger.info(f"Created student account for {student.name}")
                
            except IntegrityError as e:
                await db.rollback()
                errors.append({
                    "name": student_data['name'],
                    "email": student_data['email'],
                    "index_number": student_data['index_number'],
                    "error": f"Database integrity error: {str(e)}"
                })
                logger.warning(f"Failed to create student {student_data['name']}: {str(e)}")
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
            "failed": len(errors),
            "students": created_students,
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

@router.post("/students/register")
async def register_single_student(
    student_data: StudentRegistrationRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a single student with name as temporary password.
    
    At least one of email or index_number must be provided.
    
    Returns:
    - Student information
    - Login ID (index_number) that student will use to login
    """
    # Validate that at least one of email or index_number is provided
    if not student_data.email and not student_data.index_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of email or index_number must be provided"
        )
    
    try:
        # Check if student already exists (by email or index_number)
        existing_student_stmt = select(Student).where(
            (Student.email == student_data.email) | 
            (Student.index_number == student_data.index_number)
        )
        existing_result = await db.execute(existing_student_stmt)
        existing_student = existing_result.scalar_one_or_none()
        
        if existing_student:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student with this email or index number already exists"
            )
        
        # If no index_number provided but email is, generate one
        index_number = student_data.index_number
        if not index_number and student_data.email:
            index_number = generate_index_number(student_data.name, db)
        
        # Hash the name as temporary password
        hashed_password = get_password_hash(student_data.name)  # Use name as temporary password
        
        # Create student object
        student = Student(
            teacher_id=current_teacher.id,
            email=student_data.email or '',  # Empty string if no email
            index_number=index_number,
            hashed_password=hashed_password,
            name=student_data.name,
            student_id=0,  # Default to 0
            class_name="Not assigned",  # Default class
            password_changed=False  # Password not changed yet
        )
        
        # Add to database
        db.add(student)
        await db.commit()
        await db.refresh(student)
        
        # Return student information
        return {
            "id": str(student.id),
            "name": student.name,
            "email": student.email,
            "index_number": student.index_number,
            "login_id": student.index_number,  # Students will login with index_number
            "created_at": student.created_at.isoformat() if student.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single student registration failed: {str(e)}")
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