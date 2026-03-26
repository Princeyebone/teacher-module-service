"""
File Handler Package

This package contains all file upload and processing handlers for different types
of files in the TMDL5 system.

Modules:
- ca_file_handler: Calendar file upload and processing
- sem_file_handler: Semester mapping file upload and processing  
- tm_file_handler: Timetable file upload and processing

Each handler provides FastAPI routers for file upload endpoints and processing logic.
"""

__all__ = ['ca_file_handler', 'sem_file_handler', 'tm_file_handler']