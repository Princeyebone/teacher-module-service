import json
from datetime import datetime
import re
from groq import Groq
from config import settings

def get_holidays_from_ai(country: str, year: int):
    """
    Fetch up-to-date national/public holidays using Groq API with browser search tool.
    Returns a list of holiday dicts in the format:
    [
        {
            "date": "YYYY-MM-DD",
            "name": "Holiday Name",
            "type": "Public Holiday",
            "requires_no_classes": True,
            "description": "Why the holiday is observed"
        }
    ]
    """
    try:
        # ✅ Configure Groq client
        client = Groq(api_key=settings.API_KEY)
        
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
            "instruction": "Return ONLY a valid JSON object. Do not include markdown, text, or sources."
        }
        
        # ✅ Generate AI Response with browser search
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": json.dumps(prompt_json, indent=2)}
            ],
            model="openai/gpt-oss-120b",
            temperature=0,
            max_completion_tokens=2048,
            top_p=1,
            stream=False,
            stop=None,
            tool_choice="required",
            tools=[{"type": "browser_search"}]
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        
        # ✅ Extract JSON from response
        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            json_str = match.group(0)
            try:
                parsed_response = json.loads(json_str)
                holidays = parsed_response.get("holidays", [])
                
                # ✅ Log success
                print(f"✅ AI (Groq Browser Search) returned {len(holidays)} holidays for {country} in {year}.")
                
                return holidays
                
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parsing error: {e}")
                print(f"Raw JSON string: {json_str}")
                return []
        else:
            print("⚠️ No JSON found in AI response")
            print(f"Full response: {response_text}")
            return []
            
    except Exception as e:
        print(f"⚠️ AI Holiday Fetch Error (Groq): {e}")
        return []



# Holiday fetching function updated to use Groq API from ai.py











