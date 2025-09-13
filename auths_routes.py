from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from schemas import TeacherRegistrationRequest, StudentLoginRequest, StudentIDLoginRequest, StudentRegisterRequest, StudentToken, StudentProfileResponse
from httpx import AsyncClient
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from uuid import UUID
from model import TeacherProfile, Student
from sqlalchemy.exc import IntegrityError
from logger import logger
from dependencies import get_current_teacher
from student_auth import authenticate_student, authenticate_student_by_id, create_student_tokens, create_student, refresh_access_token
from sqlmodel import select

router = APIRouter(tags=["Authentication/Registration"])

@router.post(
    "/register-teacher",
    status_code=status.HTTP_201_CREATED,
    summary="Standalone teacher Registration Module",
)
async def register_teacher(
    data: TeacherRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Received teacher registration request for: {data.email}")
    async with AsyncClient(verify=False) as client:
        logger.info(f"Sending registration request for teacher: {data.email} to core service")
        resp = await client.post(
            f"{settings.CORE_SERVICE_URL}/api/register-teacher",
            json=data.model_dump(),
            headers={"intSAuthorization": f"Bearer {settings.SERVICE_JWT}"}
        )

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail", resp.text)
            logger.error(f"Registration failed for {data.email} with status {resp.status_code}: {detail}")
            raise HTTPException(
                status_code=resp.status_code,
                detail=detail
            )
        
        respond_data = resp.json()
        individual_id_str = respond_data.get("user_id")
        logger.info(f"Teacher registered in core service with user_id: {individual_id_str}")

        try:
            new_teacher = TeacherProfile(individual_id=UUID(individual_id_str))
            db.add(new_teacher)
            await db.commit()
            await db.refresh(new_teacher)
            logger.info(f"TeacherProfile created in local DB for user_id: {individual_id_str}")
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"IntegrityError while creating TeacherProfile for user_id: {individual_id_str}: {e}")

        return {"message": "successful registration check your email for activation link"}
    


@router.get("/central-me")
async def get_full_profile(
    request: Request,
    current_teacher = Depends(get_current_teacher),
):
    logger.info(f"Received request for central user info (teacher: {getattr(current_teacher, 'id', None)})")
    # --- 1) Local teacher‐module profile (SQLModel -> dict) ---
    # Assuming `current_teacher` is a SQLModel instance
    teacher_data = current_teacher.dict()  

    # --- 2) Forward user token to Central ERP `/api/me` ---
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid token in /central-me request")
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    service_token = settings.SERVICE_JWT

    logger.info("Sending request to core service /api/me endpoint")
    async with AsyncClient(verify=False) as client:
        central_resp = await client.get(
            f"{settings.CORE_SERVICE_URL}/api/me",
            headers={
                "Authorization": auth_header,
                "intSAuthorization": f"Bearer {service_token}"
            },
            timeout=5.0
        )

    if central_resp.status_code != 200:
        logger.error(f"Central ERP error: {central_resp.status_code} - {central_resp.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Central ERP error: {central_resp.text}"
        )

    central_json = central_resp.json()
    logger.info("Successfully fetched user info from ERP")

    # --- 3) Return both raw JSON blobs directly ---
    return {
        "central": central_json,
        "teacher": teacher_data
    }


# Student Authentication Endpoints

@router.post("/auth/student-login", response_model=StudentToken)
async def student_login(
    response: Response,
    login_data: StudentLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate a student by email and password and return JWT tokens"""
    logger.info(f"Student login attempt for email: {login_data.email}")
    
    student = await authenticate_student(login_data.email, login_data.password, db)
    if not student:
        logger.warning(f"Student authentication failed for email: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    tokens = create_student_tokens(student)
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 30 minutes
    )
    
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # 7 days
    )
    
    logger.info(f"Student login successful for email: {login_data.email}")
    return tokens

@router.post("/auth/student-id-login", response_model=StudentToken)
async def student_id_login(
    response: Response,
    login_data: StudentIDLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate a student by student ID and password and return JWT tokens"""
    logger.info(f"Student login attempt for ID: {login_data.student_id}")
    
    student = await authenticate_student_by_id(login_data.student_id, login_data.password, db)
    if not student:
        logger.warning(f"Student authentication failed for ID: {login_data.student_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect student ID or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    tokens = create_student_tokens(student)
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=True,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 30 minutes
    )
    
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 24 * 60 * 60  # 7 days
    )
    
    logger.info(f"Student login successful for ID: {login_data.student_id}")
    return tokens

@router.post("/auth/student-register", response_model=StudentProfileResponse, status_code=status.HTTP_201_CREATED)
async def student_register(
    register_data: StudentRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new student"""
    logger.info(f"Student registration attempt for email: {register_data.email}")
    
    # Check if student already exists
    existing_student = await db.execute(select(Student).where(Student.email == register_data.email))
    if existing_student.scalar_one_or_none():
        logger.warning(f"Student registration failed - email already exists: {register_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student with this email already exists"
        )
    
    # Check if index number already exists
    existing_index = await db.execute(select(Student).where(Student.index_number == register_data.index_number))
    if existing_index.scalar_one_or_none():
        logger.warning(f"Student registration failed - index number already exists: {register_data.index_number}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student with this index number already exists"
        )
    
    try:
        # Create student
        student_data = register_data.dict()
        student = await create_student(student_data, db)
        
        logger.info(f"Student registration successful for email: {register_data.email}")
        return student
    except Exception as e:
        logger.error(f"Student registration failed for email: {register_data.email} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register student"
        )

@router.post("/auth/student-refresh", response_model=dict)
async def student_refresh_token(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh student access token using refresh token"""
    logger.info("Student token refresh attempt")
    
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        new_tokens = await refresh_access_token(refresh_token, db)
        
        # Set new access token in cookie
        response.set_cookie(
            key="access_token",
            value=new_tokens["access_token"],
            httponly=True,
            secure=True,  # Set to True in production with HTTPS
            samesite="strict",
            max_age=30 * 60  # 30 minutes
        )
        
        logger.info("Student token refresh successful")
        return new_tokens
    except HTTPException as e:
        logger.warning(f"Student token refresh failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Student token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )

@router.post("/auth/student-logout")
async def student_logout(response: Response):
    """Logout student by clearing cookies"""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Successfully logged out"}

@router.get("/auth/student-profile", response_model=StudentProfileResponse)
async def get_student_profile(
    student_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get student profile by ID"""
    logger.info(f"Fetching student profile for ID: {student_id}")
    
    student = await db.execute(select(Student).where(Student.id == student_id))
    student_obj = student.scalar_one_or_none()
    
    if not student_obj:
        logger.warning(f"Student profile not found for ID: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    logger.info(f"Student profile fetched successfully for ID: {student_id}")
    return student_obj
