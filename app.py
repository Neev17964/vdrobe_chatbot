from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from langsmith import traceable, trace
import httpx
import logging
import asyncio
import re

from chatbot import ask_bot, init_bot

# -----------------------------------------------------
# 🚀 App
# -----------------------------------------------------
app = FastAPI(
    title="Fashion Stylist Chatbot API",
    description="Get personalized fashion advice and outfit suggestions",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fashion-api")


# -----------------------------------------------------
# 🌤️ Weather Helper
# -----------------------------------------------------
@traceable(name="fetch_weather", run_type="tool")
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
        logger.warning(f"⚠️ Could not fetch weather for '{location}': {e}")
        return {"temp_c": None, "feels_like_c": None, "description": None, "humidity": None}


def build_weather_string(weather: dict) -> Optional[str]:
    if weather["temp_c"] is None:
        return None
    parts = [f"{weather['temp_c']}°C"]
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
# 🏠 Root & Health
# -----------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Fashion Stylist Chatbot API 👗✨",
        "endpoints": {"/ask": "POST", "/health": "GET"},
    }

@app.get("/health")
async def health():
    return {"service": "fashion-stylist-bot", "status": "OK", "version": "2.0.0"}


# -----------------------------------------------------
# ❓ Ask Endpoint
# -----------------------------------------------------
@app.post("/ask")
async def ask_api(payload: Query):
    try:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        with trace(
            name="ask_api_endpoint",
            run_type="chain",
            inputs={"question": question, "location": payload.location},
        ) as root_run:

            date_str    = get_current_date_string()
            weather_str = None

            if payload.location:
                weather_data = await fetch_weather(payload.location)
                weather_str  = build_weather_string(weather_data)

            logger.info(f"👗 Question : {question}")
            logger.info(f"📍 Location : {payload.location!r}")
            logger.info(f"🌤️  Weather  : {weather_str!r}")

            result = await asyncio.to_thread(
                ask_bot,
                question=question,
                location=payload.location,
                date_str=date_str,
                weather=weather_str,
            )

            response = {
                "question":           question,
                "answer":             result["answer"],
                "outfit_suggestions": result["outfit_suggestions"],
                "cached":             result.get("cached", False),
                "context": {
                    "location": payload.location,
                    "date":     date_str,
                    "weather":  weather_str,
                },
            }

            root_run.end(outputs=response)
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing request")
        raise HTTPException(status_code=500, detail=str(e))
