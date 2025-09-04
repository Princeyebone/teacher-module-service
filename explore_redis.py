#!/usr/bin/env python3
"""
Redis Explorer for TMDL5 Background Tasks

This script helps you understand what's happening in Redis
when your background tasks are running.
"""

import redis
import json
from datetime import datetime

def safe_decode(data):
    """Safely decode binary data to string"""
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('utf-8', errors='replace')
    return str(data)

def connect_redis():
    """Connect to Redis and test the connection"""
    try:
        # Connect without decode_responses to handle binary data
        r = redis.Redis(host='localhost', port=6379, decode_responses=False)
        r.ping()
        print("✅ Connected to Redis successfully!")
        
        # Show basic info
        info = r.info()
        redis_version = info.get(b'redis_version', b'unknown').decode('utf-8', errors='ignore')
        print(f"📊 Redis version: {redis_version}")
        
        # Count keys safely
        try:
            total_keys = len(r.keys(b'*'))
            print(f"🔑 Total keys: {total_keys}")
        except Exception:
            print("🔑 Total keys: Unable to count")
        
        return r
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        print("💡 Make sure Redis is running: redis-server")
        print("💡 On Windows, you can install Redis via: https://github.com/microsoftarchive/redis/releases")
        return None

def explore_redis_keys(r):
    """See what keys are stored in Redis"""
    print("\n🔍 What's in Redis:")
    print("=" * 40)
    
    try:
        keys = r.keys(b'*')
        if not keys:
            print("📭 Redis is empty - no tasks yet")
            print("💡 Try starting your FastAPI server and timetable worker, then upload a file!")
            return
        
        # Group keys by type for better understanding
        key_groups = {}
        for key in keys:
            try:
                key_str = safe_decode(key)
                key_type = safe_decode(r.type(key))
                
                if key_type not in key_groups:
                    key_groups[key_type] = []
                key_groups[key_type].append((key, key_str))
            except Exception as e:
                print(f"❌ Error processing key {key}: {e}")
        
        for key_type, type_keys in key_groups.items():
            print(f"\n📂 {key_type.upper()} keys ({len(type_keys)}):")
            
            for key, key_str in type_keys[:5]:  # Show first 5 keys of each type
                print(f"📝 {key_str}")
                
                try:
                    if key_type == 'string':
                        value = r.get(key)
                        value_str = safe_decode(value) if value else "None"
                        if len(value_str) > 100:
                            print(f"   Value: {value_str[:100]}... (truncated)")
                        else:
                            print(f"   Value: {value_str}")
                    elif key_type == 'list':
                        try:
                            length = r.llen(key)
                            print(f"   List length: {length}")
                            if length > 0:
                                items = r.lrange(key, 0, 2)  # Show first 3 items
                                for i, item in enumerate(items):
                                    item_str = safe_decode(item)
                                    if len(item_str) > 50:
                                        print(f"   [{i}]: {item_str[:50]}... (truncated)")
                                    else:
                                        print(f"   [{i}]: {item_str}")
                        except Exception as e:
                            print(f"   ❌ Error reading list: {e}")
                    elif key_type == 'hash':
                        try:
                            hash_keys = r.hkeys(key)
                            hash_keys_str = [safe_decode(k) for k in hash_keys[:5]]
                            print(f"   Hash keys: {hash_keys_str}")
                            
                            # Try to get function if it exists
                            if b'function' in hash_keys:
                                func_value = r.hget(key, b'function')
                                print(f"   Function: {safe_decode(func_value)}")
                        except Exception as e:
                            print(f"   ❌ Error reading hash: {e}")
                    elif key_type == 'set':
                        try:
                            size = r.scard(key)
                            print(f"   Set size: {size}")
                        except Exception as e:
                            print(f"   ❌ Error reading set: {e}")
                    elif key_type == 'zset':
                        try:
                            size = r.zcard(key)
                            print(f"   Sorted set size: {size}")
                        except Exception as e:
                            print(f"   ❌ Error reading sorted set: {e}")
                        
                except Exception as e:
                    print(f"   ❌ Error reading key: {e}")
                
                print()
            
            if len(type_keys) > 5:
                print(f"   ... and {len(type_keys) - 5} more {key_type} keys")
    
    except Exception as e:
        print(f"❌ Error exploring Redis keys: {e}")

