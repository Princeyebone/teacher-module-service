"""
Test script to demonstrate the get_current_student dependency function
"""
from fastapi import FastAPI, Depends
from dependencies import get_current_student
from schemas import StudentProfileResponse

app = FastAPI()

# Example protected endpoint that uses the get_current_student dependency
@app.get("/api/student/dashboard", response_model=dict)
async def student_dashboard(current_student = Depends(get_current_student)):
    """
    Example protected endpoint that requires student authentication.
    The get_current_student dependency will:
    1. Extract the JWT token from the Authorization header
    2. Decode and validate the token
    3. Fetch the student record from the database
    4. Return the student object if valid, or raise an HTTPException if not
    """
    return {
        "message": f"Welcome to your dashboard, {current_student.name}!",
        "student_id": str(current_student.id),
        "email": current_student.email,
        "index_number": current_student.index_number
    }

@app.get("/api/student/profile", response_model=StudentProfileResponse)
async def student_profile(current_student = Depends(get_current_student)):
    """
    Example endpoint that returns the full student profile.
    """
    return current_student

# To use this in your frontend, you would:
# 1. Login the student using either /auth/student-login or /auth/student-id-login
# 2. Store the access_token from the response
# 3. Include the token in the Authorization header for subsequent requests:
#    Authorization: Bearer <access_token>

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)