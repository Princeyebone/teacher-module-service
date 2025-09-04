#!/usr/bin/env python3
"""
Production Worker Setup Script for TMDL5

This script helps you set up multiple ARQ workers for production use.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

class WorkerManager:
    def __init__(self, num_workers=3):
        self.num_workers = num_workers
        self.workers = []
        self.running = False
    
    def start_workers(self):
        """Start multiple ARQ worker processes"""
        print(f"🚀 Starting {self.num_workers} ARQ workers...")
        
        for i in range(self.num_workers):
            try:
                # Start worker process
                process = subprocess.Popen([
                    sys.executable, "-m", "arq", "background.worker_config"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                self.workers.append({
                    'id': i + 1,
                    'process': process,
                    'pid': process.pid
                })
                
                print(f"✅ Worker {i + 1} started (PID: {process.pid})")
                time.sleep(1)  # Small delay between starts
                
            except Exception as e:
                print(f"❌ Failed to start worker {i + 1}: {e}")
        
        self.running = True
        print(f"🎯 {len(self.workers)} workers are now running")
    
    def stop_workers(self):
        """Stop all worker processes"""
        print("🛑 Stopping all workers...")
        
        for worker in self.workers:
            try:
                process = worker['process']
                process.terminate()
                process.wait(timeout=10)
                print(f"✅ Worker {worker['id']} stopped")
            except subprocess.TimeoutExpired:
                print(f"⚡ Force killing worker {worker['id']}")
                process.kill()
            except Exception as e:
                print(f"❌ Error stopping worker {worker['id']}: {e}")
        
        self.workers = []
        self.running = False
        print("🏁 All workers stopped")
    
    def monitor_workers(self):
        """Monitor worker health and restart if needed"""
        print("👀 Monitoring workers... (Press Ctrl+C to stop)")
        
        try:
            while self.running:
                # Check each worker
                for worker in self.workers[:]:  # Copy list to avoid modification during iteration
                    process = worker['process']
                    
                    if process.poll() is not None:  # Process has died
                        print(f"💀 Worker {worker['id']} died (exit code: {process.returncode})")
                        self.workers.remove(worker)
                        
                        # Restart the worker
                        print(f"🔄 Restarting worker {worker['id']}...")
                        try:
                            new_process = subprocess.Popen([
                                sys.executable, "-m", "arq", "background.worker_config"
                            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            
                            self.workers.append({
                                'id': worker['id'],
                                'process': new_process,
                                'pid': new_process.pid
                            })
                            print(f"✅ Worker {worker['id']} restarted (PID: {new_process.pid})")
                        except Exception as e:
                            print(f"❌ Failed to restart worker {worker['id']}: {e}")
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            print("\\n⛔ Monitoring stopped by user")
    
    def status(self):
        """Show worker status"""
        print(f"📊 Worker Status ({len(self.workers)} workers)")
        print("-" * 40)
        
        for worker in self.workers:
            process = worker['process']
            status = "Running" if process.poll() is None else "Dead"
            print(f"Worker {worker['id']:2d}: PID {worker['pid']:6d} - {status}")
    
    def handle_signals(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\\n📡 Received signal {signum}")
            self.stop_workers()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TMDL5 ARQ Worker Manager')
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'status', 'monitor'],
                       help='Command to execute')
    parser.add_argument('-n', '--workers', type=int, default=3,
                       help='Number of workers to start (default: 3)')
    
    args = parser.parse_args()
    
    manager = WorkerManager(args.workers)
    manager.handle_signals()
    
    if args.command == 'start':
        manager.start_workers()
        manager.monitor_workers()
    
    elif args.command == 'stop':
        print("🔍 Finding running workers...")
        # This would need process management to find existing workers
        print("💡 Use Ctrl+C to stop workers started with 'start' command")
    
    elif args.command == 'restart':
        manager.stop_workers()
        time.sleep(2)
        manager.start_workers()
        manager.monitor_workers()
    
    elif args.command == 'status':
        manager.status()
    
    elif args.command == 'monitor':
        manager.start_workers()
        manager.monitor_workers()


if __name__ == "__main__":
    # Check if Redis is running
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("💡 Make sure Redis server is running: redis-server")
        sys.exit(1)
    
    main()