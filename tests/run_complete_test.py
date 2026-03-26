"""
RUN COMPLETE FLOW TEST

This script:
1. Clears test data
2. Runs the complete flow test
3. Shows results

Usage: python run_complete_test.py
"""

import asyncio
import subprocess
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def print_header(title):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print()


async def main():
    print_header("COMPLETE FLOW TEST RUNNER")
    
    # Step 1: Clear test data
    print_header("STEP 1: Clearing Test Data")
    print("Running: python slide_builder/clear_test_data.py")
    print()
    
    result = subprocess.run(
        [sys.executable, "slide_builder/clear_test_data.py"],
        capture_output=False
    )
    
    if result.returncode != 0:
        print()
        print("❌ Failed to clear test data")
        return
    
    # Step 2: Run complete flow test
    print()
    print_header("STEP 2: Running Complete Flow Test")
    print("Running: python slide_builder/test_complete_flow.py")
    print()
    print("This will test:")
    print("  1. Database connection")
    print("  2. Session finding")
    print("  3. Curriculum retrieval")
    print("  4. RAG retrieval")
    print("  5. AI slide generation")
    print("  6. Slide saving")
    print("  7. Image prompt saving")
    print("  8. Image generation")
    print("  9. Student lesson pack generation ⭐ NEW")
    print()
    print("Please wait... (this may take several minutes)")
    print()
    
    result = subprocess.run(
        [sys.executable, "slide_builder/test_complete_flow.py"],
        capture_output=False
    )
    
    print()
    if result.returncode == 0:
        print_header("✅ TEST COMPLETED")
        print("Check slide_builder/test_flow.log for detailed results")
    else:
        print_header("⚠️ TEST COMPLETED WITH ISSUES")
        print("Check slide_builder/test_flow.log for details")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