def monitor_tasks(r):
    """Watch for new tasks being added to Redis"""
    print("\n👀 Monitoring for new tasks...")
    print("   (Upload a file in another terminal to see tasks appear)")
    print("   Press Ctrl+C to stop\n")
    
    try:
        while True:
            # Look for ARQ job keys
            try:
                arq_keys = r.keys(b'arq:job:*')
                if arq_keys:
                    print(f"📊 Found {len(arq_keys)} ARQ jobs:")
                    for key in arq_keys[:3]:  # Show first 3
                        try:
                            key_str = safe_decode(key)
                            key_type = safe_decode(r.type(key))
                            print(f"   🔧 Job: {key_str} (type: {key_type})")
                            
                            if key_type == 'hash':
                                try:
                                    job_data = r.hgetall(key)
                                    if job_data:
                                        function = safe_decode(job_data.get(b'function', b'unknown'))
                                        status = safe_decode(job_data.get(b'status', b'unknown'))
                                        enqueue_time = safe_decode(job_data.get(b'enqueue_time', b'unknown'))
                                        print(f"      Function: {function}")
                                        print(f"      Status: {status}")
                                        print(f"      Enqueued: {enqueue_time}")
                                except Exception as e:
                                    print(f"      ❌ Error reading hash data: {e}")
                            elif key_type == 'string':
                                try:
                                    value = r.get(key)
                                    value_str = safe_decode(value) if value else "None"
                                    if len(value_str) > 100:
                                        print(f"      Value: {value_str[:100]}... (truncated)")
                                    else:
                                        print(f"      Value: {value_str}")
                                except Exception as e:
                                    print(f"      ❌ Error reading string value: {e}")
                            else:
                                print(f"      Type: {key_type} (not showing content)")
                            print()
                        except Exception as e:
                            print(f"   ❌ Error reading key {safe_decode(key)}: {e}")
            except Exception as e:
                print(f"❌ Error looking for ARQ keys: {e}")
            
            # Look for ARQ queue (safely)
            try:
                queue_key = b'arq:queue'
                if r.exists(queue_key):
                    queue_type = safe_decode(r.type(queue_key))
                    if queue_type == 'list':
                        queue_length = r.llen(queue_key)
                        if queue_length > 0:
                            print(f"📦 ARQ Queue: {queue_length} pending jobs")
                    else:
                        print(f"📦 ARQ Queue exists but is type: {queue_type}")
            except Exception as e:
                print(f"❌ Error checking ARQ queue: {e}")
            
            # Look for WebSocket messages
            try:
                ws_keys = r.keys(b'ws:*')
                if ws_keys:
                    print(f"📡 WebSocket channels: {len(ws_keys)}")
            except Exception as e:
                print(f"❌ Error checking WebSocket keys: {e}")
            
            # Show total keys
            try:
                total_keys = len(r.keys(b'*'))
                if total_keys > 0:
                    print(f"📝 Total Redis keys: {total_keys}")
            except Exception as e:
                print(f"❌ Error counting total keys: {e}")
            
            print("-" * 40)
            
            # Wait a bit before checking again
            import time
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")

