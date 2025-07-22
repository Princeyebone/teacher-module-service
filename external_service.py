import json
import google.generativeai as genai
from config import settings

# ✅ Configure Gemini with API key
genai.configure(api_key=settings.API_KEY)

# ✅ Load Gemini model
holiday_model = genai.GenerativeModel("gemini-2.5-flash")

def get_holidays_from_ai(country: str, year: int):
    """
    Uses Gemini to fetch national/public holidays for a specific country & year.
    Returns a list of holiday dicts with date, name, and requires_no_classes.
    """
    prompt = f"""
You are an AI assistant tasked with fetching updated national/internationalpublic holidays.
Return ONLY holidays for **{country}** and international holidays in **{year}** in this JSON format:

{{
  "holidays": [
    {{
      "date": "YYYY-MM-DD",
      "name": "Holiday Name",
      "type": "Public Holiday",
      "requires_no_classes": true,
      "description": "Short reason for holiday"
    }}
  ]
}}

If you are unsure about a date, respond with your best knowledge based on current information.
    """

    try:
        response = holiday_model.generate_content(prompt)
        text = response.text.strip()

        # ✅ Clean triple-backtick formatting
        if text.startswith("```json"):
            text = text.removeprefix("```json").removesuffix("```").strip()
        elif text.startswith("```"):
            text = text.removeprefix("```").removesuffix("```").strip()

        holidays = json.loads(text).get("holidays", [])
        print(f"✅ AI returned {len(holidays)} holidays for {country} {year}.")
        return holidays

    except Exception as e:
        print(f"⚠️ AI Holiday Fetch Error: {e}")
        return []
