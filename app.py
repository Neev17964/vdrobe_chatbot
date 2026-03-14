from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import httpx
import logging

from chatbot import ask_bot, init_bot

# -----------------------------------------------------
# 🚀 FastAPI App Initialization
# -----------------------------------------------------
app = FastAPI(
    title="Fashion Stylist Chatbot API",
    description="Get personalized fashion advice and outfit suggestions",
    version="1.0.0",
)

# -----------------------------------------------------
# 🌐 CORS
# -----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
# 🛠 Logger
# -----------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fashion-api")


# -----------------------------------------------------
# 🌤️  Weather Helper
# -----------------------------------------------------
async def fetch_weather(location: str) -> dict:
    url = f"https://wttr.in/{location}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        current = data["current_condition"][0]
        return {
            "temp_c":       int(current["temp_C"]),
            "feels_like_c": int(current["FeelsLikeC"]),
            "description":  current["weatherDesc"][0]["value"],
            "humidity":     int(current["humidity"]),
        }
    except Exception as e:
        logger.warning(f"⚠️  Could not fetch weather for '{location}': {e}")
        return {"temp_c": None, "feels_like_c": None, "description": None, "humidity": None}


def build_weather_string(weather: dict) -> Optional[str]:
    if weather["temp_c"] is None:
        return None
    parts = [f"{weather['temp_c']}°C (feels like {weather['feels_like_c']}°C)"]
    if weather["description"]:
        parts.append(weather["description"])
    if weather["humidity"] is not None:
        parts.append(f"{weather['humidity']}% humidity")
    return ", ".join(parts)


def get_current_date_string() -> str:
    return datetime.now().strftime("%Y-%m-%d, %A")


# -----------------------------------------------------
# 🟢 Request Model
# -----------------------------------------------------
class Query(BaseModel):
    question: str
    location: Optional[str] = None


# -----------------------------------------------------
# 🚦 Startup
# -----------------------------------------------------
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("🔄 Initializing Fashion Stylist bot...")
        init_bot()
        logger.info("✅ Fashion bot ready!")
    except Exception as e:
        logger.exception("❌ Failed to initialize bot")


# -----------------------------------------------------
# 🏠 Root
# -----------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Fashion Stylist Chatbot API 👗✨",
        "endpoints": {
            "/ask":    "POST — get fashion advice and outfit suggestions",
            "/health": "GET  — health check",
        }
    }


# -----------------------------------------------------
# ❤️  Health Check
# -----------------------------------------------------
@app.get("/health")
async def health():
    return {"service": "fashion-stylist-bot", "status": "OK", "version": "1.0.0"}


# -----------------------------------------------------
# ❓ Ask Fashion Question
# -----------------------------------------------------
@app.post("/ask")
async def ask_api(payload: Query):
    try:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Auto-resolve date
        date_str = get_current_date_string()

        # Auto-resolve weather
        weather_str = None
        if payload.location:
            weather_data = await fetch_weather(payload.location)
            weather_str  = build_weather_string(weather_data)

        logger.info(f"👗 Question : {question}")
        logger.info(f"📍 Location : {payload.location!r}")
        logger.info(f"📅 Date     : {date_str}")
        logger.info(f"🌤️  Weather  : {weather_str!r}")

        result = ask_bot(
            question=question,
            location=payload.location,
            date=date_str,
            weather=weather_str,
        )

        return {
            "question":          question,
            "answer":            result["answer"],
            "outfit_suggestions": result["outfit_suggestions"],
            "context": {
                "location": payload.location,
                "date":     date_str,
                "weather":  weather_str,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing request")
        raise HTTPException(status_code=500, detail=str(e))