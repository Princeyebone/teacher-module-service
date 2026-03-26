#!/usr/bin/env python3
"""
Test script to verify detailed logging functionality in text.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_logging():
    """Test the detailed logging functionality."""
    print("Testing detailed logging functionality...")
    
    # Check if log file exists
    log_file = "text_extraction_detailed.log"
    if os.path.exists(log_file):
        print(f"✓ Log file '{log_file}' exists")
        
        # Read and display last 20 lines of log file
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"\nLast 20 lines of '{log_file}':")
            print("-" * 50)
            for line in lines[-20:]:
                print(line.strip())
            print("-" * 50)
    else:
        print(f"✗ Log file '{log_file}' does not exist")
        
    print("\nTest completed.")

if __name__ == "__main__":
    test_logging()