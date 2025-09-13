# Student Authentication System

This document describes the student authentication system implemented in this project.

## Features

1. **Password Hashing with Argon2**: Secure password storage using the Argon2 algorithm
2. **JWT Token Creation**: JSON Web Tokens for authentication with custom claims
3. **Token Refresh**: Refresh tokens for improved security
4. **Student Registration**: Endpoint for registering new students
5. **Student Login**: Endpoint for authenticating existing students
6. **HttpOnly Cookie Storage**: Secure storage of tokens in HttpOnly cookies
7. **Dual Login Methods**: Login with email/password or index number/password

## Important Distinction

In this system, there are two different identifiers for students:
- **Student.id**: UUID automatically assigned by the database (primary key)
- **index_number**: String identifier assigned by the school (e.g., "STU001234")

## Endpoints

### Student Login (Email/Password)
```
POST /auth/student-login
```
**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
*Note: Tokens are also set as HttpOnly cookies*

### Student Login (Index Number/Password)
```
POST /auth/student-id-login
```
**Request Body:**
```json
{
  "student_id": "STU001234",  // This is the index_number, not the database ID
  "password": "securepassword"
}
```

### Student Registration
```
POST /auth/student-register
```
**Request Body:**
```json
{
  "email": "student@example.com",
  "password": "securepassword",
  "index_number": "STU001",  // School-assigned identifier
  "name": "John Doe"
}
```

### Token Refresh
```
POST /auth/student-refresh
```
*Uses refresh token from HttpOnly cookie*

### Student Logout
```
POST /auth/student-logout
```
*Clears HttpOnly cookies*

### Get Student Profile
```
GET /auth/student-profile?student_id=uuid-here
```

## JWT Token Claims

The access token contains the following claims:
- `sub`: Student ID (UUID) - the database primary key
- `role`: "student"
- `index_number`: Student's index number from the student table
- `email`: Student's email from the student table

## Security Features

1. **Argon2 Password Hashing**: Industry-standard password hashing algorithm
2. **Separate Access and Refresh Tokens**: Improved security with token rotation
3. **Token Expiration**: Access tokens expire in 30 minutes by default, refresh tokens in 7 days
4. **HttpOnly Cookie Storage**: Tokens stored in HttpOnly cookies to prevent XSS attacks
5. **Secure Flag**: Cookies marked as secure in production
6. **SameSite Protection**: Cookies use SameSite=strict to prevent CSRF attacks
7. **Proper Error Handling**: Secure error responses that don't leak sensitive information

## Implementation Details

### Files

1. **model.py**: Contains the [Student](file:///c%3A/Users/HP/tmdl5/model.py#L173-L182) model for database storage
2. **schemas.py**: Contains Pydantic models for request/response validation
3. **student_auth.py**: Core authentication logic including password hashing and token creation
4. **auths_routes.py**: FastAPI endpoints for student authentication
5. **dependencies.py**: Dependency functions for extracting student information from tokens

### Key Functions

1. `verify_password()`: Verifies a plain password against a hashed password
2. `get_password_hash()`: Hashes a password using Argon2
3. `create_access_token()`: Creates a JWT access token with custom claims
4. `create_refresh_token()`: Creates a JWT refresh token
5. `authenticate_student()`: Authenticates a student by email and password
6. `authenticate_student_by_id()`: Authenticates a student by index number and password
7. `create_student_tokens()`: Creates access and refresh tokens for a student

## Usage Example

### Backend Usage (Protected Routes)
```python
from fastapi import Depends
from dependencies import get_current_student

@app.get("/api/student/dashboard")
async def student_dashboard(current_student = Depends(get_current_student)):
    return {
        "message": f"Welcome {current_student.name}!",
        "student_id": str(current_student.id),  // Database UUID
        "index_number": current_student.index_number,  // School-assigned ID
        "email": current_student.email
    }
```

### Frontend Usage (Making Authenticated Requests)
```javascript
// Login with email/password
async function loginWithEmail(credentials) {
  const response = await fetch('/api/auth/student-login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      email: credentials.email,
      password: credentials.password
    }),
  });
  
  if (response.ok) {
    // Tokens are automatically stored in HttpOnly cookies
    console.log('Login successful');
  }
}

// Login with index number/password
async function loginWithIndexNumber(credentials) {
  const response = await fetch('/api/auth/student-id-login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      student_id: credentials.index_number,  // This is the school-assigned ID
      password: credentials.password
    }),
  });
  
  if (response.ok) {
    // Tokens are automatically stored in HttpOnly cookies
    console.log('Login successful');
  }
}

// Make authenticated requests (browser automatically includes cookies)
async function getDashboard() {
  // No need to manually include Authorization header
  // Browser automatically sends HttpOnly cookies
  const response = await fetch('/api/student/dashboard');
  const data = await response.json();
  return data;
}

// Refresh token (happens automatically)
async function refreshToken() {
  // Browser automatically includes refresh token cookie
  const response = await fetch('/api/auth/student-refresh', {
    method: 'POST',
  });
  // New access token is set in cookie automatically
}

// Logout
async function logout() {
  await fetch('/api/auth/student-logout', {
    method: 'POST',
  });
  // Cookies are cleared automatically
}
```

## Dependencies

- `passlib[argon2]`: For Argon2 password hashing
- `python-jose`: For JWT token creation and validation
- `sqlalchemy`: For database operations
- `sqlmodel`: For ORM operations
- `fastapi`: For API endpoints

## Security Recommendations

1. **Use HTTPS in Production**: Always use HTTPS to protect tokens in transit
2. **Set Secure Flag**: Ensure cookies have the secure flag set in production
3. **Implement CSRF Protection**: Add CSRF tokens for state-changing operations
4. **Token Rotation**: Consider implementing token rotation for enhanced security
5. **Rate Limiting**: Implement rate limiting on authentication endpoints
6. **Logging**: Log authentication attempts for security monitoring