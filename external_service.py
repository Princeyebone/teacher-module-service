import json
from datetime import datetime, timedelta
import re
import logging
import aiohttp
from config import settings

# Initialize logger
logger = logging.getLogger(__name__)

# Global credential cache to avoid getting new tokens on every request
_cached_credentials = None
_token_expiry = None


async def get_holidays_from_ai(country: str, year: int):
    """
    Fetch up-to-date national/public holidays using Vertex AI with Google Search grounding.
    Returns a list of holiday dicts in the format:
    [
        {
            "date": "YYYY-MM-DD",
            "name": "Holiday Name",
            "type": "Public Holiday",
            "requires_no_classes": True,
            "description": "Optional details about the holiday"
        }
    ]
    """
    import time
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import json as json_lib
    
    logger.info(f"🔍 Fetching holidays for {country} in {year} using Vertex AI with web search...")
    
    # Authentication with retry
    max_auth_retries = 5
    auth_retry_delay = 2
    access_token = None
    
    for auth_attempt in range(max_auth_retries):
        try:
            logger.info(f"🔐 Authenticating with Vertex AI (attempt {auth_attempt + 1}/{max_auth_retries})...")
            
            # Load service account credentials
            if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
                service_account_info = json_lib.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
            else:
                with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                    service_account_info = json_lib.load(f)
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Get access token
            credentials.refresh(Request())
            access_token = credentials.token
            
            logger.info("✅ Authentication successful")
            break
            
        except Exception as e:
            if auth_attempt < max_auth_retries - 1:
                logger.warning(f"⚠️ Authentication error: {str(e)[:100]}. Retrying in {auth_retry_delay}s...")
                time.sleep(auth_retry_delay)
                auth_retry_delay *= 2
            else:
                logger.error(f"❌ Failed to authenticate after {max_auth_retries} attempts")
                return []
    
    if not access_token:
        logger.error("❌ Failed to obtain access token")
        return []
    
    # Vertex AI configuration
    project_id = settings.GCS_PROJECT_ID
    model_id = "gemini-2.5-flash"
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    logger.info(f"🔗 Using Vertex AI endpoint: {model_id}")
    
    # Build prompt
    prompt_json = {
        "task": "Fetch national holidays",
        "country": country,
        "year": year,
        "output_format": {
            "holidays": [
                {
                    "date": "YYYY-MM-DD",
                    "name": "Holiday Name",
                    "type": "Public Holiday",
                    "requires_no_classes": True,
                    "description": "Optional details about the holiday"
                }
            ]
        },
        "instruction": "Use web search to find the most accurate and up-to-date list of national holidays. Return ONLY a valid JSON object."
    }
    
    # Create payload with Google Search grounding
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json_lib.dumps(prompt_json, indent=2)
                    }
                ]
            }
        ],
        "generation_config": {
            "temperature": 0,
            "maxOutputTokens": 8192,
        },
        "tools": [
            {
                "google_search": {}
            }
        ]
    }
    
    # Set headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Retry configuration
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for holiday fetch...")
                time.sleep(retry_delay)
                retry_delay *= 2
            
            # Send request with timeout
            timeout = aiohttp.ClientTimeout(total=60)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    
                    logger.info(f"📡 Response Status: {response.status}")
                    
                    # Handle 429 rate limit
                    if response.status == 429:
                        if attempt < max_retries - 1:
                            quota_wait = 10 * (attempt + 1)
                            logger.warning(f"⚠️ Rate limit hit (429). Retrying in {quota_wait}s...")
                            time.sleep(quota_wait)
                            continue
                        else:
                            logger.error(f"❌ Max retry attempts reached (429)")
                            return []
                    
                    # Success
                    if response.status == 200:
                        response_data = json_lib.loads(response_text)
                        
                        # Extract content
                        if "candidates" in response_data and len(response_data["candidates"]) > 0:
                            content = response_data["candidates"][0].get("content", {})
                            if "parts" in content and len(content["parts"]) > 0:
                                response_text = content["parts"][0].get("text", "")
                                
                                # Parse JSON response
                                try:
                                    # Try direct JSON parse first
                                    parsed_response = json_lib.loads(response_text)
                                    holidays = parsed_response.get("holidays", [])
                                    
                                    logger.info(f"🎉 Successfully fetched {len(holidays)} holidays for {country} in {year}")
                                    return holidays
                                    
                                except json_lib.JSONDecodeError:
                                    # Try regex extraction as fallback
                                    match = re.search(r"\{[\s\S]*\}", response_text)
                                    if match:
                                        json_str = match.group(0)
                                        try:
                                            parsed_response = json_lib.loads(json_str)
                                            holidays = parsed_response.get("holidays", [])
                                            
                                            logger.info(f"🎉 Successfully fetched {len(holidays)} holidays for {country} in {year}")
                                            return holidays
                                            
                                        except json_lib.JSONDecodeError as e:
                                            logger.warning(f"⚠️ JSON parsing error: {e}")
                                            logger.warning(f"📄 Raw response: {response_text[:200]}")
                                            return []
                                    else:
                                        logger.warning("⚠️ No JSON found in AI response")
                                        logger.warning(f"📄 Response: {response_text[:200]}")
                                        return []
                            else:
                                logger.warning("⚠️ No content parts found")
                                return []
                        else:
                            logger.warning("⚠️ No candidates found")
                            return []
                    else:
                        logger.error(f"❌ API request failed with status {response.status}: {response_text[:200]}")
                        if attempt < max_retries - 1:
                            logger.info(f"   Retrying in {retry_delay}s...")
                            continue
                        else:
                            return []
        
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                logger.warning(f"⏱️ Request timed out (attempt {attempt + 1}/{max_retries}). Retrying...")
                continue
            else:
                logger.error(f"❌ Failed after {max_retries} timeout attempts")
                return []
        
        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                logger.warning(f"🌐 Network error: {str(e)[:100]}. Retrying...")
                continue
            else:
                logger.error(f"❌ Failed after {max_retries} network error attempts")
                return []
            
        except Exception as e:
            logger.error(f"💥 Holiday fetch error: {e}")
            if attempt < max_retries - 1:
                logger.info(f"   Retrying in {retry_delay}s...")
                continue
            else:
                return []
    
    # All retries exhausted
    logger.error(f"❌ Holiday fetch failed after {max_retries} attempts")
    return []



