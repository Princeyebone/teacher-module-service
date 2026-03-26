#!/usr/bin/env python3
"""
Simple test to verify the read endpoints are working
"""

def test_imports():
    """Test that we can import the necessary modules"""
    try:
        # Test importing the semester_mapper module
        import semester_mapper
        print("✅ Successfully imported semester_mapper")
        
        # Check if the read endpoints exist
        import inspect
        members = inspect.getmembers(semester_mapper)
        read_endpoints = [name for name, obj in members if name.startswith('read_') and callable(obj)]
        print(f"✅ Found read endpoints: {read_endpoints}")
        
        # Check if the router has the endpoints
        router_endpoints = []
        for route in semester_mapper.router.routes:
            if hasattr(route, 'name') and route.name and route.name.startswith('read_'):
                router_endpoints.append(route.name)
        print(f"✅ Found router endpoints: {router_endpoints}")
        
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()