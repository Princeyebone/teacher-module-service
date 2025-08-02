import json
from datetime import datetime
import google.generativeai as genai
from google.generativeai import protos
from config import settings

# ✅ Configure API Key securely (from .env)
genai.configure(api_key=settings.API_KEY)

def get_holidays_from_ai(country: str, year: int):
    """
    Fetch up-to-date national/public holidays using Gemini 1.5 Flash with Google Search tool.
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
                    "description": "Optional details about the holiday"
                }
            ]
        }
    }

    try:
        # ✅ Enable Google Search Tool
        google_search_tool = protos.Tool(
            google_search_retrieval=protos.GoogleSearchRetrieval()
        )

        # ✅ Load Gemini model with tool enabled
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            tools=[google_search_tool]
        )

        # ✅ Generate AI Response
        response = model.generate_content(
            json.dumps(prompt_json),
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )

        # ✅ Parse Response Safely
        parsed = json.loads(response.text)
        holidays = parsed.get("holidays", [])

        # ✅ Log (for debugging only)
        print(f"✅ AI (Google Search) returned {len(holidays)} holidays for {country} in {year}.")

        # ✅ Optionally inspect sources (to verify real-time info)
        if response.candidates and hasattr(response.candidates[0], "grounding_metadata"):
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, "grounding_attributions") and metadata.grounding_attributions:
                print("🔗 Sources used by AI:")
                for attribution in metadata.grounding_attributions:
                    if hasattr(attribution, "web") and hasattr(attribution.web, "uri"):
                        title = getattr(attribution.web, "title", "N/A")
                        print(f"  - {title}: {attribution.web.uri}")

        return holidays

    except Exception as e:
        print(f"⚠️ AI Holiday Fetch Error: {e}")
        return []