def build_academic_calendar_prompt(extracted_text: str, gcs_source_path: str, additional_data: str = "") -> str:
    """
    Build a structured prompt for processing academic calendar data using AI.
    
    Args:
        extracted_text: The raw text extracted from the academic calendar document
        gcs_source_path: The Google Cloud Storage path to the original calendar file
        additional_data: Additional context or data that may contain multiple calendar info
        
    Returns:
        A structured prompt for the AI model
    """
    prompt = f"""🎯 You are an advanced AI specializing in academic planning and data generation. Your primary goal is to synthesize the provided academic parameters and generate a complete, structured academic calendar in JSON format, strictly adhering to the specified schema.

📂 **Input Data (Parameters for Generation):**
1.  **GENERATION_PARAMETERS (EXTRACTED_TEXT):** The core request details provided by the user (e.g., "Fall 2023 semester for Grade 10 students"). Treat this as the primary instruction source for defining the semester scope.
2.  **CONTEXT_SOURCE_PATH (GCS_SOURCE_PATH):** The Google Cloud Storage path (e.g., gs://config-files/calendar_template.json). This placeholder is reserved for providing optional context, like a policy document or a base template file, but the generation should primarily rely on the explicit requirements below.
3.  **ADDITIONAL_INFO_IN_THE_EVENT_USER_PROVIDES_ADDITIONAL_DATA (ADDITIONAL_DATA):** The document may contain multiple calendar info for different semesters or classes or even cohorts.

📋 **Task:**
Generate academic calendar data for a full semester (approximately 3-4 months) based on the "GENERATION_PARAMETERS" and the specific requirements listed below. Ensure the generated data is realistic and logically consistent.

⚙️ **Required JSON Output Structure:**
Return **only the final JSON object**, with no surrounding prose, explanations, or code fencing.

1. Academic Calendar Information:
- semester_name (string): Name of the semester (e.g., "Fall 2023", "Spring 2024")
- semester_start_date (YYYY-MM-DD): Start date of the semester
- semester_end_date (YYYY-MM-DD): End date of the semester
- mid_semester_break_start_date (YYYY-MM-DD, optional): Start date of mid-semester break
- mid_semester_break_end_date (YYYY-MM-DD, optional): End date of mid-semester break
- midsem_exams_date (YYYY-MM-DD, optional): Date of mid-semester exams
- revision_start_date (YYYY-MM-DD, optional): Start date of revision period

2. Calendar Events (array of events):
- event_name (string): Name of the event (e.g., "Parent-Teacher Conference", "School Holiday")
- event_start_date (YYYY-MM-DD): Start date of the event
- event_end_date (YYYY-MM-DD): End date of the event
- event_start_time (HH:MM, optional): Start time of the event
- event_end_time (HH:MM, optional): End time of the event
- is_holiday (boolean): Whether the event is a holiday
- requires_no_classes (boolean): Whether classes are suspended during this event

📄 **GENERATION_PARAMETERS (EXTRACTED_TEXT):**
{extracted_text}

🔗 **CONTEXT_SOURCE_PATH (GCS_SOURCE_PATH):**
{gcs_source_path}

📎 **ADDITIONAL_INFO_IN_THE_EVENT_USER_PROVIDES_ADDITIONAL_DATA (ADDITIONAL_DATA):**
{additional_data if additional_data else "No additional data provided"}

⚠️ **Requirements:**
- Generate data for a full semester (approximately 3-4 months)
- Include realistic academic events like exams, holidays, breaks, conferences
- Ensure all dates are logically consistent (events fall within semester dates)
- Include calendar events
- Make sure date ranges are valid (start dates before end dates)
- Use proper date formatting (YYYY-MM-DD) and time formatting (HH:MM)
- Return the data in JSON format with the structure specified above
- Return ONLY the final JSON object, with no surrounding prose, explanations, or code fencing

⚠️ Please return ONLY the valid JSON object that matches the specified schema. Do not include any additional text, code, or explanations.
"""
    
    return prompt


def build_timetable_prompt(extracted_text: str, gcs_source_path: str) -> str:
    """
    Build a structured prompt for processing timetable data using AI.
    
    Args:
        extracted_text: The raw text extracted from the timetable document
        gcs_source_path: The Google Cloud Storage path to the original timetable file
        
    Returns:
        A structured prompt for the AI model
    """
    prompt = f"""🎯 You are an advanced AI assistant specializing in processing complex timetable data. Your primary goal is to analyze the provided information and return a structured JSON object that exactly matches the specified frontend schema.

📂 **Input Data:**
1.  **EXTRACTED_TEXT:** The raw, copied text content from the timetable document. This is the primary data source for rapid extraction.
2.  **GCS_SOURCE_PATH:** The Google Cloud Storage path (e.g., gs://your-bucket/document.pdf) to the original timetable file. This serves as a definitive source of truth for verification against any ambiguities in the EXTRACTED_TEXT.

📋 **Task:**
Analyze the **EXTRACTED_TEXT** and structure all valid timetable entries into the required JSON format. Use the **GCS_SOURCE_PATH** reference to get insight into the original file not only when the extracted text is unclear, truncated, or contains formatting ambiguities that require context from the original document but always even if the text is clear.

⚙️ **Required JSON Output Structure:**
```
{{
  "extracted_data": {{
    "timetables": [
      {{
        "weekday": "monday",  // lowercase full day name (e.g., monday, tuesday)
        "subject": "Mathematics",  // full subject name
        "start_time": "09:00",  // 24-hour format HH:MM
        "end_time": "10:00",  // 24-hour format HH:MM
        "location": "Class 1",  // classroom or location (Optional)
        "pupils": "Class 10A"  // class, grade, or group information (Required)
      }}
      # ... include all timetable entries found
    ]
  }}
}}

📄 **EXTRACTED_TEXT:**
{extracted_text}

🔗 **GCS_SOURCE_PATH:**
{gcs_source_path}

⚠️ Please return ONLY the valid JSON object that matches the specified schema. Do not include any additional text, code, or explanations.
"""
    
    return prompt


