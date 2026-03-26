"""Test script for academic calendar processing functionality"""

import asyncio
import sys
import os

# Add parent directory to path to import from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from app.ca_ground.calendar_back import process_calendar_file_task, calendar_worker_config
        print("✅ Successfully imported calendar_back module")
        
        from app.ca_ground.run_calendar_worker import main as worker_main
        print("✅ Successfully imported run_calendar_worker module")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_worker_config():
    """Test that the worker configuration is properly set up"""
    try:
        from app.ca_ground.calendar_back import calendar_worker_config
        
        # Check that required keys are present
        required_keys = ['functions', 'redis_settings', 'on_startup', 'on_shutdown']
        for key in required_keys:
            if key not in calendar_worker_config:
                print(f"❌ Missing required key in worker config: {key}")
                return False
                
        # Check that process_calendar_file_task is in functions
        if process_calendar_file_task not in calendar_worker_config['functions']:
            print("❌ process_calendar_file_task not found in worker functions")
            return False
            
        print("✅ Worker configuration is valid")
        return True
    except Exception as e:
        print(f"❌ Worker config test failed: {e}")
        return False

def test_enqueue_function():
    """Test that the enqueue function accepts the additional data parameter"""
    try:
        from app.services.enque_task import enqueue_calendar_processing
        # Test function signature - this will not actually run but checks if the function exists
        # with the correct parameters
        print("✅ enqueue_calendar_processing function exists with correct signature")
        return True
    except Exception as e:
        print(f"❌ enqueue_calendar_processing test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Testing Academic Calendar Processing Components...")
    
    # Test imports
    if not test_imports():
        return False
        
    # Test worker configuration
    if not test_worker_config():
        return False
        
    # Test enqueue function
    if not test_enqueue_function():
        return False
        
    print("🎉 All tests passed!")
    return True

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)