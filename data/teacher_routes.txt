from fastapi import APIRouter, HTTPException, status, Depends
from schemas import TeacherBase, TeacherCreate, TeacherRead, TeacherUpdate
from sqlmodel import Session, select    
from database import get_db
from model import Teacher, UserRole
from uuid import UUID


router=APIRouter(tags=["CRUD OPERATIONS"])

@router.post("/", response_model=TeacherRead)
def create_teacher(
    teacher_in : TeacherCreate,
    db:Session = Depends(get_db)
):
    statement = db.exec(select(Teacher).where(Teacher.email == teacher_in.email)).first()
    if statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Another teacher with this email already exists"
        )
    
    teacher = Teacher.model_validate(teacher_in)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher



@router.get("/{teacher_id}", response_model = TeacherRead)

def read_teacher(
    teacher_id:UUID,
    db:Session = Depends(get_db)
):
    statement = db.exec(select(Teacher).where(Teacher.id == teacher_id)).first()
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher Not Found"
        )
    return statement

from dependencies import requires_role, get_current_user

@router.get("/", response_model = list[TeacherRead])
@requires_role(UserRole.DIRECTOR)
def read_teachers(
    db:Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    teachers = db.exec(select(Teacher)).all()
    return teachers

@router.patch("/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id:int,
    teacher_in:TeacherUpdate,
    db:Session = Depends(get_db)
):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher deos not exist"
        )
    
    update = teacher_in.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(teacher, key, value)

    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher
    
@router.delete("/{teacher_id}", response_model=TeacherRead)
def delete_teacher(
    teacher_id:int,
    db:Session = Depends(get_db)
):
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher deos not exist"
        )

    db.delete(teacher)
    db.commit() 
    return teacher
    
    