# API Endpoints Documentation

## Authentication Endpoints

### Teacher Login
`POST /auth/login`
- Authenticates teacher credentials
- Returns JWT access token in response body
- Sets refresh token in HttpOnly cookie

### Teacher Refresh Token
`POST /auth/refresh`
- Uses refresh token from HttpOnly cookie
- Returns new access token in response body

### Student Login
`POST /student/login`
- Authenticates student credentials (index_number/email + password)
- Sets both access and refresh tokens in HttpOnly cookies
- Returns basic student information in response body

### Student Refresh Token
`POST /student/refresh`
- Uses refresh token from HttpOnly cookie
- Sets new access token in HttpOnly cookie
- Returns basic student information in response body

### Student Change Password
`POST /student/change-password`
- Changes student's temporary password
- Requires current password (student name) and new password
- Only accessible to authenticated students

## Student Management Endpoints

### Register Single Student
`POST /students/register`
- Registers a new student with temporary password (name) or enrolls existing student
- Accepts student name, email, and index_number
- Optional subject and class enrollment
- Returns student information including login ID
- **Duplicate Handling**: Checks for existing students by email or index_number across all teachers. If student already exists, enrolls them in the teacher's course without creating duplicate account. If subject is provided and student isn't already enrolled in that specific course, creates new enrollment.

### Bulk Register Students
`POST /students/bulk-upload`
- Registers multiple students from CSV file or enrolls existing students
- CSV must include student names
- Optional email, index_number, class_name, subject columns
- Query parameters for class_name, subject, teacher_display_name apply to all students
- **Duplicate Handling**: Enrolls existing students in the teacher's courses and continues processing. No error messages for duplicates.

### Get Student Profile
`GET /students/{student_id}`
- Returns detailed profile for specified student
- Only accessible to teachers if student is enrolled in their courses

### List Students
`GET /list-students`
- Returns paginated list of students enrolled in current teacher's courses
- Supports pagination with skip/limit parameters
- Supports sorting by name, email, index_number, created_at
- Supports filtering by class_name and subject
- Returns total count and pagination metadata

### Get Current Student Profile
`GET /students/me`
- Returns profile of currently authenticated student
- Only accessible to students
- Shows information from all enrolled courses

### Delete Student
`DELETE /students/{student_id}`
- Removes student's enrollment from current teacher's courses
- If student has no other enrollments, deletes entire student account
- Only removes enrollments for current teacher's courses
- Returns information about what was deleted

## Student Enrollment Endpoints

### Get Student Subjects
`GET /students/{student_id}/subjects`
- Returns list of distinct subjects for specified student in teacher's courses
- Only accessible to teacher who has the student enrolled

### Get Student Classes
`GET /students/{student_id}/classes`
- Returns list of distinct classes for specified student in teacher's courses
- Only accessible to teacher who has the student enrolled

### Get Student Enrollments
`GET /students/{student_id}/enrollments`
- Returns all enrollments for specified student in teacher's courses
- Only accessible to teacher who has the student enrolled

### Get Current Student Subjects
`GET /students/me/subjects`
- Returns list of distinct subjects for current student from all teachers
- Only accessible to students

### Get Current Student Classes
`GET /students/me/classes`
- Returns list of distinct classes for current student from all teachers
- Only accessible to students

### Get Current Student Enrollments
`GET /students/me/enrollments`
- Returns all enrollments for current student from all teachers
- Only accessible to students

### Get Specific Enrollment
`GET /students/me/enrollments/{enrollment_id}`
- Returns specific enrollment for current student
- Only accessible to students

## Shared Student Accounts
The system implements a shared student account model:
- Each actual student has one account in the system
- Multiple teachers can enroll the same student in their courses
- Students log in once and can access all their courses from all teachers
- Teachers only see students enrolled in their own courses
- When deleting students, only the enrollment is removed unless it's the student's last enrollment

## Handling Large Numbers of Students
The `/list-students` endpoint implements pagination to handle large numbers of students:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records to return (default: 100, max: 500)
- `sort_by`: Field to sort by (name, email, index_number, created_at)
- `sort_order`: Sort order (asc, desc)
- `class_name`: Filter students by class name (optional)
- `subject`: Filter students by subject (optional)
- Returns pagination metadata including total count, has_next, has_prev, etc.

## Student Deletion (Selective)
The student deletion endpoint implements selective deletion:
1. Verifies student exists
2. Removes enrollments for current teacher's courses only
3. If student has no remaining enrollments, deletes the entire student account
4. Returns detailed information about what was deleted

## Student Enrollment
Students can be enrolled in subjects and classes during registration:
- Enrollment information stored in StudentEnrollment table
- Each enrollment includes subject, class_name, teacher_display_name
- Students can have multiple active enrollments from different teachers
- Enrollments can be viewed by both teachers (for their courses) and students (for all courses)