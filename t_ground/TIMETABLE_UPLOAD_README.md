# Timetable Upload System with AI Processing

This system allows teachers to upload their existing timetables and have AI automatically extract and organize the data.

## 🚀 Features

- **File Upload**: Support for PNG, JPG, JPEG, WebP, GIF, PDF, DOC, DOCX, XLS, XLSX, and TXT files
- **AI Processing**: Uses Google Gen AI (Gemini 2.5 Flash) for accurate timetable extraction
- **User Review**: Interactive interface to review and correct AI extractions
- **Database Integration**: Saves to your existing `WeeklyTimeTable` model
- **Authentication**: Integrated with your existing teacher authentication system
- **Error Handling**: Comprehensive error handling and validation

## 📁 Files Added/Modified

### New Files:
- `timetable_routes.py` - Main API endpoints for timetable operations
- `test_timetable.py` - Test script for the upload functionality
- `TIMETABLE_UPLOAD_README.md` - This documentation

### Modified Files:
- `main.py` - Added timetable routes
- `config.py` - Added API_KEY configuration
- `requirements.txt` - Added google-generativeai dependency

## 🔧 Setup Instructions

### 1. Install Dependencies
```bash
pip install google-genai==0.3.0
```

### 2. Configure API Key
Add your Google Gen AI API key to your `.env` file:
```env
API_KEY=your_actual_google_genai_api_key_here
```

### 3. Start Your Backend
```bash
python main.py
```

## 📡 API Endpoints

### 1. Upload Timetable
```http
POST /api/upload-timetable
Content-Type: multipart/form-data

file: [timetable image, PDF, Word, Excel, or text file]
```

**Response:**
```json
{
  "file_id": "uuid-string",
  "message": "File uploaded successfully",
  "filename": "timetable.jpg",
  "size": 123456
}
```

### 2. Process with AI
```http
POST /api/process-timetable/{file_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "timeSlots": [
    {"start": "08:00", "end": "09:00"},
    {"start": "09:00", "end": "10:00"}
  ],
  "subjects": [
    {
      "day": "Monday",
      "timeSlot": 0,
      "subjectName": "Mathematics",
      "duration": 60,
      "confidence": 0.85
    }
  ]
}
```

### 3. Save Timetable
```http
POST /api/save-timetable
Authorization: Bearer <token>
Content-Type: application/json

{
  "days": [...],
  "timeSlots": [...],
  "subjects": [...]
}
```

**Response:**
```json
{
  "message": "Timetable saved successfully",
  "entries_saved": 15,
  "teacher_id": "uuid-string"
}
```

### 4. Get Timetable
```http
GET /api/get-timetable
Authorization: Bearer <token>
```

**Response:**
```json
{
  "teacher_id": "uuid-string",
  "timetable": {
    "monday": [
      {
        "id": 1,
        "subject": "Mathematics",
        "start_time": "08:00",
        "end_time": "09:00",
        "pupils": "",
        "location": ""
      }
    ]
  }
}
```

## 🧪 Testing

### Run the Test Script
```bash
python test_timetable.py
```

**Note:** You'll need to add a test timetable image named `test_timetable.jpg` to run the tests.

### Manual Testing
1. Start your backend server
2. Use the frontend upload interface
3. Check the API documentation at `http://localhost:8001/api/docs`

## 🔒 Security Features

- **Authentication Required**: All endpoints require valid teacher authentication
- **File Validation**: Supports images (PNG, JPG, JPEG, WebP, GIF), documents (PDF, DOC, DOCX, XLS, XLSX), and text files
- **Temporary Storage**: Files are stored temporarily and cleaned up automatically
- **Input Validation**: All inputs are validated before processing

## 🐛 Error Handling

The system handles various error scenarios:

- **Invalid File Type**: Returns 400 with clear error message
- **File Too Large**: Returns 400 for files > 10MB
- **AI Processing Failures**: Returns 500 with detailed error
- **Database Errors**: Returns 500 with rollback protection
- **Authentication Failures**: Returns 401/403 as appropriate

## 📊 Database Schema

The system uses your existing `WeeklyTimeTable` model:

```python
class WeeklyTimeTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id")
    weekday: str
    pupils: str
    subject: str
    start_time: str
    end_time: str
    location: Optional[str] = None
```

## 🔄 Integration with Frontend

The frontend components (`TimetableUpload.jsx` and `TimetableReview.jsx`) are already configured to work with these endpoints:

1. **Upload Flow**: Frontend → `/api/upload-timetable`
2. **AI Processing**: Frontend → `/api/process-timetable/{file_id}`
3. **Save Flow**: Frontend → `/api/save-timetable`

## 🚨 Important Notes

1. **API Key Security**: Never commit your API key to version control
2. **File Cleanup**: Temporary files are automatically cleaned up
3. **Document Support**: Full support for PDF, Word, Excel, and text files
4. **Rate Limiting**: Consider adding rate limiting for production use
5. **Error Logging**: All errors are logged for debugging

## 🎯 Next Steps

1. **Test the system** with real timetable images
2. **Test with various document types** (PDF, Word, Excel)
3. **Implement rate limiting** for production
4. **Add file compression** for large images
5. **Enhance AI prompts** for better accuracy

## 🆘 Troubleshooting

### Common Issues:

1. **"API_KEY not found"**: Check your `.env` file
2. **"File not found"**: Ensure the file was uploaded successfully
3. **"Invalid JSON"**: The AI response couldn't be parsed
4. **"Database error"**: Check your database connection

### Debug Mode:
Enable debug logging by setting the log level in your logger configuration.

---

**🎉 Your AI-powered timetable upload system is ready to use!** 