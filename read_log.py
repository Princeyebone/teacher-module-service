import os

log_file = r"c:\Users\HP\tmdl5\slide_builder\slide_log.txt"
if os.path.exists(log_file):
    with open(log_file, 'rb') as f:
        # seek to end - 10000 bytes
        try:
            f.seek(-20000, 2)
        except OSError:
            f.seek(0)
        
        content = f.read().decode('utf-8', errors='ignore')
        print(content)
else:
    print("No log file found")
