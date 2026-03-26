import os
import re

ROOT = r"c:\Users\HP\tmdl5"
APP_DIR = os.path.join(ROOT, "app")

# All subdirectory modules that moved under app/
APP_SUBDIRS = [
    "sch_ground", "t_ground", "ca_ground", "semplan_ground",
    "curri_back", "rag_back", "outline_back", "free_back",
    "student_back", "slide_builder", "lesson_notes", "brief_sche",
    "file_handler", "rag",
]

# Explicit top-level module renames
EXPLICIT = [
    # Core
    ("from config import",              "from app.core.config import"),
    ("from database import",            "from app.core.database import"),
    ("from dependencies import",        "from app.core.dependencies import"),
    ("from logger import",              "from app.core.logger import"),
    ("from websocket_manager import",   "from app.core.websocket_manager import"),
    ("from service_auth import",        "from app.core.service_auth import"),
    # Models
    ("from model import",               "from app.models.model import"),
    ("from student import",             "from app.models.student import"),
    ("from schemas import",             "from app.schemas.schemas import"),
    # Services
    ("from gcs_utils import",           "from app.services.gcs_utils import"),
    ("from schedule_utils import",      "from app.services.schedule_utils import"),
    ("from gradeweights import",        "from app.services.gradeweights import"),
    ("from score import",               "from app.services.score import"),
    ("from semester_mapper import",     "from app.services.semester_mapper import"),
    ("from external_service import",    "from app.services.external_service import"),
    ("from enque_task import",          "from app.services.enque_task import"),
    # gRPC
    ("from grpc_server import",         "from app.teacher_grpc.grpc_server import"),
    ("from teacher_pb2 import",         "from app.teacher_grpc.teacher_pb2 import"),
    ("from teacher_pb2_grpc import",    "from app.teacher_grpc.teacher_pb2_grpc import"),
    # Routers
    ("from auths_routes import",        "from app.api.routers.auths_routes import"),
    ("from profile_routes import",      "from app.api.routers.profile_routes import"),
    ("from teacher_crud import",        "from app.api.routers.teacher_crud import"),
    ("from timetable_crud import",      "from app.api.routers.timetable_crud import"),
    ("from calendar_crud import",       "from app.api.routers.calendar_crud import"),
    ("from productivity import",        "from app.api.routers.productivity import"),
    ("from notifications_crud import",  "from app.api.routers.notifications_crud import"),
    ("from main_calendar_crud import",  "from app.api.routers.main_calendar_crud import"),
    ("from grade_crud import",          "from app.api.routers.grade_crud import"),
    ("from student_auth import",        "from app.api.routers.student_auth import"),
    ("from student_read import",        "from app.api.routers.student_read import"),
    ("from publishing import",          "from app.api.routers.publishing import"),
    ("from monitering import",          "from app.api.routers.monitering import"),
    ("from answer import",              "from app.api.routers.answer import"),
    ("from todays_overview import",     "from app.api.routers.todays_overview import"),
    ("from assessment import",          "from app.api.routers.assessment import"),
]


def fix_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        enc = "utf-8"
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="latin-1") as f:
            content = f.read()
        enc = "latin-1"

    orig = content

    # 1. Fix "from subdir.xxx import ..." -> "from app.subdir.xxx import ..."
    #    and "import subdir.xxx as yyy" -> "import app.subdir.xxx as yyy"
    for subdir in APP_SUBDIRS:
        esc = re.escape(subdir)
        # from subdir.X import Y  ->  from app.subdir.X import Y
        content = re.sub(
            rf"^(\s*)from {esc}\.",
            rf"\1from app.{subdir}.",
            content, flags=re.MULTILINE
        )
        # import subdir.X [as Y]  ->  import app.subdir.X [as Y]
        content = re.sub(
            rf"^(\s*)import {esc}\.",
            rf"\1import app.{subdir}.",
            content, flags=re.MULTILINE
        )

    # 2. Apply explicit replacement pairs
    for old, new in EXPLICIT:
        esc_old = re.escape(old)
        content = re.sub(
            rf"^(\s*){esc_old}",
            lambda m, new=new: m.group(1) + new,
            content, flags=re.MULTILINE
        )

    if content != orig:
        with open(filepath, "w", encoding=enc) as f:
            f.write(content)
        print(f"  Fixed: {os.path.relpath(filepath, ROOT)}")


def main():
    scan_dirs = [APP_DIR, os.path.join(ROOT, "tests"), os.path.join(ROOT, "scripts")]
    for scan_dir in scan_dirs:
        for root_dir, _, files in os.walk(scan_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fix_file(os.path.join(root_dir, fname))
    print("Done.")


if __name__ == "__main__":
    main()
