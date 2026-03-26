#!/usr/bin/env python3
"""
Startup Verification Script for TMDL5

This script checks if all required services are running correctly.
Run this after starting your services to verify everything is working.
"""

import asyncio
import requests
import redis
import json
from arq import create_pool
from app.sch_ground.background import arq_redis_settings

async def check_redis():
    """Check if Redis is running"""
    try:
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        print("✅ Redis: Running")
        return True
    except Exception as e:
        print(f"❌ Redis: Not running - {e}")
        return False

async def check_fastapi():
    """Check if FastAPI server is running"""
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ FastAPI Server: Running on http://localhost:8000")
            return True
        else:
            print(f"❌ FastAPI Server: Bad response - {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FastAPI Server: Not running - {e}")
        return False

async def check_arq_connection():
    """Check if ARQ can connect to Redis"""
    try:
        redis_pool = await create_pool(arq_redis_settings)
        await redis_pool.ping()
        await redis_pool.aclose()
        print("✅ ARQ Connection: Working")
        return True
    except Exception as e:
        print(f"❌ ARQ Connection: Failed - {e}")
        return False

async def check_websocket_listener():
    """Check if WebSocket Redis listener is working"""
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        # Check if there are any active pub/sub channels
        channels = r.pubsub_channels("ws:*")
        print("✅ WebSocket Listener: Ready")
        return True
    except Exception as e:
        print(f"❌ WebSocket Listener: Error - {e}")
        return False

def print_startup_summary():
    """Print helpful startup information"""
    print("\n" + "="*50)
    print("🚀 TMDL5 STARTUP VERIFICATION")
    print("="*50)
    
def print_next_steps():
    """Print what to do next"""
    print("\n" + "="*50)
    print("🎯 NEXT STEPS")
    print("="*50)
    print("1. 📱 Frontend: Connect to http://localhost:8000")
    print("2. 📄 Upload a timetable file via /timetable/upload")
    print("3. 🔌 Connect WebSocket to /ws/{teacher_id} for real-time updates")
    print("4. 📊 Check API docs at http://localhost:8000/api/docs")
    print("\n💡 Test with this curl command:")
    print('curl -X GET "http://localhost:8000/" -H "accept: application/json"')
    print("="*50)

async def main():
    """Main verification function"""
    print_startup_summary()
    
    # Check all services
    results = []
    results.append(await check_redis())
    results.append(await check_fastapi())
    results.append(await check_arq_connection())
    results.append(await check_websocket_listener())
    
    # Summary
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n📊 Status: {success_count}/{total_count} services running")
    
    if success_count == total_count:
        print("🎉 All services are running! System ready.")
        print_next_steps()
    else:
        print("⚠️  Some services are not running. Check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("- Make sure Redis is running: redis-server")
        print("- Make sure FastAPI is running: python main.py")
        print("- Check if ports 6379 (Redis) and 8000 (FastAPI) are available")

if __name__ == "__main__":
    asyncio.run(main())