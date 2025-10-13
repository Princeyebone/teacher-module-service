# Semester Plan AI JSON Parsing Fix

## Problem
The semester plan AI processing was failing with a JSON parsing error:
```
JSSON parsing error: Expecting ',' delimiter: line 741 column 8 (char 25056)
```

This error occurred because the AI was returning malformed JSON with missing commas between object properties.

## Solution
Enhanced the JSON parsing strategies in the `send_semester_plan_to_ai` function with multiple fallback approaches:

### 1. Direct Parsing (Original Method)
Attempts to parse JSON directly without modifications.

### 2. Common JSON Fixes
- Fix trailing commas before closing braces/brackets
- Fix single quotes to double quotes for keys and string values

### 3. Line-by-Line Cleaning
- Remove comments (text after `//`)
- Remove extra whitespace
- Clean each line individually

### 4. Advanced Comma Fixes
- Add missing commas between object properties: `re.sub(r'(\})\s*"', r'\1,"', fixed_json)`
- Add missing commas between array elements: `re.sub(r'(\])\s*\{', r'\1,\{', fixed_json)`
- Add missing commas between object elements: `re.sub(r'(\})\s*\{', r'\1,\{', fixed_json)`

### 5. Aggressive Cleaning
- Remove non-JSON text before the first `{`
- Remove non-JSON text after the last `}`
- Balance quotes and fix escaping issues

## Testing
Created comprehensive tests to verify the enhanced parsing strategies:
- `test_json_parsing.py` - Tests specific comma error scenarios
- `test_semplan_ai_integration.py` - Tests overall semester plan AI integration

## Results
The enhanced JSON parsing strategies successfully handle the "Expecting ',' delimiter" error and other common JSON formatting issues from AI responses.

## Files Modified
1. `external_service.py` - Enhanced JSON parsing in `send_semester_plan_to_ai` function
2. Created test files to verify the fixes

## Verification
Tests confirm that the enhanced parsing strategies can successfully parse JSON with:
- Missing commas between object properties
- Trailing commas
- Single quotes instead of double quotes
- Comments in JSON
- Other common formatting issues