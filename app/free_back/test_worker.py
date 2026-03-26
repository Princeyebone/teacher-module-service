"""
Test Free Plan Worker - Run single worker to see errors
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import and run
from app.free_back.free_worker import main

if __name__ == "__main__":
    print("=" * 70)
    print("Testing Free Plan Worker")
    print("=" * 70)
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
