# Vertex AI Reauthentication System

## Overview
Implements robust retry logic with exponential backoff for Google Vertex AI authentication across all planning systems (SemPlan, Curriculum, Free Hand).

---

## Problem
Network failures (DNS resolution errors, connection timeouts) to `oauth2.googleapis.com` were causing immediate authentication failures without retry attempts.

**Error Example:**
```
Failed to authenticate with Vertex AI: HTTPSConnectionPool(host='oauth2.googleapis.com', port=443): 
Max retries exceeded with url: /token (Caused by NameResolutionError)
```

---

## Solution

### Retry Configuration
- **Max Retries**: 5 attempts
- **Initial Delay**: 2 seconds
- **Backoff Strategy**: Exponential (2s → 4s → 8s → 16s → 32s)
- **Total Wait Time**: Up to 62 seconds before final failure

---

## Implementation Details

### Authentication Flow

```python
for attempt in range(5):
    try:
        # Try to use cached token first
        if cached_token_is_valid:
            use_cached_token()
            break  # Success!
        
        # Otherwise, fetch new token
        credentials = load_service_account_credentials()
        credentials.refresh(Request())
        cache_new_token()
        break  # Success!
        
    except Exception as e:
        if attempt < 4:  # Not last attempt
            detect_error_type()
            wait_with_exponential_backoff()
        else:  # Last attempt
            raise_detailed_error()
```

---

## Error Detection

The system automatically detects **network-related errors**:

```python
is_network_error = any(keyword in error.lower() for keyword in [
    'nameerror',          # DNS resolution failure
    'getaddrinfo',        # DNS lookup failure
    'dns',                # General DNS issues
    'connection',         # Connection errors
    'timeout',            # Timeout errors
    'oauth2.googleapis.com',  # Specific endpoint
    'max retries'         # Retry exhaustion
])
```

---

## Logging Examples

### Success After Retry
```
⚠️ Network error during authentication (attempt 1/5): Failed to resolve 'oauth2.googleapis.com'
   Retrying in 2 seconds...
🔄 Reauthentication attempt 2/5...
✅ Successfully obtained and cached new access token
```

### Success Using Cache
```
✅ Using cached access token
```

### Final Failure
```
⚠️ Network error during authentication (attempt 5/5): ...
❌ Failed to authenticate after 5 attempts
   Final error: [error details]
   This appears to be a network/DNS issue. Please check your internet connection.
```

---

## Coverage

This reauthentication mechanism is used by **all planning systems**:

| System | File | Function |
|--------|------|----------|
| **Free Plan** | `free_back/free_processor.py` | Uses `send_semester_plan_to_ai()` |
| **Curriculum** | `curri_back/curri_processor.py` | Uses `send_semester_plan_to_ai()` |
| **SemPlan** | `semplan_ground/semplan_back.py` | Uses `send_semester_plan_to_ai()` |
| **Core** | `external_service.py` | Implements authentication |

**All systems now benefit from retry logic automatically!**

---

## Token Caching

Tokens are cached to minimize authentication requests:

```python
_cached_credentials = credentials
_token_expiry = datetime.now() + timedelta(minutes=55)  # Refresh before expiry
```

- **Token Lifespan**: ~60 minutes
- **Refresh Before**: 55 minutes (5 minutes safety margin)
- **Cache Check**: On every AI request

---

## Benefits

1. **Resilience**: Handles temporary network issues gracefully
2. **Performance**: Caches tokens to reduce authentication overhead
3. **User Experience**: Automatic recovery from transient  failures
4. **Visibility**: Clear logging shows retry attempts and final errors
5. **Network-Aware**: Detects and logs network-specific issues

---

## Testing

### Simulate Network Failure
Disconnect network briefly during plan generation:
```
🔄 Fetching new access token...
⚠️ Network error during authentication (attempt 1/5): DNS failure
   Retrying in 2 seconds...
🔄 Reauthentication attempt 2/5...
✅ Successfully obtained and cached new access token  # Network restored
```

### Check Logs
All authentication attempts are logged to:
- `free_back/log.txt` - Free plan logs
- `curri_back/log.txt` - Curriculum logs  
- `semplan_ground/log.txt` - SemPlan logs (if exists)

---

## Configuration

Adjust retry parameters in `external_service.py`:

```python
max_auth_retries = 5      # Number of attempts
auth_retry_delay = 2      # Initial delay (seconds)
# Backoff is exponential: 2s → 4s → 8s → 16s → 32s
```

---

## Status
✅ **IMPLEMENTED AND ACTIVE**

All planning systems now have automatic reauthentication with network error handling!