async def send_academic_calendar_to_ai(extracted_text: str, gcs_source_path: str, api_key: str, additional_data: str = "") -> dict:
    """
    Send academic calendar data to AI for processing and return structured results.
    
    Args:
        extracted_text: The raw text extracted from the academic calendar document
        gcs_source_path: The Google Cloud Storage path to the original calendar file
        api_key: The API key for the AI service (Google Gemini)
        additional_data: Additional context or data that may contain multiple calendar info
        
    Returns:
        A dictionary with the AI-processed academic calendar data
    """
    try:
        logger.info(f"🚀 Sending academic calendar data to AI for processing")
        logger.info(f"📂 GCS Source Path: {gcs_source_path}")
        logger.info(f"📊 Extracted Text Length: {len(extracted_text)} characters")
        if additional_data:
            logger.info(f"📎 Additional Data Length: {len(additional_data)} characters")
        
        # Build the prompt
        prompt = build_academic_calendar_prompt(extracted_text, gcs_source_path, additional_data)
        logger.info(f"📝 Prompt Length: {len(prompt)} characters")
        
        # Add detailed logging of what is sent to AI
        logger.info("=====START OF WHAT IS SENT TO AI=====")
        logger.info(f"URL: https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY[:8]}...{settings.API_KEY[-4:]}")
        logger.info("HEADERS: {'Content-Type': 'application/json'}")
        logger.info("PAYLOAD:")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        logger.info(json.dumps(payload, indent=2))
        logger.info("=====END OF WHAT IS SENT TO AI=====")
        
        # Prepare the request for Google Vertex AI API (Gemini) - Use generateContent instead of streamGenerateContent
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY}"
        logger.info(f"🔗 Sending request to AI API")
        
        # Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Send request to AI service
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.info(f"📡 AI API Response Status: {response.status}")
                
                # Check if request was successful
                if response.status == 200:
                    response_data = json.loads(response_text)
                    logger.info(f"✅ AI API Response Received Successfully")
                    
                    # Log the full response for debugging
                    logger.info(f"📋 AI Response: {str(response_data)}")
                    
                    # Extract the generated content
                    if "candidates" in response_data and len(response_data["candidates"]) > 0:
                        content = response_data["candidates"][0].get("content", {})
                        if "parts" in content and len(content["parts"]) > 0:
                            result_text = content["parts"][0].get("text", "")
                            logger.info(f"🔍 AI Generated Content Length: {len(result_text)} characters")
                            
                            # Try to parse as JSON
                            try:
                                # Clean up the response text to extract JSON
                                json_match = re.search(r"\{[\s\S]*\}", result_text)
                                if json_match:
                                    json_str = json_match.group(0)
                                    logger.info(f"📦 JSON Extracted from AI Response, Length: {len(json_str)} characters")
                                    parsed_result = json.loads(json_str)
                                    logger.info("AI Response Parsed Successfully")
                                    
                                    # Clean up empty string values for optional date fields
                                    # Convert empty strings to None for optional date fields
                                    date_fields = [
                                        "mid_semester_break_start_date",
                                        "mid_semester_break_end_date",
                                        "midsem_exams_date",
                                        "revision_start_date"
                                    ]
                                    
                                    for field in date_fields:
                                        if field in parsed_result and parsed_result[field] == "":
                                            parsed_result[field] = None
                                            logger.info(f"🧹 Cleaned empty string for field '{field}' -> None")
                                    
                                    # The AI response has the academic calendar data at the root level, not wrapped in academic_calendar
                                    semester_name = parsed_result.get('semester_name', 'Unknown')
                                    logger.info(f"Academic calendar generated with semester: {semester_name}")
                                    return parsed_result
                                else:
                                    logger.warning(f"⚠️ No JSON found in AI response: {result_text[:200]}...")
                                    return {"error": "No JSON found in AI response", "raw_response": result_text}
                            except json.JSONDecodeError as e:
                                logger.error(f"💥 JSON parsing error: {e}")
                                logger.error(f"📄 Raw response: {result_text[:500]}...")
                                return {"error": f"JSON parsing error: {str(e)}", "raw_response": result_text}
                        else:
                            logger.warning("No content parts found in AI response")
                            return {"error": "No content parts found in AI response"}
                    else:
                        logger.warning("No candidates found in AI response")
                        return {"error": "No candidates found in AI response"}
                else:
                    logger.error(f"AI API request failed with status {response.status}: {response_text}")
                    return {"error": f"AI API request failed with status {response.status}", "details": response_text}
        
    except Exception as e:
        logger.error(f"AI Academic Calendar Processing Error: {e}", exc_info=True)
        return {"error": str(e)}


