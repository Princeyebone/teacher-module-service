# Student Authentication Frontend Implementation Guide

## Overview
This guide provides implementation details for integrating the student authentication system into frontend applications. The system allows teachers to register students with temporary passwords, and students to authenticate and change their passwords.

## Key Concepts

### Shared Student Accounts
The system implements a shared student account model:
- Each actual student has one account in the system, regardless of how many teachers register them
- When Teacher A registers a student, and then Teacher B registers the same student (by email or index_number), the system:
  - Recognizes the student already exists
  - Enrolls the existing student in Teacher B's course
  - Does not create a duplicate account
- Students can log in once and see all courses they're enrolled in from all teachers
- Teachers only see students enrolled in their own courses

### Student Registration Flow
1. Teachers register students with names (used as temporary passwords)
2. System checks if student already exists by email or index_number
3. If student exists, enrolls them in teacher's course without duplication
4. If student doesn't exist, creates new account and enrolls in teacher's course
5. System generates unique index_numbers if not provided
6. Students receive login credentials (index_number or email + temporary password)
7. Students authenticate and must change password on first login

### Authentication Mechanism
- Student authentication uses HttpOnly cookies for token storage
- Access tokens expire after 30 minutes
- Refresh tokens are valid for 7 days
- Both tokens are automatically managed by the browser through cookies

### Password Management
- Temporary passwords are student names
- Students must change temporary passwords on first login
- Password strength requirements are enforced

## Implementation Details

### Student Registration
Teachers can register students individually or in bulk:

#### Single Student Registration
```javascript
// Register a single student
const registerStudent = async (studentData) => {
  try {
    const response = await fetch('/api/teacher/students/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${teacherAccessToken}`
      },
      body: JSON.stringify(studentData)
    });
    
    if (response.ok) {
      const student = await response.json();
      console.log('Student registered or enrolled:', student);
      // Student login_id indicates what the student will use to login
      // If newly_enrolled is true, student was enrolled in a new course
      // If newly_enrolled is false, student was already enrolled in this course
      return student;
    } else {
      throw new Error('Registration failed');
    }
  } catch (error) {
    console.error('Registration error:', error);
  }
};

// Student data format
const studentData = {
  name: "John Doe",           // Required
  email: "john@example.com",  // Optional
  index_number: "STU001",     // Optional
  subject: "Mathematics",     // Optional - for enrollment
  class_name: "Grade 10A"     // Optional - for enrollment
};
```

#### Bulk Student Registration
```javascript
// Register multiple students from CSV
const bulkRegisterStudents = async (csvFile, enrollmentData = {}) => {
  try {
    const formData = new FormData();
    formData.append('file', csvFile);
    
    const queryParams = new URLSearchParams(enrollmentData).toString();
    const response = await fetch(`/api/teacher/students/bulk-upload?${queryParams}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${teacherAccessToken}`
      },
      body: formData
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('Bulk registration result:', result);
      // Result includes created (new students), enrolled (existing students), and failed counts
      return result;
    } else {
      throw new Error('Bulk registration failed');
    }
  } catch (error) {
    console.error('Bulk registration error:', error);
  }
};

