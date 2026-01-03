# from groq import Groq

# client = Groq(api_key="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")
# completion = client.chat.completions.create(
#   model="openai/gpt-oss-20b",
#    messages=[
#     {
#        "role": "user",
#        "content": "what number did i send you"
#        
#      }
#    ],
#    temperature=1,
#    max_completion_tokens=8192,
#    top_p=1,
#    reasoning_effort="medium",
#    stream=True,
#   stop=None
#)

# for chunk in completion:
#    print(chunk.choices[0].delta.content or "", end="")


from groq import Groq
import json
import re
from config import settings

client = Groq(api_key=settings.API_KEY)  # add your API key here

prompt_json = {
    "task": "Fetch national holidays",
    "country": "Ghana",
    "year": 2025,
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

# 🔎 Extract the JSON object from the noisy response
match = re.search(r"\{[\s\S]*\}", response_text)
if match:
    json_str = match.group(0)
    try:
        holidays = json.loads(json_str)
        print(json.dumps(holidays, indent=2))
    except json.JSONDecodeError:
        print("⚠️ Extracted JSON but failed to parse. Raw JSON string:")
        print(json_str)
else:
    print("⚠️ No JSON found in model response. Full output:")
    print(response_text)
