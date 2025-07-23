import json
import google.generativeai as genai
from config import settings

# ✅ Configure API Key
genai.configure(api_key=settings.API_KEY)

def get_holidays_from_ai(country: str, year: int):
    """
    Uses Gemini to fetch national/public holidays (real-time if supported).
    Deduplicates by date before returning.
    Returns a list of holiday dicts.
    """
    prompt_json = {
        "prompt_type": "national_holidays_request",
        "country": country,
        "year": year,
        "output_format": {
            "holidays": [
                {
                    "date": "YYYY-MM-DD",
                    "name": "Holiday Name",
                    "type": "Public Holiday",
                    "requires_no_classes": True,
                    "description": "Optional details about the holiday or why it's observed on this date"
                }
            ]
        }
    }

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")  # ✅ Or gemini-2.5-flash if available

        response = model.generate_content(
            json.dumps(prompt_json),
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )

        parsed = json.loads(response.text)
        holidays = parsed.get("holidays", [])

        # ✅ Deduplicate holidays by date
        unique_holidays = {}
        for h in holidays:
            date_key = h.get("date")
            if date_key and date_key not in unique_holidays:
                unique_holidays[date_key] = h  # First occurrence kept

        holidays = list(unique_holidays.values())

        print(f"✅ AI returned {len(holidays)} unique holidays for {country} in {year}.")
        return holidays

    except Exception as e:
        print(f"⚠️ AI Holiday Fetch Error: {e}")
        return []

# ✅ Manual Test
if __name__ == "__main__":
    holidays = get_holidays_from_ai("Ghana", 2025)
    print("\nFetched Holidays:")
    for h in holidays:
        print(f"- {h['date']}: {h['name']} ({'No Classes' if h.get('requires_no_classes', True) else 'Classes May Hold'})")
