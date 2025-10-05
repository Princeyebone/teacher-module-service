import os
from file_handler.tm_file_handler import save_file
from fastapi import UploadFile
from io import BytesIO

# Test the file naming convention
async def test_file_naming():
    # Create a mock UploadFile
    file_content = b"This is a test timetable file"
    file_bytes = BytesIO(file_content)
    
    # Create a mock UploadFile object
    class MockUploadFile:
        def __init__(self, filename, content):
            self.filename = filename
            self.content = content
            
        async def read(self):
            return self.content
    
    mock_file = MockUploadFile("test_timetable.pdf", file_content)
    
    # Test saving with the new naming convention
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    file_path = await save_file(mock_file, teacher_id)
    
    print(f"File saved to: {file_path}")
    
    # Verify the file was created with the correct naming convention
    expected_path = f"./uploads/timetable/{teacher_id}.pdf"
    if file_path == expected_path:
        print("✅ File naming convention is correct!")
    else:
        print(f"❌ File naming convention is incorrect. Expected: {expected_path}, Got: {file_path}")
    
    # Check if file exists
    if os.path.exists(file_path):
        print("✅ File was created successfully!")
        # Clean up test file
        os.remove(file_path)
        # Also try to remove the directory if it's empty
        try:
            os.rmdir(os.path.dirname(file_path))
        except OSError:
            pass  # Directory not empty, that's fine
    else:
        print("❌ File was not created!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_file_naming())