async def send_timetable_to_ai(extracted_text: str, gcs_source_path: str, api_key: str) -> dict:
    """
    Send timetable data to AI for processing and return structured results.
    
    Args:
        extracted_text: The raw text extracted from the timetable document
        gcs_source_path: The Google Cloud Storage path to the original timetable file
        api_key: The API key for the AI service (Google Gemini)
        
    Returns:
        A dictionary with the AI-processed timetable data
    """
    try:
        logger.info(f"🚀 Sending timetable data to AI for processing")
        logger.info(f"📂 GCS Source Path: {gcs_source_path}")
        logger.info(f"📊 Extracted Text Length: {len(extracted_text)} characters")
        
        # Build the prompt
        prompt = build_timetable_prompt(extracted_text, gcs_source_path)
        logger.info(f"📝 Prompt Length: {len(prompt)} characters")
        
        # Add detailed logging of what is sent to AI
        logger.info("=====START OF WHAT IS SENT TO AI=====")
        logger.info(f"URL: https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY[:8]}...{settings.API_KEY[-4:]}")
        logger.info("HEADERS: {'Content-Type': 'application/json'}")
        logger.info("PAYLOAD:")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        logger.info(json.dumps(payload, indent=2))
        logger.info("=====END OF WHAT IS SENT TO AI=====")
        
        # Prepare the request for Google Vertex AI API (Gemini) - Use generateContent instead of streamGenerateContent
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY}"
        logger.info(f"🔗 Sending request to AI API")
        
        # Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Send request to AI service
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_text = await response.text()
                logger.info(f"📡 AI API Response Status: {response.status}")
                
                # Check if request was successful
                if response.status == 200:
                    response_data = json.loads(response_text)
                    logger.info(f"✅ AI API Response Received Successfully")
                    
                    # Log the full response for debugging
                    logger.info(f"📋 AI Response: {str(response_data)}")
                    
                    # Extract the generated content
                    if "candidates" in response_data and len(response_data["candidates"]) > 0:
                        content = response_data["candidates"][0].get("content", {})
                        if "parts" in content and len(content["parts"]) > 0:
                            result_text = content["parts"][0].get("text", "")
                            logger.info(f"🔍 AI Generated Content Length: {len(result_text)} characters")
                            
                            # Try to parse as JSON
                            try:
                                # Clean up the response text to extract JSON
                                
                                # Strategy 0: Check for markdown code blocks first (most reliable)
                                markdown_match = re.search(r"```(?:json)?\s*([\[\{][\s\S]*?[\]\}])\s*```", result_text)
                                
                                json_str = None
                                if markdown_match:
                                    json_str = markdown_match.group(1)
                                    logger.info(f"📦 JSON Extracted from Markdown Code Block, Length: {len(json_str)} characters")
                                else:
                                    # Fallback 1: Check if the text itself looks like JSON (starts with { or [)
                                    stripped_text = result_text.strip()
                                    if stripped_text.startswith('{') or stripped_text.startswith('['):
                                        json_str = stripped_text
                                        logger.info(f"📦 JSON Extracted from Raw Text (Direct Match), Length: {len(json_str)} characters")
                                    else:
                                        # Fallback 2: regex search for outer-most Object or Array
                                        # We look for both and take the longest valid-looking one to avoid partial matches
                                        list_match = re.search(r"\[[\s\S]*\]", result_text)
                                        obj_match = re.search(r"\{[\s\S]*\}", result_text)
                                        
                                        candidates = []
                                        if list_match: candidates.append(list_match.group(0))
                                        if obj_match: candidates.append(obj_match.group(0))
                                        
                                        if candidates:
                                            # Pick the longest match (e.g. if we have [ { } ], list is longer than obj)
                                            json_str = max(candidates, key=len)
                                            logger.info(f"📦 JSON Extracted from Regex Search, Length: {len(json_str)} characters")
                                
                                if json_str:
                                    parsed_result = json.loads(json_str)
                                    logger.info(f"🎉 AI Response Parsed Successfully")
                                    logger.info(f"📈 Number of timetable entries found: {len(parsed_result.get('extracted_data', {}).get('timetables', []))}")
                                    return parsed_result
                                else:
                                    logger.warning(f"⚠️ No JSON found in AI response: {result_text[:200]}...")
                                    return {"error": "No JSON found in AI response", "raw_response": result_text}
                            except json.JSONDecodeError as e:
                                logger.error(f"💥 JSON parsing error: {e}")
                                logger.error(f"📄 Raw response: {result_text[:500]}...")
                                return {"error": f"JSON parsing error: {str(e)}", "raw_response": result_text}
                        else:
                            logger.warning("No content parts found in AI response")
                            return {"error": "No content parts found in AI response"}
                    else:
                        logger.warning("No candidates found in AI response")
                        return {"error": "No candidates found in AI response"}
                else:
                    logger.error(f"AI API request failed with status {response.status}: {response_text}")
                    return {"error": f"AI API request failed with status {response.status}", "details": response_text}
        
    except Exception as e:
        logger.error(f"💥 AI Timetable Processing Error: {e}", exc_info=True)
        return {"error": str(e)}


