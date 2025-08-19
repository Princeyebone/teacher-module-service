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



from groq import Groq
import json

async def fetch_number_from_ai(country: str, year: int):
    """
    Fetch national holidays for a given country/year from AI using Groq's chat completions.
    Returns the content of the AI response.
    """
    country="Ghana"
    year="2023"

    # Build the structured prompt
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

    client = Groq(api_key="")  # Insert your actual API key here

    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",  # keep role "user" so model knows it's the actual prompt
                "content": json.dumps(prompt_json, indent=2)
            }
        ],
        temperature=1,
        max_completion_tokens=8192,
        top_p=1,
        reasoning_effort="medium",
        stream=True,
        stop=None
    )

    # Streaming response
    for chunk in completion:
        print(chunk.choices[0].delta.content or "", end="")











