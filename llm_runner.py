import os
import together
from dotenv import load_dotenv

# Load .env file if available
load_dotenv()

# Get API key from environment
together.api_key = TOGETHER_API_KEY
if not TOGETHER_API_KEY:
    raise ValueError("TOGETHER_API_KEY not found in environment variables.")

# Initialize Together client
client = Together(api_key=TOGETHER_API_KEY)

# Model to use (you can change this)
MODEL_NAME = "meta-llama/Llama-3.2-3B-Instruct-Turbo"

def generate_summary(prompt: str) -> str:
    try:
        response = together.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a disaster risk analyst generating detailed, markdown-formatted flood reports "
                        "based on environmental risk scores and urban flood metrics. Your summaries must be data-aware, "
                        "well-structured, and reflect analytical reasoning from flood indicators like rainfall, elevation, "
                        "drainage, and humidity. Format clearly for export as a PDF."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ TogetherAI error: {str(e)}"
