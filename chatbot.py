from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langsmith import traceable
from dotenv import load_dotenv
import os
import hashlib
import re

from outfit_extractor import extract_outfits

# Global state
llm = None
fashion_data = []
response_cache = {}
chat_history = []
session_initialized = False

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


@traceable(name="init_bot")
def init_bot():
    global llm, fashion_data

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.8
    )

    with open('demo.txt', 'r', encoding='utf-8') as f:
        fashion_data = [line.strip() for line in f if line.strip()]


# -------------------------------------------------------
# WARDROBE FILTER
# -------------------------------------------------------
def filter_items(question: str, wardrobe: list[str]) -> str:
    query_words = set(question.lower().split())
    scored = [(len(set(l.lower().split()) & query_words), l) for l in wardrobe]
    scored.sort(reverse=True)
    top = [l for s, l in scored if s > 0][:8]
    return "\n".join(top if top else wardrobe[:8])


# -------------------------------------------------------
# CONTEXT COMPRESSOR
# -------------------------------------------------------
def compress_context(location=None, date_str=None, weather=None) -> str:
    parts = []
    if location:
        parts.append(location.lower())

    if weather:
        descriptors = []
        w = weather.lower()

        for word in ["hot", "cold", "warm", "cool", "humid", "dry",
                     "sunny", "cloudy", "rainy", "windy", "foggy", "snowy"]:
            if word in w:
                descriptors.append(word)

        temp = re.search(r'(\d+)°c', w)
        if temp:
            descriptors.insert(0, f"{temp.group(1)}°C")

        if descriptors:
            parts.extend(descriptors)

    return ", ".join(parts) if parts else ""


# -------------------------------------------------------
# CACHE KEY
# -------------------------------------------------------
def make_cache_key(question: str, context: str) -> str:
    raw = f"{question.lower().strip()}|{context}"
    return hashlib.md5(raw.encode()).hexdigest()


# -------------------------------------------------------
# ASK BOT
# -------------------------------------------------------
@traceable(name="ask_bot", run_type="chain")
def ask_bot(question, location=None, date_str=None, weather=None) -> dict:
    global llm, fashion_data, response_cache, session_initialized, chat_history

    if llm is None:
        init_bot()

    context = compress_context(location, date_str, weather)
    cache_key = make_cache_key(question, context)

    if cache_key in response_cache:
        return {**response_cache[cache_key], "cached": True}

    if not session_initialized:
        full_wardrobe = "\n".join(fashion_data)  # full list, no filtering

        ctx = []
        if location: ctx.append(f"Location: {location}")
        if date_str: ctx.append(f"Date: {date_str}")
        if context:  ctx.append(f"Weather: {context}")
        context_str = ("\nContext: " + " | ".join(ctx)) if ctx else ""

        system_prompt = f"""You are a friendly AI Stylist. Be casual, short, and natural.
You have access to a wardrobe collection below. Use ONLY items from it.
Do NOT invent, assume, or modify any item name.
{context_str}

Wardrobe:
{full_wardrobe}

Rules:
- Greetings/small talk → reply naturally, no outfit suggestions.
- ANY question about outfits, clothes, colors, or specific items → outfit request.

- Outfit request → always give 3 outfits in this EXACT format (no exceptions):
  Outfit 1 - [vibe]: [top] + [bottom] + [shoes if available]. [one sentence why it works.]
  Outfit 2 - [vibe]: [top] + [bottom] + [shoes if available]. [one sentence why it works.]
  Outfit 3 - [vibe]: [top] + [bottom] + [shoes if available]. [one sentence why it works.]

- Every outfit MUST have 1 top + 1 bottom. Shoes only if present in wardrobe.
- If the user asks for a specific color/item, prioritize those. Use other items to complete the outfit.
- If only 1 matching top exists, reuse it across outfits but vary the bottom and shoes.
- NEVER say "I can't make outfits" or "not enough items" — always attempt 3 outfits.
- No bullet points, no bold, no headers. Plain text only.

- Off-topic (non-fashion): "That's outside my lane! I'm all about outfits 😄"
"""

        chat_history = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question)
        ]
        session_initialized = True

    else:
        chat_history.append(HumanMessage(content=question))

    response = llm.invoke(chat_history)
    answer = response.content.strip()
    chat_history.append(AIMessage(content=answer))

    outfit_suggestions = extract_outfits(answer)
    response_cache[cache_key] = {"answer": answer, "outfit_suggestions": outfit_suggestions}

    return {"answer": answer, "outfit_suggestions": outfit_suggestions, "cached": False}


# -------------------------------------------------------
# RESET SESSION
# -------------------------------------------------------
def reset_session():
    global chat_history, session_initialized, response_cache
    chat_history = []
    session_initialized = False
    response_cache = {}