def build_semester_plan_prompt(extracted_text: str, gcs_source_path: str, session_data: dict = None, class_name: str = None, subject: str = None) -> str:
    """
    Build a structured prompt for processing semester plan data using AI.
    
    Args:
        extracted_text: The raw text extracted from the semester plan document
        gcs_source_path: The Google Cloud Storage path to the original semester plan file
        session_data: Session data including academic calendar and class sessions
        class_name: The specific class name to focus on (optional)
        subject: The specific subject to focus on (optional)
        
    Returns:
        A structured prompt for the AI model
    """
    # Create the example JSON structure as a string to avoid nested f-string issues
    # IMPORTANT: This example should ONLY show the structure without real values to avoid confusing the AI
    example_json = '''{
  "strand_data": [
    {
      "strand_name": "Example Strand Name",
      "weeks": []
    }
  ],
  "substrand_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "weeks": []
    }
  ],
  "content_standard_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "content_standard_code": "EXAMPLE.CODE.1",
      "content_standard_text": "Example content standard description"
    }
  ],
  "indicator_data": [
    {
      "strand_name": "Example Strand Name",
      "substrand_name": "Example Substrand Name",
      "content_standard_code": "EXAMPLE.CODE.1",
      "indicator_code": "EXAMPLE.CODE.1.1",
      "indicator_text": "Example indicator description"
    }
  ]
}'''
    
    # Validate session_data structure
    available_weeks = []
    week_details = []
    strand_boundaries = {}
    
    if session_data and 'weekly_sessions' in session_data:
        available_weeks = list(session_data['weekly_sessions'].keys())
        for week_key, week_data in session_data['weekly_sessions'].items():
            session_count = len(week_data.get('sessions', []))
            week_details.append(f"{week_key}: {session_count} sessions")
    
    # Create strand boundary information for clearer instructions
    if available_weeks:
        strand_boundaries["Example Strand A"] = f"Weeks {available_weeks[0][:min(3, len(available_weeks))]} (example)".replace("Week ", "") if available_weeks else "No weeks"
        if len(available_weeks) > 3:
            strand_boundaries["Example Strand B"] = f"Weeks {available_weeks[3:min(6, len(available_weeks))]} (example)".replace("Week ", "") if len(available_weeks) > 3 else "No weeks"
    
    prompt = f"""You are an Educational Curriculum Mapping AI. Analyze academic content and map it to actual teaching sessions.

IMPORTANT: You MUST use BOTH the ExtractedText AND the original file at GCSFileLocation for comprehensive analysis. The ExtractedText may be incomplete or unclear, but the original file contains the complete information.

TARGET CLASS AND SUBJECT:
- Class Name: {class_name if class_name else "Not specified"}
- Subject: {subject if subject else "Not specified"}

If the document contains information for multiple classes or subjects, you MUST ONLY process and return data for the specified class and subject above. Ignore all other classes and subjects in the document.

INPUTS:
- ExtractedText: {extracted_text}
- GCSFileLocation: {gcs_source_path}
- WeeklySessions: {json.dumps(session_data, indent=2) if session_data else "No session data provided"}

AVAILABLE WEEKS: {', '.join(available_weeks) if available_weeks else "None"}
WEEK DETAILS: {', '.join(week_details) if week_details else "No weeks available"}

STRICT INSTRUCTIONS - READ CAREFULLY:
1. The weeks mentioned in the ExtractedText or the original document are FOR REFERENCE ONLY to understand the duration of each strand
2. You MUST IGNORE any week numbers mentioned in the ExtractedText or original document for your final output
3. You MUST ONLY use the weeks and sessions provided in the WeeklySessions data above
4. The WeeklySessions data contains the ACTUAL available teaching weeks and sessions for this specific class
5. Any week numbers in the ExtractedText or document are for your understanding of strand duration, NOT for mapping
6. You MUST ONLY process data for the specified Class Name and Subject provided above
7. If the document contains multiple classes or subjects, IGNORE all except the specified Class Name and Subject
8. ALL curriculum elements (strands, substrands, content standards, indicators) MUST be for the specified Class Name and Subject only
9. CRITICAL FORMAT REQUIREMENT: Week numbers MUST be provided as NUMERIC VALUES ONLY (e.g., [1, 2, 3]) NOT as text (e.g., ["Week 1", "Week 2", "Week 3"])
10. CRITICAL FORMAT REQUIREMENT: You MUST return FLAT STRUCTURES for all curriculum elements:
    - strand_data: Array of strand objects with strand_name field
    - substrand_data: Array of substrand objects with strand_name and substrand_name fields
    - content_standard_data: Array of content standard objects with strand_name, substrand_name, content_standard_code, and content_standard_text fields
    - indicator_data: Array of indicator objects with strand_name, substrand_name, content_standard_code, indicator_code, and indicator_text fields
11. DO NOT return nested structures where substrand_data is inside strand_data
12. Each curriculum element MUST have its own entry in the appropriate array
13. Use the field names EXACTLY as specified above (e.g., strand_name, substrand_name, content_standard_text, indicator_text)
14. CRITICAL REQUIREMENT: For ALL curriculum elements (strand, substrand, content standard, indicator), you MUST include the "sessions" array with session details from the WeeklySessions data
15. CRITICAL REQUIREMENT: For each session in the sessions array, you MUST include ALL of these fields:
    - id: The session ID from WeeklySessions
    - date: The session date from WeeklySessions
    - start_time: The session start time from WeeklySessions
    - end_time: The session end time from WeeklySessions
    - week_number: The week number from WeeklySessions
16. CRITICAL REQUIREMENT: You MUST return the FULL TEXT for ALL content standards and indicators, NOT just the codes
17. CRITICAL REQUIREMENT: You MUST ONLY use the weeks provided in WeeklySessions data, NOT weeks mentioned in the document

CRITICAL REQUIREMENT: Each curriculum element MUST have session data in the "sessions" array.
CRITICAL REQUIREMENT: DO NOT put session data in "session_ids" or "session_details" fields.
CRITICAL REQUIREMENT: Session data MUST be in the "sessions" array with the exact field names specified above.
CRITICAL REQUIREMENT: You MUST return the FULL TEXT for ALL content standards and indicators, NOT just the codes.
CRITICAL REQUIREMENT: You MUST ONLY use the weeks provided in WeeklySessions data, NOT weeks mentioned in the document.

STRICT STRAND BOUNDARY RULES:
Each strand must have its own distinct weeks. For example:
{chr(10).join([f"- {strand}: {weeks}" for strand, weeks in strand_boundaries.items()]) if strand_boundaries else "No strand boundaries defined"}

CONTENT STANDARD AND INDICATOR ASSIGNMENT RULES:
1. EACH content standard MUST be assigned to at least one session from its parent substrand
2. EACH indicator MUST be assigned to at least one session from its parent content standard's sessions
3. EVERY single indicator of a strand MUST be assigned to at least one session of its content standard
4. A session CAN have at most TWO indicators assigned to it
5. ONLY in extreme cases can a session have two indicators (indicators can be paired with another indicator)
6. Aside from extreme cases, indicators should have exactly ONE session each
7. When assigning sessions, ensure even distribution of indicators across available sessions

STRICT RULES FOR CURRICULUM MAPPING:
1. ONLY use weeks that are explicitly provided in WeeklySessions (see AVAILABLE WEEKS above)
2. NEVER create or invent weeks that are not in the provided WeeklySessions data
3. ALL members of a strand (substrands, content standards, indicators) MUST be within the week bounds of that specific strand
4. Strand A members MUST ONLY use Strand A's assigned weeks, even if Strand B has unassigned sessions
5. Each strand must have its own distinct week boundaries - NO cross-strand week assignments
6. ONLY use session data that is explicitly provided in WeeklySessions
7. NEVER make assumptions or create imaginary session data
8. ALL session details must be copied EXACTLY from WeeklySessions - DO NOT modify or invent session details
9. When creating a strand, define its weeks field - this becomes the boundary for ALL its members
10. ALL substrands, content standards, and indicators MUST use weeks from their parent strand's weeks field ONLY
11. ALL curriculum elements MUST be for the specified Class Name: {class_name if class_name else 'Not specified'} and Subject: {subject if subject else 'Not specified'} only
12. CRITICAL FORMAT REQUIREMENT: Week numbers MUST be provided as NUMERIC VALUES ONLY (e.g., [1, 2, 3]) NOT as text (e.g., ["Week 1", "Week 2", "Week 3"])
13. CRITICAL FORMAT REQUIREMENT: Use the EXACT field names specified:
    - For strands: strand_name (NOT name)
    - For substrands: substrand_name (NOT name)
    - For content standards: content_standard_text (NOT name)
    - For indicators: indicator_text (NOT name)
14. CRITICAL REQUIREMENT: For ALL curriculum elements (strand, substrand, content standard, indicator), you MUST include the "sessions" array with session details from the WeeklySessions data
15. CRITICAL REQUIREMENT: For each session in the sessions array, you MUST include ALL of these fields:
    - id: The session ID from WeeklySessions
    - date: The session date from WeeklySessions
    - start_time: The session start time from WeeklySessions
    - end_time: The session end time from WeeklySessions
    - week_number: The week number from WeeklySessions
16. CRITICAL REQUIREMENT: You MUST return the FULL TEXT for ALL content standards and indicators, NOT just the codes
17. CRITICAL REQUIREMENT: You MUST ONLY use the weeks provided in WeeklySessions data, NOT weeks mentioned in the document

TASK:
1. Analyze BOTH the ExtractedText AND the original file at GCSFileLocation for complete curriculum information
2. Use the weeks mentioned in the text/document ONLY to understand how long each strand should last
3. Identify strands, substrands, content standards, and indicators from the combined analysis BUT ONLY for the specified Class Name and Subject
4. Map these elements to FLAT STRUCTURES (not nested):
   - Create strand_data entries with strand information including weeks (this defines the strand boundary)
   - Create substrand_data entries with substrand information (must use weeks from parent strand only)
   - Create content_standard_data entries with content standard information (must use weeks from parent strand only)
   - Create indicator_data entries with indicator information (must use weeks from parent strand only)
5. For each entry, map to actual sessions from WeeklySessions ONLY
6. For each mapping, COPY EXACT session details (id, date, start_time, end_time, week_number) from WeeklySessions
7. Return ONLY valid JSON matching the format below

IMPORTANT INSTRUCTIONS:
- The example JSON below is ONLY for showing the STRUCTURE - DO NOT copy the example values
- COPY session details EXACTLY from WeeklySessions - DO NOT make up values
- ONLY use sessions that are provided in WeeklySessions
- Each session in WeeklySessions contains ONLY these fields: id, date, start_time, end_time, week_number
- Map content linearly across weeks using the sessions provided in WeeklySessions
- Each session should only be used once
- Return ONLY the JSON, nothing else
- DO NOT wrap the output in markdown code blocks like ```json ... ```
- DO NOT include any introductory or concluding text
- just raw JSON starting with [ or {{ and ending with ] or }}
- ONLY use weeks that are listed in AVAILABLE WEEKS above
- NEVER create session data that is not in WeeklySessions
- ONLY process data for Class Name: {class_name if class_name else 'Not specified'} and Subject: {subject if subject else 'Not specified'}
- CRITICAL FORMAT REQUIREMENT: Week numbers MUST be provided as NUMERIC VALUES ONLY (e.g., [1, 2, 3]) NOT as text (e.g., ["Week 1", "Week 2", "Week 3"])
- CRITICAL FORMAT REQUIREMENT: Use the EXACT field names specified:
    - For strands: strand_name (NOT name)
    - For substrands: substrand_name (NOT name)
    - For content standards: content_standard_text (NOT name)
    - For indicators: indicator_text (NOT name)
- CRITICAL REQUIREMENT: For ALL curriculum elements (strand, substrand, content standard, indicator), you MUST include the "sessions" array with session details from the WeeklySessions data
- CRITICAL REQUIREMENT: For each session in the sessions array, you MUST include ALL of these fields:
    - id: The session ID from WeeklySessions
    - date: The session date from WeeklySessions
    - start_time: The session start time from WeeklySessions
    - end_time: The session end time from WeeklySessions
    - week_number: The week number from WeeklySessions
- CRITICAL REQUIREMENT: You MUST return the FULL TEXT for ALL content standards and indicators, NOT just the codes
- CRITICAL REQUIREMENT: You MUST ONLY use the weeks provided in WeeklySessions data, NOT weeks mentioned in the document
- The weeks in the document are ONLY for understanding strand duration, NOT for actual mapping
- ALL actual mapping MUST use the provided WeeklySessions data
"""
    
    return prompt