def show_arq_queues(r):
    """Show ARQ queue information"""
    print("\n📋 ARQ Queue Status:")
    print("=" * 40)
    
    try:
        # Check for ARQ queues
        queue_key = b'arq:queue'
        
        if not r.exists(queue_key):
            print("📦 No ARQ queue found yet")
            print("💡 Queue will appear when tasks are enqueued")
        else:
            queue_type = safe_decode(r.type(queue_key))
            print(f"📦 Queue type: {queue_type}")
            
            if queue_type == 'list':
                queue_length = r.llen(queue_key)
                print(f"📦 Main queue length: {queue_length}")
                
                if queue_length > 0:
                    print("🔧 Pending jobs:")
                    jobs = r.lrange(queue_key, 0, 4)  # Show first 5 jobs
                    for i, job in enumerate(jobs):
                        try:
                            job_str = safe_decode(job)
                            job_data = json.loads(job_str)
                            print(f"   [{i+1}] Function: {job_data.get('function', 'unknown')}")
                            print(f"       Args: {job_data.get('args', [])}")
                            print(f"       Queued: {job_data.get('enqueue_time', 'unknown')}")
                        except json.JSONDecodeError:
                            job_str = safe_decode(job)
                            if len(job_str) > 100:
                                print(f"   [{i+1}] Raw: {job_str[:100]}... (truncated)")
                            else:
                                print(f"   [{i+1}] Raw: {job_str}")
                        except Exception as e:
                            print(f"   [{i+1}] Error: {e}")
                        print()
                else:
                    print("✅ No pending jobs")
            else:
                print(f"❌ Queue exists but is type '{queue_type}', expected 'list'")
        
        # Check for job results/history
        try:
            job_keys = r.keys(b'arq:job:*')
            if job_keys:
                print(f"\n📊 Job history: {len(job_keys)} jobs found")
                
                # Show recent jobs
                recent_jobs = sorted(job_keys)[-3:]  # Last 3 jobs
                for job_key in recent_jobs:
                    try:
                        job_key_str = safe_decode(job_key)
                        key_type = safe_decode(r.type(job_key))
                        
                        if key_type == 'hash':
                            job_info = r.hgetall(job_key)
                            status = safe_decode(job_info.get(b'status', b'unknown'))
                            function = safe_decode(job_info.get(b'function', b'unknown'))
                            print(f"   📄 {job_key_str}: {function} - {status}")
                        else:
                            print(f"   📄 {job_key_str}: type {key_type}")
                    except Exception as e:
                        print(f"   ❌ Error reading {safe_decode(job_key)}: {e}")
            else:
                print("\n📊 No job history found")
        except Exception as e:
            print(f"❌ Error checking job history: {e}")
        
    except Exception as e:
        print(f"❌ Error checking ARQ queues: {e}")
        print("💡 Make sure ARQ worker is configured properly")

def test_redis_pub_sub(r):
    """Test Redis pub/sub (used for WebSocket messages)"""
    print("\n📡 Testing WebSocket Pub/Sub:")
    print("=" * 40)
    
    try:
        # Publish a test message
        test_teacher_id = "test-teacher-123"
        test_message = {
            "status": "test",
            "message": "This is a test WebSocket message",
            "timestamp": datetime.now().isoformat()
        }
        
        channel = f"ws:{test_teacher_id}"
        channel_bytes = channel.encode('utf-8')
        message_bytes = json.dumps(test_message).encode('utf-8')
        
        result = r.publish(channel_bytes, message_bytes)
        print(f"📤 Published test message to: {channel}")
        print(f"📝 Message: {test_message}")
        print(f"👥 Subscribers received message: {result}")
        
        # Check if there are active subscribers
        try:
            channels = r.pubsub_channels(b"ws:*")
            channels_str = [safe_decode(ch) for ch in channels]
            print(f"📻 Active WebSocket channels: {len(channels)} - {channels_str[:5]}")
        except Exception as e:
            print(f"❌ Error checking channels: {e}")
            
    except Exception as e:
        print(f"❌ Error testing pub/sub: {e}")

def main():
    """Main exploration function"""
    print("🔍 REDIS EXPLORER FOR TMDL5")
    print("=" * 50)
    
    # Connect to Redis
    r = connect_redis()
    if not r:
        return
    
    while True:
        print("\n🎛️  Choose what to explore:")
        print("1. 📝 See all Redis keys")
        print("2. 📋 Check ARQ job queues") 
        print("3. 👀 Monitor tasks in real-time")
        print("4. 📡 Test WebSocket pub/sub")
        print("5. 🧹 Clear all Redis data")
        print("6. 🚪 Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            explore_redis_keys(r)
        elif choice == '2':
            show_arq_queues(r)
        elif choice == '3':
            monitor_tasks(r)
        elif choice == '4':
            test_redis_pub_sub(r)
        elif choice == '5':
            # Clear Redis data
            confirm = input("⚠️  Are you sure you want to clear all Redis data? (y/N): ").strip().lower()
            if confirm == 'y':
                try:
                    r.flushall()
                    print("✅ Redis cleared!")
                except Exception as e:
                    print(f"❌ Error clearing Redis: {e}")
            else:
                print("❌ Cancelled")
        elif choice == '6':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main()