// CSV format example:
// name,email,index_number,subject,class_name
// John Doe,john@example.com,STU001,Mathematics,Grade 10A
// Jane Smith,jane@example.com,STU002,Science,Grade 10B
```

### Student Authentication
Students authenticate using index_number/email and temporary password:

#### Student Login
```javascript
// Student login (using index_number or email)
const studentLogin = async (loginId, password) => {
  try {
    const response = await fetch('/api/teacher/student/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        login_id: loginId,    // index_number or email
        password: password    // temporary password (name)
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Login successful:', data);
      // Student profile data is returned in response body
      // Browser automatically handles HttpOnly cookie storage
      // Student can now access all their courses from all teachers
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
  } catch (error) {
    console.error('Login error:', error);
  }
};
```

#### Student Password Change
```javascript
// Change temporary password
const changeStudentPassword = async (currentPassword, newPassword) => {
  try {
    const response = await fetch('/api/teacher/student/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Cookie is automatically sent by browser
      },
      body: JSON.stringify({
        current_password: currentPassword,  // temporary password (name)
        new_password: newPassword           // new password (min 8 characters)
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Password changed:', data);
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Password change failed');
    }
  } catch (error) {
    console.error('Password change error:', error);
  }
};
```

### Student Profile Access
Students can access their own profile information:

#### Get Current Student Profile
```javascript
// Get current student's profile
const getCurrentStudentProfile = async () => {
  try {
    const response = await fetch('/api/teacher/students/me', {
      method: 'GET',
      headers: {
        // Cookie is automatically sent by browser
      }
    });
    
    if (response.ok) {
      const student = await response.json();
      console.log('Student profile:', student);
      return student;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch profile');
    }
  } catch (error) {
    console.error('Profile fetch error:', error);
  }
};
```

### Student Course Access
Students can access information about all their courses:

#### Get Student Enrollments
```javascript
// Get all student's enrollments from all teachers
const getStudentEnrollments = async () => {
  try {
    const response = await fetch('/api/teacher/students/me/enrollments', {
      method: 'GET',
      headers: {
        // Cookie is automatically sent by browser
      }
    });
    
    if (response.ok) {
      const enrollments = await response.json();
      console.log('Student enrollments:', enrollments);
      return enrollments;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch enrollments');
    }
  } catch (error) {
    console.error('Enrollments fetch error:', error);
  }
};
```

### Student Management (Teacher)
Teachers can manage students in their courses:

#### List Students with Filtering
```javascript
// Get list of students enrolled in teacher's courses with pagination and filtering
const listStudents = async (options = {}) => {
  const {
    skip = 0,
    limit = 100,
    sortBy = 'created_at',
    sortOrder = 'desc',
    className = null,
    subject = null
  } = options;
  
  try {
    const queryParams = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
      sort_by: sortBy,
      sort_order: sortOrder
    });
    
    // Add optional filters
    if (className) queryParams.append('class_name', className);
    if (subject) queryParams.append('subject', subject);
    
    const response = await fetch(`/api/teacher/list-students?${queryParams.toString()}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${teacherAccessToken}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Students list:', data);
      // Only shows students enrolled in this teacher's courses
      // Filtered by class_name and/or subject if provided
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch students');
    }
  } catch (error) {
    console.error('List students error:', error);
  }
};

// Examples of usage:
// Get all students
listStudents();

// Get students in a specific class
listStudents({ className: 'Grade 10A' });

// Get students enrolled in a specific subject
listStudents({ subject: 'Mathematics' });

// Get students in a specific class and subject
listStudents({ className: 'Grade 10A', subject: 'Mathematics' });

// Get students with pagination and sorting
listStudents({ 
  skip: 0, 
  limit: 50, 
  sortBy: 'name', 
  sortOrder: 'asc',
  className: 'Grade 10A'
});
```

#### Delete Student
```javascript
// Remove student from teacher's course
const deleteStudent = async (studentId) => {
  try {
    const response = await fetch(`/api/teacher/students/${studentId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${teacherAccessToken}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Student removal result:', data);
      // If student_account_deleted is true, student account was deleted entirely
      // If student_account_deleted is false, student still has enrollments with other teachers
      return data;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to remove student');
    }
  } catch (error) {
    console.error('Remove student error:', error);
  }
};
```

## Error Handling
The API provides detailed error messages for various scenarios:

### Common Error Responses
```javascript
// HTTP 400 - Bad Request
{
  "detail": "At least one of email or index_number must be provided"
}

// HTTP 401 - Unauthorized
{
  "detail": "Could not validate credentials"
}

// HTTP 403 - Forbidden
{
  "detail": "Invalid Activation Token"
}

// HTTP 404 - Not Found
{
  "detail": "Student not found or not enrolled in your courses"
}

// HTTP 500 - Internal Server Error
{
  "detail": "Failed to register student: database error"
}
```

## Security Considerations
1. Tokens are stored in HttpOnly cookies and cannot be accessed by JavaScript
2. All API requests should be made over HTTPS in production
3. Password strength requirements are enforced (minimum 8 characters)
4. Temporary passwords (student names) should be changed immediately after first login
5. Access tokens expire after 30 minutes for security
6. Refresh tokens are valid for 7 days and automatically rotated

## Duplicate Handling
The system gracefully handles duplicate student registrations:
- When registering a student that already exists, the system enrolls them in the teacher's course without creating a duplicate account
- No error messages are returned for duplicate registrations
- If a subject is provided during registration and the student isn't already enrolled in that specific course, a new enrollment is created
- This applies to both single and bulk registration endpoints

## Selective Deletion
The student deletion endpoint implements selective deletion:
- When a teacher deletes a student, only the enrollment in the teacher's courses is removed
- If the student has no other enrollments, their entire account is deleted
- The response indicates whether the student account was deleted or if they still have enrollments with other teachers

## Filtering Students
Teachers can filter the student list by class name and subject:
- **Class Name Filter**: Shows only students enrolled in a specific class
- **Subject Filter**: Shows only students enrolled in a specific subject
- **Combined Filters**: Use both filters together for more specific results
- **Pagination Compatible**: All filtering works with pagination
- **Sorting Compatible**: Results can be sorted while applying filters

Example usage:
```javascript
// Filter by class
const studentsInGrade10A = await listStudents({ className: 'Grade 10A' });

// Filter by subject
const mathStudents = await listStudents({ subject: 'Mathematics' });

// Filter by both class and subject
const mathStudentsInGrade10A = await listStudents({ 
  className: 'Grade 10A', 
  subject: 'Mathematics' 
});
```

## Testing
Example test scenarios:

### Student Login Test
```javascript
describe('Student Login', () => {
  it('should login with index_number and temporary password', async () => {
    const response = await fetch('/api/teacher/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        login_id: 'STU001',
        password: 'John Doe'  // temporary password (name)
      })
    });
    
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('access_token');
    expect(data).toHaveProperty('student');
    expect(data.student.name).toBe('John Doe');
  });
});
```

### Password Change Test
```javascript
describe('Student Password Change', () => {
  it('should change temporary password', async () => {
    // First login to get cookies
    await fetch('/api/teacher/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        login_id: 'STU001',
        password: 'John Doe'
      })
    });
    
    // Then change password
    const response = await fetch('/api/teacher/student/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: 'John Doe',
        new_password: 'NewSecurePassword123'
      })
    });
    
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.message).toBe('Password changed successfully');
  });
});
```