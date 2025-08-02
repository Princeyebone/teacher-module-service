import subprocess
import sys

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlmodel",
    "alembic",
    "psycopg2-binary",
    "celery[redis]",
    "redis",
    "google-generativeai"
]

def install_missing_packages():
    for package in REQUIRED_PACKAGES:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "show", package.split("[")[0]])
        except subprocess.CalledProcessError:
            print(f"⚠️ Installing missing package: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if __name__ == "__main__":
    install_missing_packages()
    print("✅ All dependencies installed!")
