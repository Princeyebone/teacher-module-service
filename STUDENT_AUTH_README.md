# Student Authentication System

## Overview
The student authentication system allows teachers to register students, and students to authenticate using temporary passwords. The system supports shared student accounts across multiple teachers, enabling students to access all their courses with a single login.

## Key Features
1. **Teacher-Managed Registration**: Teachers register students with temporary passwords (student names)
2. **Student Authentication**: Students login with index_number/email and temporary password
3. **Password Management**: Students must change temporary passwords on first login
4. **Token-Based Authentication**: JWT tokens with HttpOnly cookies for security
5. **Cross-Teacher Enrollment**: Students can be enrolled in courses by multiple teachers
6. **Unified Student Experience**: Students log in once and access all their courses
7. **Teacher-Scoped Views**: Each teacher only sees students in their own courses
8. **Advanced Filtering**: Teachers can filter students by class and subject

## Shared Student Accounts
The system implements a shared student account model:
- Each actual student has one account in the system, regardless of how many teachers register them
- When Teacher A registers a student, and then Teacher B registers the same student (by email or index_number), the system:
  - Recognizes the student already exists
  - Enrolls the existing student in Teacher B's course
  - Does not create a duplicate account
- Students can log in once and see all courses they're enrolled in from all teachers
- Teachers only see students enrolled in their own courses

## Student Registration Process
1. Teacher registers student with name (used as temporary password)
2. System checks if student already exists by email or index_number
3. If student exists, enrolls them in teacher's course without duplication
4. If student doesn't exist, creates new account and enrolls in teacher's course
5. System generates unique index_number if not provided
6. Student receives login credentials (index_number or email + temporary password)
7. Student authenticates and must change password on first login

## Authentication Flow
1. Student authenticates with index_number/email and temporary password (name)
2. System issues JWT access and refresh tokens
3. Tokens stored in HttpOnly cookies for security
4. Student must change temporary password on first successful login
5. Access tokens expire after 30 minutes by default
6. Refresh tokens valid for 7 days

## Token Management
- Access tokens: Short-lived (30 minutes), used for authentication
- Refresh tokens: Long-lived (7 days), used to obtain new access tokens
- Both tokens stored in HttpOnly cookies for security
- Tokens contain student ID, role, and other identifying information

## Password Security
- Temporary passwords are student names
- Passwords hashed using Argon2 algorithm
- Students must change temporary passwords on first login
- Password strength requirements enforced

## Student Enrollment
Students can be enrolled in specific subjects and classes:
- Enrollment information stored in StudentEnrollment table
- Students can be enrolled in multiple courses from different teachers
- Enrollment includes subject, class_name, and teacher_display_name
- Teachers can view enrollments for students in their courses
- Students can view all their enrollments from all teachers

## API Endpoints

### Student Authentication
- `POST /student/login`: Authenticate student and issue tokens
- `POST /student/refresh`: Refresh access token using refresh token
- `POST /student/change-password`: Change temporary password

### Student Management (Teacher Endpoints)
- `POST /students/register`: Register a single student or enroll existing student in course
- `POST /students/bulk-upload`: Bulk register students or enroll existing students in courses
- `GET /students/{student_id}`: Get student profile (only for students in teacher's courses)
- `GET /list-students`: List all students enrolled in current teacher's courses with pagination and filtering
- `GET /students/me`: Get current student profile (student endpoint)
- `DELETE /students/{student_id}`: Remove student from teacher's course (selective deletion)

### Student Enrollment (Teacher Endpoints)
- `GET /students/{student_id}/subjects`: Get all subjects for a student in teacher's courses
- `GET /students/{student_id}/classes`: Get all classes for a student in teacher's courses
- `GET /students/{student_id}/enrollments`: Get all enrollments for a student in teacher's courses

### Student Enrollment (Student Endpoints)
- `GET /students/me/subjects`: Get all subjects for current student from all teachers
- `GET /students/me/classes`: Get all classes for current student from all teachers
- `GET /students/me/enrollments`: Get all enrollments for current student from all teachers
- `GET /students/me/enrollments/{enrollment_id}`: Get specific enrollment for current student

## Filtering Students
The list students endpoint supports advanced filtering:
- **By Class Name**: Filter students enrolled in a specific class
- **By Subject**: Filter students enrolled in a specific subject
- **Combined Filters**: Use both class_name and subject filters together
- **Pagination**: All filtering works with pagination (skip/limit)
- **Sorting**: Results can be sorted while applying filters

Example API calls:
```
# Get all students in "Grade 10A" class
GET /list-students?class_name=Grade%2010A

# Get all students enrolled in "Mathematics" subject
GET /list-students?subject=Mathematics

# Get students in "Grade 10A" class enrolled in "Mathematics" subject
GET /list-students?class_name=Grade%2010A&subject=Mathematics

# Get students with pagination and sorting
GET /list-students?class_name=Grade%2010A&skip=0&limit=50&sort_by=name&sort_order=asc
```

## Duplicate Handling
When registering students, the system gracefully handles duplicates:
- Checks for existing students by email or index_number across all teachers
- If student already exists, enrolls them in the teacher's course without creating duplicate account
- No error messages for duplicate registrations
- If subject is provided and student isn't already enrolled in that specific course, creates new enrollment
- Bulk uploads enroll existing students and continue processing

## Selective Deletion
The student deletion endpoint implements selective deletion:
- When a teacher deletes a student, only removes the enrollment in the teacher's courses
- If student has enrollments with other teachers, their account remains
- Only deletes the student's entire account if they have no remaining enrollments
- Returns information about what was deleted

## Security Features
1. HttpOnly cookies for token storage
2. Argon2 password hashing
3. JWT token expiration and refresh
4. Teacher authorization for student management
5. Student authentication for profile access
6. CORS configuration for frontend integration

## Implementation Details
- Built with FastAPI
- PostgreSQL database with SQLModel ORM
- Passlib for password hashing
- PyJWT for token management
- HttpOnly cookies for secure token storage
- Comprehensive logging for debugging