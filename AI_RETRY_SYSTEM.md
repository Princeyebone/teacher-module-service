# AI Request Retry System with Exponential Backoff

## Overview
All planning implementations (Free Plan, Curriculum, SemPlan) now have comprehensive retry logic with exponential backoff to handle timeouts and network failures gracefully.

---

## Configuration

### Retry Parameters
```python
max_retries = 5           # Maximum number of attempts
retry_delay = 20          # Initial delay in seconds
timeout_seconds = 300     # 5 minutes per attempt
```

### Exponential Backoff Schedule
| Attempt | Delay Before Retry | Total Wait Time |
|---------|-------------------|-----------------|
| 1       | 0s (immediate)    | 0s              |
| 2       | 20s               | 20s             |
| 3       | 40s               | 60s             |
| 4       | 80s               | 140s            |
| 5       | 160s              | 300s            |

**Maximum Total Time**: 5 attempts × 300s + 300s delays = **~30 minutes**

---

## How It Works

### Success Case
```
Attempt 1
  ↓
Send AI Request (5min timeout)
  ↓
✅ Response received < 5min
  ↓
Parse JSON
  ↓
Return success
```

### Retry Case (Timeout/Network Error)
```
Attempt 1
  ↓
Send AI Request (5min timeout)
  ↓
⏱️ Timeout or 🌐 Network Error
  ↓
⏳ Wait 20 seconds
  ↓
Attempt 2
  ↓
Send AI Request (5min timeout)
  ↓
⏱️ Timeout or 🌐 Network Error
  ↓
⏳ Wait 40 seconds (2× previous)
  ↓
Attempt 3
  ↓
... continues until success or 5 attempts exhausted
```

---

## Error Handling Strategy

### **Retryable Errors** (trigger exponential backoff):
1. ⏱️ **`asyncio.TimeoutError`** - Request timed out after 5 minutes
2. 🌐 **`aiohttp.ClientError`** - Network connectivity issues
3. 💥 **Unexpected exceptions** during HTTP request

### **Non-Retryable Errors** (return immediately):
1. **HTTP 400-499** - Client errors (bad request, permissions, etc.)
2. **HTTP 500-599** - Server errors (indicates AI service issue, not transient)
3. **JSON parsing errors** - Response was received but malformed
4. **Missing response** data - Response structure invalid

---

## Logging Examples

### Successful First Attempt
```
📤 Sending AI request (attempt 1/5)...
⏱️ Request timeout set to 300 seconds (5 minutes)
📡 AI API Response Status: 200
✅ AI API Response Received Successfully
```

### Timeout with Retry
```
📤 Sending AI request (attempt 1/5)...
⏱️ Request timeout set to 300 seconds (5 minutes)
⏱️ AI API request timed out (attempt 1/5)
   Retrying in 20 seconds...
🔄 Retry attempt 2/5 after 20s delay...
⏱️ Request timeout set to 300 seconds (5 minutes)
📡 AI API Response Status: 200
✅ AI API Response Received Successfully
```

### Network Error with Retry
```
📤 Sending AI request (attempt 1/5)...
⏱️ Request timeout set to 300 seconds (5 minutes)
🌐 Network error (attempt 1/5): Connection refused
   Retrying in 20 seconds...
🔄 Retry attempt 2/5 after 20s delay...
⏱️ Request timeout set to 300 seconds (5 minutes)
✅ Response received
```

### All Retries Exhausted
```
📤 Sending AI request (attempt 1/5)...
⏱️ AI API request timed out (attempt 1/5)
   Retrying in 20 seconds...
🔄 Retry attempt 2/5 after 20s delay...
⏱️ AI API request timed out (attempt 2/5)
   Retrying in 40 seconds...
🔄 Retry attempt 3/5 after 40s delay...
⏱️ AI API request timed out (attempt 3/5)
   Retrying in 80 seconds...
🔄 Retry attempt 4/5 after 80s delay...
⏱️ AI API request timed out (attempt 4/5)
   Retrying in 160 seconds...
🔄 Retry attempt 5/5 after 160s delay...
⏱️ AI API request timed out (attempt 5/5)
❌ Failed after 5 attempts - all timed out
   This indicates persistent network or service issues
```