async def send_semester_plan_to_ai(extracted_text: str, gcs_source_path: str, api_key: str, session_data: dict = None, class_name: str = None, subject: str = None) -> dict:
    """
    Send semester plan data to AI for processing and return structured results.
    
    Args:
        extracted_text: The raw text extracted from the semester plan document (may be incomplete)
        gcs_source_path: The Google Cloud Storage path to the original semester plan file
        api_key: The API key for the AI service (Google Gemini)
        session_data: Session data including academic calendar and class sessions
        class_name: The specific class name to focus on (optional)
        subject: The specific subject to focus on (optional)
        
    Returns:
        A dictionary with the AI-processed semester plan data
    """
    try:
        logger.info(f"🚀 Sending semester plan data to AI for processing")
        logger.info(f"📂 GCS Source Path: {gcs_source_path}")
        logger.info(f"📊 Extracted Text Length: {len(extracted_text)} characters")
        # Log a warning if extracted text is very short
        if len(extracted_text) < 100:
            logger.warning(f"⚠️ Extracted text is very short ({len(extracted_text)} characters). AI will rely heavily on the original GCS file for complete information.")
        
        # Log session data being sent to AI for debugging
        if session_data:
            logger.info(f"📅 SESSION DATA BEING SENT TO AI:")
            logger.info(f"   Semester Start: {session_data.get('semester_start_date', 'Not provided')}")
            logger.info(f"   Semester End: {session_data.get('semester_end_date', 'Not provided')}")
            weekly_sessions = session_data.get('weekly_sessions', {})
            logger.info(f"   Number of Weeks: {len(weekly_sessions)}")
            for week_key, week_data in weekly_sessions.items():
                logger.info(f"     {week_key}: {len(week_data.get('sessions', []))} sessions")
            # Log the actual weeks available to make it clear to the AI
            available_weeks = list(weekly_sessions.keys())
            logger.info(f"   🔑 AVAILABLE WEEKS FOR MAPPING (AI MUST USE ONLY THESE): {', '.join(available_weeks)}")
            logger.info(f"   📌 IMPORTANT: AI has been instructed to IGNORE any week numbers in the document/extracted text")
        else:
            logger.warning("⚠️ NO SESSION DATA PROVIDED TO AI")
        
        # Build the prompt
        prompt = build_semester_plan_prompt(extracted_text, gcs_source_path, session_data, class_name, subject)
        logger.info(f"📝 Prompt Length: {len(prompt)} characters")
        # Log a sample of the prompt being sent to AI (first 1000 characters)
        logger.info(f"📝 SAMPLE OF PROMPT BEING SENT TO AI: {prompt[:1000]}...")
        
        # Get access token from service account for Vertex AI (with caching and retry logic)
        global _cached_credentials, _token_expiry
        
        # Retry configuration for authentication
        max_auth_retries = 5
        auth_retry_delay = 2  # Start with 2 seconds
        access_token = None
        
        for auth_attempt in range(max_auth_retries):
            try:
                # Check if we have a valid cached token
                if _cached_credentials and _token_expiry and datetime.now() < _token_expiry:
                    access_token = _cached_credentials.token
                    logger.info("✅ Using cached access token")
                    break  # Success, exit retry loop
                else:
                    from google.oauth2 import service_account
                    from google.auth.transport.requests import Request
                    import json as json_lib
                    import time
                    
                    if auth_attempt > 0:
                        logger.info(f"🔄 Reauthentication attempt {auth_attempt + 1}/{max_auth_retries}...")
                    else:
                        logger.info("🔄 Fetching new access token...")
                    
                    # Load service account credentials
                    if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
                        service_account_info = json_lib.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
                    else:
                        with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                            service_account_info = json_lib.load(f)
                    
                    # Create credentials
                    credentials = service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=['https://www.googleapis.com/auth/cloud-platform']
                    )
                    
                    # Get access token
                    credentials.refresh(Request())
                    access_token = credentials.token
                    
                    # Cache credentials (tokens last ~1 hour, refresh after 55 min)
                    _cached_credentials = credentials
                    _token_expiry = datetime.now() + timedelta(minutes=55)
                    
                    logger.info("✅ Successfully obtained and cached new access token")
                    break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e)
                is_network_error = any(keyword in error_msg.lower() for keyword in [
                    'nameerror', 'getaddrinfo', 'dns', 'connection', 'timeout', 
                    'oauth2.googleapis.com', 'max retries'
                ])
                
                if auth_attempt < max_auth_retries - 1:
                    if is_network_error:
                        logger.warning(f"⚠️ Network error during authentication (attempt {auth_attempt + 1}/{max_auth_retries}): {error_msg}")
                        logger.warning(f"   Retrying in {auth_retry_delay} seconds...")
                    else:
                        logger.warning(f"⚠️ Authentication error (attempt {auth_attempt + 1}/{max_auth_retries}): {error_msg}")
                        logger.warning(f"   Retrying in {auth_retry_delay} seconds...")
                    
                    time.sleep(auth_retry_delay)
                    auth_retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ Failed to authenticate after {max_auth_retries} attempts")
                    logger.error(f"   Final error: {error_msg}")
                    if is_network_error:
                        logger.error("   This appears to be a network/DNS issue. Please check your internet connection.")
                    raise Exception(f"Failed to authenticate with Vertex AI after {max_auth_retries} attempts: {e}")
        
        if not access_token:
            raise Exception("Failed to obtain access token after all retry attempts")
        
        # Use Vertex AI endpoint with us-central1 location
        project_id = settings.GCS_PROJECT_ID
        model_id = "gemini-2.5-flash"
        url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
        logger.info(f"🔗 Sending request to Vertex AI: {url}")
        
        # Create the payload with text prompt and Google Search grounding
        # NOTE: We do NOT use responseMimeType: 'application/json' here because it conflicts 
        # with Google Search tools in some Vertex AI model versions. We rely on the prompt to enforce JSON.
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.5,
                "maxOutputTokens": 65536,  # Increased to prevent truncation
            },
            "tools": [
                {
                    "google_search": {}
                }
            ]
        }
        
        logger.info("✅ Google Search grounding enabled for curriculum data retrieval")
        
        # DEBUG LOGGING TO sent.txt as requested
        try:
            with open("sent.txt", "w", encoding="utf-8") as f:
                f.write(f"--- TIMESTAMP: {datetime.now().isoformat()} ---\n\n")
                f.write(f"--- WEEKLY SESSION DATA ---\n")
                f.write(json.dumps(session_data, indent=2, default=str) if session_data else "No Session Data Provided")
                f.write("\n\n")
                f.write(f"--- EXACT PROMPT SENT TO AI ---\n")
                f.write(prompt)
                f.write("\n\n")
                f.write(f"--- FULL PAYLOAD STRUCT ---\n")
                f.write(json.dumps(payload, indent=2, default=str))
            logger.info("📝 Detailed debug info written to sent.txt")
        except Exception as e:
            logger.error(f"Failed to write to sent.txt: {e}")
        
        # Set headers with Bearer token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # ============================================================================
        # RETRY LOGIC WITH EXPONENTIAL BACKOFF
        # ============================================================================
        max_retries = 5
        retry_delay = 20  # Start with 20 seconds
        timeout_seconds = 300  # 5 minutes per attempt
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} after {retry_delay}s delay...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.info(f"📤 Sending AI request (attempt {attempt + 1}/{max_retries})...")
                
                # Send request to AI service with timeout
                timeout = aiohttp.ClientTimeout(total=timeout_seconds)
                logger.info(f"⏱️ Request timeout set to {timeout_seconds} seconds (5 minutes)")
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=payload) as response:
                        response_text = await response.text()
                
                        # DEBUG LOGGING response to sent2.txt
                        try:
                            with open("sent2.txt", "w", encoding="utf-8") as f:
                                f.write(f"--- TIMESTAMP: {datetime.now().isoformat()} ---\n\n")
                                f.write(f"--- RAW AI API RESPONSE ---\n")
                                f.write(response_text)
                            logger.info("📝 Detailed response debug info written to sent2.txt")
                        except Exception as e:
                            logger.error(f"Failed to write to sent2.txt: {e}")
        
                        logger.info(f"📡 AI API Response Status: {response.status}")
                        
                        # Check if request was successful
                        if response.status == 200:
                            response_data = json.loads(response_text)
                            logger.info(f"✅ AI API Response Received Successfully")
                            
                            # Log the full response for debugging
                            logger.info(f"📋 AI Response: {str(response_data)}")
                            
                            # Extract the generated content
                            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                                content = response_data["candidates"][0].get("content", {})
                                if "parts" in content and len(content["parts"]) > 0:
                                    result_text = content["parts"][0].get("text", "")
                                    logger.info(f"🔍 AI Generated Content Length: {len(result_text)} characters")
                                    
                                    # Try to parse as JSON with more robust error handling
                                    try:
                                        # Clean up the response text to extract JSON
                                        
                                        # Strategy 0: Check for markdown code blocks first (most reliable)
                                        # Look for ```json ... ``` or just ``` ... ``` containing { or [
                                        markdown_match = re.search(r"```(?:json)?\s*([\[\{][\s\S]*?[\]\}])\s*```", result_text)
                                        
                                        json_str = None
                                        if markdown_match:
                                            json_str = markdown_match.group(1)
                                            logger.info(f"📦 JSON Extracted from Markdown Code Block, Length: {len(json_str)} characters")
                                        else:
                                            # Fallback 1: Check if the text itself looks like JSON (starts with { or [)
                                            stripped_text = result_text.strip()
                                            if stripped_text.startswith('{') or stripped_text.startswith('['):
                                                json_str = stripped_text
                                                logger.info(f"📦 JSON Extracted from Raw Text (Direct Match), Length: {len(json_str)} characters")
                                            else:
                                                # Fallback 2: regex search for outer-most Object or Array
                                                # We look for both and take the longest valid-looking one to avoid partial matches
                                                list_match = re.search(r"\[[\s\S]*\]", result_text)
                                                obj_match = re.search(r"\{[\s\S]*\}", result_text)
                                                
                                                candidates = []
                                                if list_match: candidates.append(list_match.group(0))
                                                if obj_match: candidates.append(obj_match.group(0))
                                                
                                                if candidates:
                                                    # Pick the longest match (e.g. if we have [ { } ], list is longer than obj)
                                                    json_str = max(candidates, key=len)
                                                    logger.info(f"📦 JSON Extracted from Regex Search, Length: {len(json_str)} characters")
                                        
                                        if json_str:
                                            
                                            # Try multiple JSON parsing strategies
                                            parsed_result = None
                                            parsing_errors = []
                                            
                                            # Strategy 1: Direct parsing with raw_decode to handle "Extra data"
                                            try:
                                                # Use raw_decode to parse just the JSON part and ignore any trailing characters
                                                parsed_result, end_index = json.JSONDecoder().raw_decode(json_str)
                                                # If we parsed something and it looks like a valid structure
                                                if parsed_result is not None:
                                                    # If there was extra data, log it but proceed with the result
                                                    if end_index < len(json_str):
                                                        remaining = json_str[end_index:].strip()
                                                        if remaining:
                                                            logger.warning(f"⚠️ Metadata parsed but extra data found: {len(remaining)} chars. Ignoring.")
                                                    
                                                    logger.info(f"🎉 AI Response Parsed Successfully (Direct/Raw Decode)")
                                            except json.JSONDecodeError as e:
                                                parsing_errors.append(f"Direct parsing failed: {e}")
                                                logger.warning(f"⚠️ Direct parsing failed: {e}")
                                                        
                                            # (continuing with all other strategies...)
                                            if parsed_result is not None:
                                                # Log the complete parsed AI response for debugging
                                                logger.info(f"🤖 COMPLETE PARSED AI RESPONSE: {json.dumps(parsed_result, indent=2, default=str)}")
                                                return parsed_result
                                            else:
                                                logger.error(f"💥 All JSON parsing strategies failed")
                                                return {"error": "JSON parsing failed after multiple strategies", "raw_response": result_text, "parsing_errors": parsing_errors}
                                        else:
                                            logger.warning(f"⚠️ No JSON found in AI response: {result_text[:200]}...")
                                            return {"error": "No JSON found in AI response", "raw_response": result_text}
                                    except Exception as e:
                                        logger.error(f"💥 Unexpected error during JSON parsing: {e}")
                                        logger.error(f"📄 Raw response: {result_text[:500]}...")
                                        return {"error": f"Unexpected error during JSON parsing: {str(e)}", "raw_response": result_text}
                                else:
                                    logger.warning("No content parts found in AI response")
                                    return {"error": "No content parts found in AI response"}
                            else:
                                logger.warning("No candidates found in AI response")
                                return {"error": "No candidates found in AI response"}
                        
                        # Non-200 responses - check if it's a retryable error
                        else:
                            # Handle rate limit (HTTP 429) gracefully with exponential backoff
                            if response.status == 429:
                                logger.warning(f"⚠️ Quota/rate limit hit (HTTP 429) - attempt {attempt + 1}/{max_retries}")
                                
                                if attempt < max_retries - 1:
                                    # Use longer wait time for quota errors (10 seconds * attempt number)
                                    quota_wait_time = 10 * (attempt + 1)
                                    logger.warning(f"⏰ Quota exhausted. Retrying in {quota_wait_time}s...")
                                    import time
                                    time.sleep(quota_wait_time)
                                    continue  # Retry
                                else:
                                    logger.error(f"❌ Max retry attempts reached for rate limit errors")
                                    logger.error(f"Response: {response_text}")
                                    return {
                                        "error": f"AI API request failed with status {response.status}", 
                                        "details": response_text,
                                        "quota_exhausted": True
                                    }
                            
                            # For other non-200 responses, return error immediately
                            else:
                                logger.error(f"AI API request failed with status {response.status}: {response_text}")
                                return {"error": f"AI API request failed with status {response.status}", "details": response_text}
            
            except asyncio.TimeoutError as timeout_error:
                logger.warning(f"⏱️ AI API request timed out (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.warning(f"   Retrying in {retry_delay} seconds...")
                    retry_delay *= 2  # Exponential backoff: 20s → 40s → 80s → 160s → 320s
                    continue  # Retry
                else:
                    logger.error(f"❌ Failed after {max_retries} attempts - all timed out")
                    logger.error("   This indicates persistent network or service issues")
                    return {"error": f"AI API timed out after {max_retries} attempts", "timeout": True}
            
            except aiohttp.ClientError as network_error:
                logger.warning(f"🌐 Network error (attempt {attempt + 1}/{max_retries}): {network_error}")
                if attempt < max_retries - 1:
                    logger.warning(f"   Retrying in {retry_delay} seconds...")
                    retry_delay *= 2  # Exponential backoff
                    continue  # Retry
                else:
                    logger.error(f"❌ Failed after {max_retries} attempts - network errors")
                    return {"error": f"Network error after {max_retries} attempts: {str(network_error)}", "network_error": True}
            
            except Exception as request_error:
                logger.error(f"💥 Unexpected error during AI request (attempt {attempt + 1}/{max_retries}): {request_error}")
                if attempt < max_retries - 1:
                    logger.warning(f"   Retrying in {retry_delay} seconds...")
                    retry_delay *= 2  # Exponential backoff
                    continue  # Retry
                else:
                    logger.error(f"❌ Failed after {max_retries} attempts")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {"error": f"Request failed after {max_retries} attempts: {str(request_error)}"}
        
        # If we get here, all retries were exhausted
        logger.error(f"❌ All {max_retries} attempts exhausted")
        return {"error": f"All {max_retries} retry attempts failed"}
        
    except Exception as e:
        logger.error(f"💥 AI Semester Plan Processing Error: {e}", exc_info=True)
        return {"error": str(e)}

# Holiday fetching function updated to use Google AI API