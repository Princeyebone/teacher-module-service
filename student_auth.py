from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from model import Student
from schemas import StudentTokenData
from config import settings
from fastapi import HTTPException, status
from logger import logger

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
            logger.warning(f"Invalid password for student with index number: {index_number}")
            return None
        
        logger.info(f"Student authenticated successfully: {index_number}")
        return student
    except Exception as e:
        logger.error(f"Error authenticating student with index number {index_number}: {str(e)}")
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
    """Create a new student with hashed password"""
    # Hash the password
    hashed_password = get_password_hash(student_data["password"])
    
    # Create student object
    student = Student(
        email=student_data["email"],
        index_number=student_data["index_number"],
        hashed_password=hashed_password,
        name=student_data["name"]
    )
    
    # Add to database
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
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