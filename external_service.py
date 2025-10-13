import json
from datetime import datetime
import re
import requests
import logging
from config import settings

# Initialize logger
logger = logging.getLogger(__name__)


def get_holidays_from_ai(country: str, year: int):
    """
    Fetch up-to-date national/public holidays using Google AI API with browser search tool.
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
    try:
        # ✅ Build structured prompt for holiday fetching
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
            "instruction": "Return ONLY a valid JSON object. Do not include text, code, or sources."
        }
        
        # ✅ Prepare the request for Google Generative AI API (Gemini)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={settings.API_KEY}"
        
        # ✅ Create the request payload
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(prompt_json, indent=2)
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0,
                "topP": 1,
                "responseMimeType": "application/json"
            },
            "tools": [
                {
                    "googleSearchRetrieval": {
                        "disableAttribution": False
                    }
                }
            ]
        }
        
        # Add detailed logging of what is sent to AI
        logger.info("=====START OF WHAT IS SENT TO AI=====")
        logger.info(f"URL: https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={settings.API_KEY[:8]}...{settings.API_KEY[-4:]}")
        logger.info("HEADERS: {'Content-Type': 'application/json'}")
        logger.info("PAYLOAD:")
        logger.info(json.dumps(payload, indent=2))
        logger.info("=====END OF WHAT IS SENT TO AI=====")
        
        # ✅ Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # ✅ Send request to Google AI service
        response = requests.post(url, headers=headers, json=payload)
        
        # ✅ Check if request was successful
        if response.status_code == 200:
            response_data = response.json()
            
            # ✅ Extract the generated content
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                content = response_data["candidates"][0].get("content", {})
                if "parts" in content and len(content["parts"]) > 0:
                    response_text = content["parts"][0].get("text", "")
                    
                    # ✅ Extract JSON from response
                    match = re.search(r"\{[\s\S]*\}", response_text)
                    if match:
                        json_str = match.group(0)
                        try:
                            parsed_response = json.loads(json_str)
                            holidays = parsed_response.get("holidays", [])
                            
                            # ✅ Log success
                            print(f"🎉 AI (Google AI Search) returned {len(holidays)} holidays for {country} in {year}.")
                            
                            return holidays
                            
                        except json.JSONDecodeError as e:
                            print(f"⚠️ JSON parsing error: {e}")
                            print(f"📄 Raw JSON string: {json_str}")
                            return []
                    else:
                        print("⚠️ No JSON found in AI response")
                        print(f"📄 Full response: {response_text}")
                        return []
                else:
                    print("⚠️ No content parts found in AI response")
                    return []
            else:
                print("⚠️ No candidates found in AI response")
                return []
        else:
            print(f"💥 AI API request failed with status {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        print(f"💥 AI Holiday Fetch Error (Google AI): {e}")
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


def send_academic_calendar_to_ai(extracted_text: str, gcs_source_path: str, api_key: str, additional_data: str = "") -> dict:
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
        response = requests.post(url, headers=headers, json=payload)
        logger.info(f"📡 AI API Response Status: {response.status_code}")
        
        # Check if request was successful
        if response.status_code == 200:
            response_data = response.json()
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
            logger.error(f"AI API request failed with status {response.status_code}: {response.text}")
            return {"error": f"AI API request failed with status {response.status_code}", "details": response.text}
        
    except Exception as e:
        logger.error(f"AI Academic Calendar Processing Error: {e}", exc_info=True)
        return {"error": str(e)}


def send_timetable_to_ai(extracted_text: str, gcs_source_path: str, api_key: str) -> dict:
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
        response = requests.post(url, headers=headers, json=payload)
        logger.info(f"📡 AI API Response Status: {response.status_code}")
        
        # Check if request was successful
        if response.status_code == 200:
            response_data = response.json()
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
            logger.error(f"AI API request failed with status {response.status_code}: {response.text}")
            return {"error": f"AI API request failed with status {response.status_code}", "details": response.text}
        
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
    import json
    
    # Extract available weeks from session_data
    available_weeks = []
    week_details = []
    
    if session_data and 'weekly_sessions' in session_data:
        available_weeks = sorted([int(w.replace('Week ', '')) for w in session_data['weekly_sessions'].keys()])
        for week_key, week_data in sorted(session_data['weekly_sessions'].items()):
            session_count = len(week_data.get('sessions', []))
            week_details.append(f"{week_key}: {session_count} sessions")
    
    # Format session data for clarity
    session_data_str = json.dumps(session_data, indent=2) if session_data else "No session data provided"
    available_weeks_str = ', '.join([str(w) for w in available_weeks]) if available_weeks else "None"
    
    prompt = f"""You are an Educational Curriculum Mapping AI. Your task is to map curriculum elements (strands, substrands, content standards, indicators) to actual teaching sessions.

