"""
Diagnose Redis Queue Status
"""
import asyncio
import redis.asyncio as redis

async def diagnose():
    print("=" * 60)
    print("REDIS QUEUE DIAGNOSTIC")
    print("=" * 60)
    
    # Connect to Redis DB 7 (slide queue)
    r = redis.Redis(host='localhost', port=6379, db=7)
    
    try:
        # Check connection
        pong = await r.ping()
        print(f"✅ Redis connection: {'OK' if pong else 'FAILED'}")
        
        # Check all keys
        keys = await r.keys('*')
        print(f"\n📦 Keys in DB 7: {len(keys)}")
        for key in keys[:20]:
            key_type = await r.type(key)
            print(f"   - {key.decode()}: {key_type.decode()}")
        
        # Check the queue specifically
        queue_key = b'arq:queue:slide_queue'
        queue_len = await r.llen(queue_key)
        print(f"\n📋 Jobs in slide_queue: {queue_len}")
        
        if queue_len > 0:
            # Peek at jobs
            jobs = await r.lrange(queue_key, 0, 5)
            for job in jobs:
                print(f"   Job: {job[:100]}...")
        
        # Check for any result keys
        result_keys = [k for k in keys if b'result' in k]
        print(f"\n📊 Result keys: {len(result_keys)}")
        for rk in result_keys[:5]:
            print(f"   - {rk.decode()}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await r.aclose()

if __name__ == "__main__":
    asyncio.run(diagnose())
