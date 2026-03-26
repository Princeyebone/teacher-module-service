import os
import re
import shutil

# The root directory
ROOT = r"c:\Users\HP\tmdl5"
APP_DIR = os.path.join(ROOT, "app")

# Directories to create
DIRS = [
    "app",
    "app/api/routers",
    "app/core",
    "app/models",
    "app/schemas",
    "app/services",
    "app/grpc",
]

# File mappings (source -> destination)
FILE_MAP = {
    "auths_routes.py": "app/api/routers/auths_routes.py",
    "profile_routes.py": "app/api/routers/profile_routes.py",
    "teacher_crud.py": "app/api/routers/teacher_crud.py",
    "timetable_crud.py": "app/api/routers/timetable_crud.py",
    "calendar_crud.py": "app/api/routers/calendar_crud.py",
    "main_calendar_crud.py": "app/api/routers/main_calendar_crud.py",
    "notifications_crud.py": "app/api/routers/notifications_crud.py",
    "grade_crud.py": "app/api/routers/grade_crud.py",
    "student_auth.py": "app/api/routers/student_auth.py",
    "student_read.py": "app/api/routers/student_read.py",
    "publishing.py": "app/api/routers/publishing.py",
    "monitering.py": "app/api/routers/monitering.py",
    "answer.py": "app/api/routers/answer.py",
    "todays_overview.py": "app/api/routers/todays_overview.py",
    "productivity.py": "app/api/routers/productivity.py",
    "assessment.py": "app/api/routers/assessment.py",

    "config.py": "app/core/config.py",
    "database.py": "app/core/database.py",
    "dependencies.py": "app/core/dependencies.py",
    "logger.py": "app/core/logger.py",
    "websocket_manager.py": "app/core/websocket_manager.py",
    "service_auth.py": "app/core/service_auth.py",

    "model.py": "app/models/model.py",
    "student.py": "app/models/student.py",
    "schemas.py": "app/schemas/schemas.py",

    "gcs_utils.py": "app/services/gcs_utils.py",
    "schedule_utils.py": "app/services/schedule_utils.py",
    "gradeweights.py": "app/services/gradeweights.py",
    "score.py": "app/services/score.py",
    "semester_mapper.py": "app/services/semester_mapper.py",
    "external_service.py": "app/services/external_service.py",
    "enque_task.py": "app/services/enque_task.py",

    "grpc_server.py": "app/grpc/grpc_server.py",
    "teacher_pb2.py": "app/grpc/teacher_pb2.py",
    "teacher_pb2_grpc.py": "app/grpc/teacher_pb2_grpc.py",
    "teacher.proto": "app/grpc/teacher.proto",
    
    "main.py": "app/main.py",
}

# Directories to move wholesale into app/
SUBDIRS_TO_MOVE = [
    "file_handler", "rag", "t_ground", "sch_ground", "semplan_ground",
    "student_back", "curri_back", "rag_back", "outline_back", "free_back",
    "ca_ground", "brief_sche", "slide_builder", "lesson_notes"
]

# Module mappings for import rewriting
MODULE_MAP = {
    # Routers
    "auths_routes": "app.api.routers.auths_routes",
    "profile_routes": "app.api.routers.profile_routes",
    "teacher_crud": "app.api.routers.teacher_crud",
    "timetable_crud": "app.api.routers.timetable_crud",
    "calendar_crud": "app.api.routers.calendar_crud",
    "main_calendar_crud": "app.api.routers.main_calendar_crud",
    "notifications_crud": "app.api.routers.notifications_crud",
    "grade_crud": "app.api.routers.grade_crud",
    "student_auth": "app.api.routers.student_auth",
    "student_read": "app.api.routers.student_read",
    "publishing": "app.api.routers.publishing",
    "monitering": "app.api.routers.monitering",
    "answer": "app.api.routers.answer",
    "todays_overview": "app.api.routers.todays_overview",
    "productivity": "app.api.routers.productivity",
    "assessment": "app.api.routers.assessment",

    # Core
    "config": "app.core.config",
    "database": "app.core.database",
    "dependencies": "app.core.dependencies",
    "logger": "app.core.logger",
    "websocket_manager": "app.core.websocket_manager",
    "service_auth": "app.core.service_auth",

    # Models
    "model": "app.models.model",
    "schemas": "app.schemas.schemas",
    "student": "app.models.student",

    # Services
    "gcs_utils": "app.services.gcs_utils",
    "schedule_utils": "app.services.schedule_utils",
    "gradeweights": "app.services.gradeweights",
    "score": "app.services.score",
    "semester_mapper": "app.services.semester_mapper",
    "external_service": "app.services.external_service",
    "enque_task": "app.services.enque_task",

    # GRPC
    "grpc_server": "app.teacher_grpc.grpc_server",
    "teacher_pb2": "app.teacher_grpc.teacher_pb2",
    "teacher_pb2_grpc": "app.teacher_grpc.teacher_pb2_grpc",
}

def create_dirs():
    for d in DIRS:
        full_path = os.path.join(ROOT, d)
        os.makedirs(full_path, exist_ok=True)
        # add __init__.py
        with open(os.path.join(full_path, "__init__.py"), "w") as f:
            pass

def move_files():
    for src_name, dest_path in FILE_MAP.items():
        src = os.path.join(ROOT, src_name)
        dest = os.path.join(ROOT, dest_path)
        if os.path.exists(src):
            shutil.move(src, dest)
            print(f"Moved {src_name} -> {dest_path}")
            
    for subdir in SUBDIRS_TO_MOVE:
        src = os.path.join(ROOT, subdir)
        dest = os.path.join(APP_DIR, subdir)
        if os.path.exists(src):
            shutil.move(src, dest)
            print(f"Moved {subdir} -> app/{subdir}")

def refactor_imports():
    # Walk all .py files in app, tests, and scripts directories
    for target_dir in [APP_DIR, os.path.join(ROOT, "tests"), os.path.join(ROOT, "scripts")]:
        for root_dir, _, files in os.walk(target_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue
            
            filepath = os.path.join(root_dir, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                file_encoding = "utf-8"
            except UnicodeDecodeError:
                with open(filepath, "r", encoding="latin-1") as f:
                    content = f.read()
                file_encoding = "latin-1"

            orig_content = content
            
            # Subdirectories we moved don't exactly need "app." prefix unless we want absolute root imports, 
            # let's prefix subdirectories too so everything is absolute from root
            for subdir in SUBDIRS_TO_MOVE:
                MODULE_MAP[subdir] = f"app.{subdir}"

            for old_mod, new_mod in MODULE_MAP.items():
                # 1. import A -> import new_A
                content = re.sub(rf"^(\s*)import {old_mod}\b", r"\1import " + f"{new_mod}", content, flags=re.MULTILINE)
                content = re.sub(rf"^(\s*)import {old_mod} as\b", r"\1import " + f"{new_mod} as", content, flags=re.MULTILINE)
                content = re.sub(rf"^(\s*)from {old_mod} import\b", r"\1from " + f"{new_mod} import", content, flags=re.MULTILINE)
                content = re.sub(rf"^(\s*)from {old_mod}\.", r"\1from " + f"{new_mod}.", content, flags=re.MULTILINE)

            if orig_content != content:
                with open(filepath, "w", encoding=file_encoding) as f:
                    f.write(content)
                print(f"Updated imports in {file}")

if __name__ == "__main__":
    create_dirs()
    move_files()
    refactor_imports()
    print("Refactoring complete.")