TARGET CLASS AND SUBJECT:
Class Name: {class_name or 'Not specified'}
Subject: {subject or 'Not specified'}

PROCESS ONLY data for this specific class and subject. Ignore all other classes/subjects in the document.

INPUT DATA:
ExtractedText:
{extracted_text}

GCSFileLocation: {gcs_source_path}

Available Teaching Weeks: {available_weeks_str}
Week Details:
{chr(10).join(week_details) if week_details else 'No week information available'}

Session Data Structure:
{session_data_str}

OUTPUT FORMAT:
Return a single JSON object with these four arrays:

{{
  "strand_data": [
    {{
      "strand_name": "Strand Name",
      "weeks": [1, 2, 3],
      "sessions": [
        {{"id": "s1", "date": "2024-01-15", "start_time": "09:00", "end_time": "10:00", "week_number": 1}},
        {{"id": "s2", "date": "2024-01-22", "start_time": "09:00", "end_time": "10:00", "week_number": 2}}
      ]
    }}
  ],
  "substrand_data": [
    {{
      "strand_name": "Parent Strand Name",
      "substrand_name": "Substrand Name",
      "weeks": [1, 2],
      "sessions": [...]
    }}
  ],
  "content_standard_data": [
    {{
      "strand_name": "Parent Strand Name",
      "substrand_name": "Parent Substrand Name",
      "content_standard_code": "CODE.1",
      "content_standard_text": "Full description of what students should know",
      "sessions": [...]
    }}
  ],
  "indicator_data": [
    {{
      "strand_name": "Parent Strand Name",
      "substrand_name": "Parent Substrand Name",
      "content_standard_code": "CODE.1",
      "indicator_code": "CODE.1.1",
      "indicator_text": "Specific measurable indicator",
      "sessions": [...]
    }}
  ]
}}

CRITICAL REQUIREMENTS:

1. Week Numbers:
   - ONLY use weeks from the Available Teaching Weeks list above
   - Format weeks as numeric arrays: [1, 2, 3] NOT ["Week 1", "Week 2"]
   - Use document week references ONLY to understand strand duration
   - Do not plan with the weeks in the document or the document's extract, except that week also is available in the teaching weeks list
   - You must plan with the available teaching weeks
   - Do not plan outside the available teaching weeks
   - If i find out your are planning outside the available teaching weeks or using weeks in the document instead of the available teaching weeks, I will deduct points from your score


2. Session Data:
   - Copy session details EXACTLY from the provided session data
   - Each session must have: id, date, start_time, end_time, week_number
   - NEVER create or invent session data
   - Sessions of each strand member, should be a session found in the weeks or week of the parent strand
   - Each session of each substrand , should be a session found in the weeks or week of the parent strand
   - Each session of a content standard, should be a session found in the weeks or week of the parent substrand
   - Each session of an indicator, should be a session found in the weeks or week of the parent content standard

3. Curriculum Structure:
   - ALL four data arrays must be FLAT (not nested)
   - Each element must reference its parent using: strand_name, substrand_name, content_standard_code
   - Preserve or create(if not available) full text for content_standard_text and indicator_text (NOT just codes)
   - The content_standard_text and indicator_text are the full text of the content standard and indicator, they are not codes
   - Do not return codes as content_standard_text or indicator_text, if the document deosnt provide one, youre are free to generate one base on the strand and substrand

4. Field Names (use EXACTLY as shown):
   - strand_name (not "name" or "strand")
   - substrand_name (not "name" or "substrand")
   - content_standard_text (not "name" or "description")
   - indicator_text (not "name" or "description")
   - content_standard_code, indicator_code (use actual codes from document)

5. Logical Mapping:
   - Each strand defines its week boundary via the "weeks" field
   - All substrands/content_standards/indicators of a strand MUST use weeks and sessions from that strand ONLY
   - No cross-strand week usage
   - Distribute indicators across sessions 

6. Data Validation:
   - Verify all references exist (substrand references strand, content standard references substrand, etc.)
   - Verify all weeks referenced are in the Available Teaching Weeks list
   - Verify all session IDs exist in the provided session data
   - Do not return any data on revision, examination, or holiday or any other events 