---

## Coverage

This retry system is implemented in **ONE CENTRAL LOCATION** and benefits **ALL** planning systems:

| Planning System | Uses Retry Logic | File |
|----------------|------------------|------|
| **Free Plan** | ✅ Yes | Uses `send_semester_plan_to_ai()` |
| **Curriculum** | ✅ Yes | Uses `send_semester_plan_to_ai()` |
| **SemPlan** | ✅ Yes | Uses `send_semester_plan_to_ai()` |
| **Outline Generation** | ✅ Yes | Uses similar AI call pattern |

**All systems automatically benefit from retry logic!**

---

## Key Features

### 1. **Intelligent Retry Decision**
- Only retries on transient errors (timeout, network)
- Doesn't retry on permanent errors (bad request, malformed data)
- Prevents wasting time on unrecoverable errors

### 2. **Exponential Backoff**
- Starts with 20-second delay
- Doubles each time: 20s → 40s → 80s → 160s → 320s
- Gives system time to recover from transient issues
- Prevents overwhelming failing services

### 3. **Comprehensive Logging**
- Every attempt is logged with attempt number
- Success/failure clearly indicated
- Retry delays shown
- Final status after all attempts

### 4. **Graceful Degradation**
- If all retries fail, clear error message returned
- Worker continues to next job (not stuck)
- Failed job properly marked as failed

---

## Configuration Options

### Adjust Retry Parameters
Edit `external_service.py` around line 902:

```python
max_retries = 5           # Change to 3 for faster failure
retry_delay = 20          # Change to 10 for faster retries
timeout_seconds = 300     # Change to 180 for 3-minute timeout
```

### Adjust Backoff Strategy
Current: **Exponential** (doubles each time)
```python
retry_delay *= 2  # Exponential: 20, 40, 80, 160, 320
```

Alternative: **Linear** (fixed increment)
```python
retry_delay += 20  # Linear: 20, 40, 60, 80, 100
```

Alternative: **Fixed** (constant delay)
```python
retry_delay = 20  # Fixed: 20, 20, 20, 20, 20
```

---

## Testing

### Test Successful Request
Generate any plan - should succeed on first attempt:
```
📤 Sending AI request (attempt 1/5)...
✅ AI API Response Received Successfully
```

### Test Retry on Network Failure
Temporarily disconnect network during plan generation:
```
📤 Sending AI request (attempt 1/5)...
🌐 Network error (attempt 1/5): ...
   Retrying in 20 seconds...
🔄 Retry attempt 2/5 after 20s delay...
✅ Response received  ← Network restored
```

### Test Timeout Handling
Use a very large prompt or slow network:
```
📤 Sending AI request (attempt 1/5)...
⏱️ AI API request timed out (attempt 1/5)
   Retrying in 20 seconds...
```

---

## Benefits

1. **Resilience**: Handles temporary network/service issues
2. **User Experience**: Automatic recovery without manual intervention
3. **Visibility**: Clear logging shows what's happening
4. **Efficiency**: Exponential backoff prevents resource waste
5. **Reliability**: All planning systems protected

---

## Monitoring

### Check Retry Activity
Look for these patterns in logs:

**Good** (occasional retries):
```
🔄 Retry attempt 2/5
✅ Response received
```

**Concerning** (frequent retries reaching max):
```
❌ Failed after 5 attempts
```
→ Investigate network/service issues

**Critical** (all jobs failing):
```
Multiple jobs: ❌ Failed after 5 attempts
```
→ Check AI service status, network connectivity, credentials

---

## Status
✅ **IMPLEMENTED AND ACTIVE**

All planning systems now have automatic retry with exponential backoff!

**Restart workers to activate:**
```bash
python free_back/run_free_workers.py
```
