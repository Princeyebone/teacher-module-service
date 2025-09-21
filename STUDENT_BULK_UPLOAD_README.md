# Student Management API

This document describes the student management endpoints that allow teachers to register students individually or in bulk using CSV files, and students to change their temporary passwords.

## Endpoints

### Teacher Endpoints
1. Single Student Registration: `POST /api/teacher/students/register`
2. Bulk Student Registration: `POST /api/teacher/students/bulk-upload`

### Student Endpoints
1. Login with Email: `POST /api/auth/student-login`
2. Login with Index Number: `POST /api/auth/student-id-login`
3. Change Password: `POST /api/teacher/students/change-password` (requires authentication)
4. Refresh Access Token: `POST /api/auth/student-refresh`
5. Logout: `POST /api/auth/student-logout`

## Authentication

All teacher endpoints require teacher authentication. Include a valid JWT token in the Authorization header:

```
Authorization: Bearer <your_token>
```

Student endpoints require either no authentication (for login) or student authentication (for password change).

**Security Note**: Tokens are stored in HttpOnly cookies and are not returned in the response body for enhanced security.

## Registration Flow

### 1. Single Student Registration

Register a single student with their name as a temporary password.

#### Request Format

```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",  // Optional
  "index_number": "STU001"          // Optional, but at least one of email or index_number is required
}
```

**Requirements:**
- `name` is always required
- At least one of `email` or `index_number` must be provided

**Login Details Based on Provided Data:**
- If only `email` and `name` are provided → Student logs in with **email** and name (password)
- If only `index_number` and `name` are provided → Student logs in with **index_number** and name (password)
- If both `email`, `index_number`, and `name` are provided → Student logs in with **index_number** and name (password)

#### Response Format

```json
{
  "id": "uuid-string",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "index_number": "STU001",
  "login_id": "STU001",  // or email if index_number not provided
  "created_at": "2023-01-01T00:00:00"
}
```

### 2. Bulk Student Registration

Upload a CSV file containing student information and create accounts with names as temporary passwords.

#### CSV Format

**Required Columns:**
- `name`: Student's full name (compulsory)

**At least one of the following:**
- `email`: Student's email address
- `index_number`: Student's index number
- `student_id`: Student's ID (used as index_number if index_number not provided)

#### Example CSV

```csv
name,email,index_number
John Doe,john.doe@example.com,STU001
Jane Smith,,STU002
Bob Johnson,bob.johnson@example.com,
Mary Jane,mary.jane@example.com,MJ001
```

**Important Notes:**
1. `name` is always required
2. At least one of `email`, `index_number`, or `student_id` must be provided
3. If `index_number` is not provided but `student_id` is, `student_id` will be used as `index_number`
4. Login Details Based on Provided Data:
   - If only `email` provided → Student logs in with **email** and name (password)
   - If `index_number` provided (with or without `email`) → Student logs in with **index_number** and name (password)

## Login Flow

Students can login using either their email or index number with their name as the temporary password.

### Login with Email

```
POST /api/auth/student-login
```

```json
{
  "email": "john.doe@example.com",
  "password": "John Doe"  // Student's name as temporary password
}
```

### Login with Index Number

```
POST /api/auth/student-id-login
```

```json
{
  "student_id": "STU001",  // This is the index_number
  "password": "John Doe"   // Student's name as temporary password
}
```

### Login Response

```json
{
  "token_type": "bearer",
  "password_change_required": true,
  "student": {
    "id": "uuid-string",
    "email": "john.doe@example.com",
    "index_number": "STU001",
    "name": "John Doe",
    "created_at": "2023-01-01T00:00:00"
  }
}
```
*Note: Tokens are set as HttpOnly cookies and not returned in the response body for enhanced security*

**Important**: If `password_change_required` is `true`, the student must change their password immediately.

## Token Management

### Access Token
- Used for authenticating API requests
- Short-lived (30 minutes by default)
- Stored in HttpOnly cookie for security

### Refresh Token
- Used to obtain new access tokens
- Long-lived (7 days by default)
- Stored in HttpOnly cookie for security

### Refreshing Access Token

When an access token expires, use the refresh token to get a new one:

```
POST /api/auth/student-refresh
```

**Headers:**
- The refresh token is automatically sent in cookies

**Response:**
```json
{
  "access_token": "new-jwt-access-token",
  "token_type": "bearer"
}
```

### Logout

To logout and clear tokens:

```
POST /api/auth/student-logout
```

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

This endpoint clears both access and refresh tokens from cookies.

## Password Change Flow