MAPPING WORKFLOW:
1. Extract curriculum hierarchy from ExtractedText
2. Identify which document weeks each strand spans (for reference only)
3. Assign each strand to available teaching weeks
4. Create flat array entries for each curriculum element
5. Assign sessions to each element based on its assigned weeks
6. Validate all references and data completeness

Return ONLY valid JSON. Do not include explanations or markdown formatting."""
    
    return prompt


def send_semester_plan_to_ai(extracted_text: str, gcs_source_path: str, api_key: str, session_data: dict = None, class_name: str = None, subject: str = None) -> dict:
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
        
        # Prepare the request for Google Vertex AI API (Gemini) - Use the same endpoint as timetable
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY}"
        logger.info(f"🔗 Sending request to AI API")
        
        # Create the payload with only the text prompt (no file data)
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
                "temperature": 0.3,
                "responseMimeType": "application/json"
            }
        }
        
        # Add detailed logging of what is sent to AI
        logger.info("=====START OF WHAT IS SENT TO AI=====")
        logger.info(f"URL: https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY[:8]}...{settings.API_KEY[-4:]}")
        logger.info("HEADERS: {'Content-Type': 'application/json'}")
        logger.info("PAYLOAD:")
        logger.info(json.dumps(payload, indent=2))
        logger.info("=====END OF WHAT IS SENT TO AI=====")
        
        # Set headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Send request to AI service
        response = requests.post(url, headers=headers, json=payload)
        logger.info(f"📡 AI API Response Status: {response.status_code}")
        
        # Check if request was successful
        if response.status_code == 200:
            response_data = response.json()
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
                        # First, try to find JSON object pattern
                        json_match = re.search(r"\{[\s\S]*\}", result_text)
                        if json_match:
                            json_str = json_match.group(0)
                            logger.info(f"📦 JSON Extracted from AI Response, Length: {len(json_str)} characters")
                            
                            # Try multiple JSON parsing strategies
                            parsed_result = None
                            parsing_errors = []
                            
                            # Strategy 1: Direct parsing
                            try:
                                parsed_result = json.loads(json_str)
                                logger.info(f"🎉 AI Response Parsed Successfully (Direct)")
                            except json.JSONDecodeError as e:
                                parsing_errors.append(f"Direct parsing failed: {e}")
                                logger.warning(f"⚠️ Direct parsing failed: {e}")
                            
                            # Strategy 2: If direct parsing fails, try to fix common issues
                            if parsed_result is None:
                                try:
                                    # Fix common JSON issues
                                    fixed_json = json_str
                                    
                                    # Fix trailing commas before closing braces/brackets
                                    fixed_json = re.sub(r",(\s*[}\]])", r"\1", fixed_json)
                                    
                                    # Fix single quotes to double quotes (be careful not to mess up escaped quotes)
                                    # This is a simple approach - more sophisticated handling might be needed
                                    fixed_json = re.sub(r"'([^']*)':", r'"\1":', fixed_json)  # Keys
                                    fixed_json = re.sub(r":\s*'([^']*)'", r': "\1"', fixed_json)  # String values
                                    
                                    parsed_result = json.loads(fixed_json)
                                    logger.info(f"🎉 AI Response Parsed Successfully (With Fixes)")
                                except json.JSONDecodeError as e:
                                    parsing_errors.append(f"Fixed parsing failed: {e}")
                                    logger.warning(f"⚠️ Fixed parsing failed: {e}")
                            
                            # Strategy 3: If still failing, try to extract and parse line by line
                            if parsed_result is None:
                                try:
                                    lines = json_str.split('\n')
                                    cleaned_lines = []
                                    for line in lines:
                                        # Remove comments (everything after //)
                                        line = re.split(r'//', line)[0]
                                        # Remove extra whitespace
                                        line = line.strip()
                                        if line:
                                            cleaned_lines.append(line)
                                    
                                    cleaned_json = '\n'.join(cleaned_lines)
                                    parsed_result = json.loads(cleaned_json)
                                    logger.info(f"🎉 AI Response Parsed Successfully (Line-by-line cleaning)")
                                except json.JSONDecodeError as e:
                                    parsing_errors.append(f"Line-by-line parsing failed: {e}")
                                    logger.warning(f"⚠️ Line-by-line parsing failed: {e}")
                            
                            # Strategy 4: More advanced JSON fixing for comma issues
                            if parsed_result is None:
                                try:
                                    # Try to fix missing commas between object properties
                                    fixed_json = json_str
                                    
                                    # Fix missing commas between object properties
                                    # Look for patterns like }"key" and add comma: },"key"
                                    fixed_json = re.sub(r'(\})\s*"', r'\1,"', fixed_json)
                                    
                                    # Fix missing commas between array elements
                                    # Look for patterns like ]{ and add comma: ],{
                                    fixed_json = re.sub(r'(\])\s*\{', r'\1,\{', fixed_json)
                                    
                                    # Fix missing commas between array elements
                                    # Look for patterns like }{ and add comma: },{
                                    fixed_json = re.sub(r'(\})\s*\{', r'\1,\{', fixed_json)
                                    
                                    # Try to parse the fixed JSON
                                    parsed_result = json.loads(fixed_json)
                                    logger.info(f"🎉 AI Response Parsed Successfully (Advanced comma fixes)")
                                except json.JSONDecodeError as e:
                                    parsing_errors.append(f"Advanced comma fixes failed: {e}")
                                    logger.warning(f"⚠️ Advanced comma fixes failed: {e}")
                            
                            # Strategy 5: Brute force approach - try to parse with more aggressive cleaning
                            if parsed_result is None:
                                try:
                                    # Aggressive cleaning approach
                                    fixed_json = json_str
                                    
                                    # Remove any non-JSON text before the first {
                                    first_brace = fixed_json.find('{')
                                    if first_brace > 0:
                                        fixed_json = fixed_json[first_brace:]
                                    
                                    # Remove any non-JSON text after the last }
                                    last_brace = fixed_json.rfind('}')
                                    if last_brace > 0:
                                        fixed_json = fixed_json[:last_brace+1]
                                    
                                    # Try to fix common formatting issues
                                    # Replace single quotes with double quotes more carefully
                                    fixed_json = re.sub(r'([{,])\s*\'([^\']+)\'\s*:', r'\1"\2":', fixed_json)  # Keys
                                    fixed_json = re.sub(r':\s*\'([^\']+)\'\s*([,}])', r':"\1"\2', fixed_json)  # String values
                                    
                                    # Fix unescaped quotes inside strings
                                    # This is a heuristic - we'll try to balance quotes
                                    parts = fixed_json.split('"')
                                    if len(parts) % 2 == 0:  # Unbalanced quotes
                                        # Try to fix by removing the last quote
                                        fixed_json = '"'.join(parts[:-1])
                                    
                                    parsed_result = json.loads(fixed_json)
                                    logger.info(f"🎉 AI Response Parsed Successfully (Aggressive cleaning)")
                                except json.JSONDecodeError as e:
                                    parsing_errors.append(f"Aggressive cleaning failed: {e}")
                                    logger.warning(f"⚠️ Aggressive cleaning failed: {e}")
                            
                            if parsed_result is not None:
                                # Log the complete parsed AI response for debugging
                                logger.info(f"🤖 COMPLETE PARSED AI RESPONSE: {json.dumps(parsed_result, indent=2, default=str)}")
                                return parsed_result
                            else:
                                logger.error(f"💥 All JSON parsing strategies failed:")
                                for error in parsing_errors:
                                    logger.error(f"   - {error}")
                                logger.error(f"📄 Raw JSON string: {json_str}")
                                # Log the raw response for debugging
                                logger.error(f"📄 COMPLETE RAW AI RESPONSE: {json.dumps(result_text, indent=2, default=str)}")
                                return {"error": "JSON parsing failed after multiple strategies", "raw_response": result_text, "parsing_errors": parsing_errors}
                        else:
                            logger.warning(f"⚠️ No JSON found in AI response: {result_text[:200]}...")
                            return {"error": "No JSON found in AI response", "raw_response": result_text}
                    except Exception as e:
                        logger.error(f"💥 Unexpected error during JSON parsing: {e}")
                        logger.error(f"📄 Raw response: {result_text[:500]}...")
                        # Log the complete raw response for debugging
                        logger.error(f"📄 COMPLETE RAW AI RESPONSE THAT FAILED PARSING: {json.dumps(result_text, indent=2, default=str)}")
                        return {"error": f"Unexpected error during JSON parsing: {str(e)}", "raw_response": result_text}
                else:
                    logger.warning("No content parts found in AI response")
                    return {"error": "No content parts found in AI response"}
            else:
                logger.warning("No candidates found in AI response")
                return {"error": "No candidates found in AI response"}
        else:
            logger.error(f"AI API request failed with status {response.status_code}: {response.text}")
            return {"error": f"AI API request failed with status {response.status_code}", "details": response.text}
        
    except Exception as e:
        logger.error(f"💥 AI Semester Plan Processing Error: {e}", exc_info=True)
        return {"error": str(e)}

# Holiday fetching function updated to use Google AI API