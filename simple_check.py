import asyncio
from datetime import datetime, timedelta

# Print current time
now = datetime.utcnow()
five_minutes_ago = now - timedelta(minutes=5)
print(f"Current time: {now}")
print(f"Five minutes ago: {five_minutes_ago}")

# Check the timestamps from our previous output:
# Record ID: 564 - Created at: 2025-12-06 10:32:23.681114
# Record ID: 565 - Created at: 2025-12-06 11:09:33.020085

record_564_time = datetime(2025, 12, 6, 10, 32, 23, 681114)
record_565_time = datetime(2025, 12, 6, 11, 9, 33, 20085)

print(f"\nRecord 564 created at: {record_564_time}")
print(f"Record 565 created at: {record_565_time}")

print(f"\nRecord 564 is older than 5 minutes: {record_564_time < five_minutes_ago}")
print(f"Record 565 is older than 5 minutes: {record_565_time < five_minutes_ago}")

# Calculate time differences
diff_564 = now - record_564_time
diff_565 = now - record_565_time

print(f"\nTime since Record 564 was created: {diff_564}")
print(f"Time since Record 565 was created: {diff_565}")

print(f"\nRecord 564 is older than 2 minutes: {diff_564.total_seconds() >= 120}")
print(f"Record 565 is older than 2 minutes: {diff_565.total_seconds() >= 120}")