After successful login, if `password_change_required` is `true`, students must change their password.

### Request

```
POST /api/teacher/students/change-password
```

**Headers:**
```
Authorization: Bearer <access_token>
```

**Body:**
```json
{
  "current_password": "John Doe",      // Student's name (current temporary password)
  "new_password": "MyNewPassword123!"  // New secure password (min 8 characters)
}
```

### Response

```json
{
  "message": "Password changed successfully",
  "password_changed": true
}
```

After changing the password, the student can use their new password for future logins.

## Frontend Implementation Guide

### Authentication Flow

1. **Login Process:**
   - User submits login credentials (email/index_number + temporary password)
   - On successful login, store tokens in HttpOnly cookies (handled automatically by browser)
   - Check `password_change_required` flag in response
   - If true, redirect user to password change page

2. **Token Management:**
   - Access tokens are automatically sent with requests via cookies
   - When API returns 401 Unauthorized:
     - Attempt to refresh token using `/api/auth/student-refresh`
     - If refresh fails, redirect to login page

3. **Making Authenticated Requests:**
   - Include credentials with requests to ensure cookies are sent:
   ```javascript
   fetch('/api/some-protected-endpoint', {
     method: 'GET',
     credentials: 'include'  // Important for cookies
   })
   ```

### Example Frontend Implementation

#### Login and Token Handling

```javascript
async function loginStudent(credentials) {
  try {
    // Determine which endpoint to use based on the identifier type
    const isEmail = credentials.identifier.includes('@');
    const endpoint = isEmail ? 
      '/api/auth/student-login' : 
      '/api/auth/student-id-login';
    
    const loginData = isEmail ? 
      { email: credentials.identifier, password: credentials.password } : 
      { student_id: credentials.identifier, password: credentials.password };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',  // Important for cookie handling
      body: JSON.stringify(loginData)
    });

    if (response.ok) {
      const data = await response.json();
      
      // Check if password change is required
      if (data.password_change_required) {
        // Redirect to password change page
        window.location.href = '/change-password';
      } else {
        // Redirect to dashboard
        window.location.href = '/dashboard';
      }
      
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail);
    }
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
}
```

#### Making Authenticated Requests

```javascript
async function makeAuthenticatedRequest(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include',  // Important for cookie handling
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    // Handle token expiration
    if (response.status === 401) {
      // Try to refresh token
      const refreshResponse = await fetch('/api/auth/student-refresh', {
        method: 'POST',
        credentials: 'include'
      });

      if (refreshResponse.ok) {
        // Retry original request
        return makeAuthenticatedRequest(url, options);
      } else {
        // Redirect to login
        window.location.href = '/login';
        throw new Error('Session expired. Please login again.');
      }
    }

    return response;
  } catch (error) {
    console.error('Request failed:', error);
    throw error;
  }
}
```

#### Password Change

```javascript
async function changePassword(currentPassword, newPassword) {
  try {
    const response = await fetch('/api/teacher/students/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to dashboard after successful password change
      window.location.href = '/dashboard';
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail);
    }
  } catch (error) {
    console.error('Password change failed:', error);
    throw error;
  }
}
```

#### Logout

```javascript
async function logout() {
  try {
    const response = await fetch('/api/auth/student-logout', {
      method: 'POST',
      credentials: 'include'
    });

    if (response.ok) {
      // Redirect to login page
      window.location.href = '/login';
    }
  } catch (error) {
    console.error('Logout failed:', error);
    // Still redirect to login
    window.location.href = '/login';
  }
}
```

## Security Considerations

1. **Temporary Passwords**: Students use their names as temporary passwords, which they know
2. **Mandatory Password Change**: Students must change their temporary password on first login
3. **Password Strength**: New passwords must be at least 8 characters long
4. **Secure Storage**: Passwords are hashed using Argon2
5. **Token Security**: JWT tokens are stored in HttpOnly cookies (not returned in response body)
6. **Authentication Required**: Only authenticated teachers can register students
7. **HTTPS**: In production, all communication should be over HTTPS

## Best Practices

1. **Inform Students**: Clearly communicate that they need to change their password after first login
2. **Password Policies**: Encourage students to use strong, unique passwords
3. **Data Validation**: Validate student data before registration
4. **Duplicate Checking**: The system prevents creation of duplicate accounts
5. **Index Number Consistency**: Use consistent index number format across your institution
6. **Token Refresh**: Implement automatic token refresh to prevent session interruptions
7. **Error Handling**: Provide clear error messages to users
8. **Loading States**: Show loading indicators during API requests