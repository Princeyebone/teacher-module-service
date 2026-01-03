"""
Test script to verify student support pack creation works
"""
import requests
import json

# API endpoint
BASE_URL = "http://localhost:8001"

# You'll need to replace this with a valid teacher token
# Get it from your login endpoint or use an existing one
TEACHER_TOKEN = "YOUR_TEACHER_TOKEN_HERE"

headers = {
    "Authorization": f"Bearer {TEACHER_TOKEN}",
    "Content-Type": "application/json"
}

# Test data
test_data = {
    "student_name": "Test Student",
    "subject": "Mathematics",
    "class_name": "Grade 10",
    "topic": "Quadratic Equations",
    "interests": ["sports", "music", "technology"],
    "health_considerations": "None"
}

print("=" * 60)
print("Testing Student Support Pack Creation")
print("=" * 60)
print(f"\nRequest Data:")
print(json.dumps(test_data, indent=2))

try:
    response = requests.post(
        f"{BASE_URL}/api/teacher/student-support",
        headers=headers,
        json=test_data,
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Student support pack created.")
        pack_id = response.json().get("pack_id")
        print(f"Pack ID: {pack_id}")
        print("\nThe worker will pick this up and generate the content.")
    else:
        print("\n❌ FAILED!")
        
except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: Could not connect to server at", BASE_URL)
    print("Make sure the FastAPI server is running on port 8001")
except Exception as e:
    print(f"\n❌ ERROR: {e}")

print("\n" + "=" * 60)
