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
                "maxOutputTokens": 2048,
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
        
        # Prepare the request for Google Vertex AI API (Gemini) - Use generateContent instead of streamGenerateContent
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY}"
        logger.info(f"🔗 Sending request to AI API")
        
        # Create the request payload
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
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }
        
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
            
            # Log the full response for debugging (first 1000 chars)
            logger.info(f"📋 AI Response (first 1000 chars): {str(response_data)[:1000]}...")
            
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
        
        # Prepare the request for Google Vertex AI API (Gemini) - Use generateContent instead of streamGenerateContent
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite:generateContent?key={settings.API_KEY}"
        logger.info(f"🔗 Sending request to AI API")
        
        # Create the request payload
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
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }
        
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
            
            # Log the full response for debugging (first 1000 chars)
            logger.info(f"📋 AI Response (first 1000 chars): {str(response_data)[:1000]}...")
            
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


# Holiday fetching function updated to use Google AI API