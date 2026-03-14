from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import json
import re

# Global variables so state persists between calls
llm = None
fashion_data = ""
conversation_history = []  # stores tuples (q, a)

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


def init_bot():
    global llm, fashion_data

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.8
    )

    with open('demo.txt', 'r', encoding='utf-8') as file:
        fashion_data = file.read()


def build_clothing_item(item_description: str) -> dict:
    """
    Returns a structured dict for a single clothing item with:
        name, type, color, style
    """
    return {
        "name":  item_description if item_description else None,
        "type":  None,
        "color": None,
        "style": None,
    }


def extract_outfit_suggestions(answer: str) -> list:
    """
    Calls the LLM a second time to extract structured outfit suggestions
    from the fashion advice answer.

    Each clothing piece (top, bottom, shoes, accessory) is broken into:
        - name  : the user-given name of the item, or null if none
        - type  : category (e.g. shirt, jeans, sneakers, watch)
        - color : color of the item (e.g. red, black, white)
        - style : style detail (e.g. full-sleeve, slim-fit, ankle-length, null if unclear)

    Returns a list of up to 3 outfit dicts.
    """
    extraction_prompt = f"""You are a fashion data extractor.

Below is a fashion advice response that contains outfit suggestions.
Extract up to 3 outfit suggestions and return them as a JSON array.

Each outfit object must follow EXACTLY this structure:

{{
  "outfit_number": 1,
  "occasion": "Casual",
  "top": {{
    "name": "user-given name of the item, or null if not mentioned",
    "type": "type of clothing e.g. shirt / t-shirt / kurta / blouse / jacket",
    "color": "color of the item e.g. red / black / navy blue",
    "style": "style detail e.g. full-sleeve / half-sleeve / sleeveless / oversized / crop / null if unclear"
  }},
  "bottom": {{
    "name": "user-given name or null",
    "type": "type e.g. jeans / trousers / skirt / shorts / leggings",
    "color": "color",
    "style": "style e.g. slim-fit / straight-fit / flared / high-waist / null if unclear"
  }},
  "shoes": {{
    "name": "user-given name or null",
    "type": "type e.g. sneakers / loafers / heels / sandals / boots",
    "color": "color",
    "style": "style e.g. lace-up / slip-on / ankle-length / chunky / null if unclear"
  }},
  "accessory": {{
    "name": "user-given name or null",
    "type": "type e.g. watch / belt / cap / bag / null if none",
    "color": "color or null if none",
    "style": "style detail or null if none"
  }}
}}

Rules:
- Extract ONLY items that are actually mentioned in the fashion advice below.
- Use ONLY item names that exist in the Fashion Collection Data.
- "name" should be the user-given label for that item if one was mentioned, otherwise null.
- If no accessory is mentioned, set all accessory fields to null.
- If fewer than 3 outfits are suggested in the advice, return only those.
- Return ONLY the raw JSON array. No explanation, no markdown, no backticks.

Fashion Advice to Extract From:
{answer}

JSON Array:"""

    response = llm.invoke(extraction_prompt)
    raw = response.content.strip()

    # Strip accidental markdown code fences
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    try:
        suggestions = json.loads(raw)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []
    except json.JSONDecodeError:
        return []


def ask_bot(
    question: str,
    location: str = None,
    date: str = None,
    weather: str = None
) -> dict:
    """
    Returns a dict with two keys:
        - answer             : full styled fashion advice string
        - outfit_suggestions : list of up to 3 structured outfit dicts (empty list if not applicable)

    Args:
        question : The user's fashion question.
        location : User's current location (e.g. "Mumbai, India").
        date     : Current date string (e.g. "2025-07-15, Tuesday").
        weather  : Current weather description (e.g. "32°C, humid, partly cloudy").
    """
    global conversation_history, llm, fashion_data

    if llm is None:
        init_bot()

    # Build limited history string (last 5 messages)
    history_str = ""
    if conversation_history:
        hist = conversation_history[-5:]
        numbered = [
            f"Q{i+1}: {q}\nA{i+1}: {a}"
            for i, (q, a) in enumerate(hist)
        ]
        history_str = "\n\nPrevious Conversation:\n" + "\n\n".join(numbered)

    # Build context block
    context_parts = []
    if location:
        context_parts.append(f"📍 Location : {location}")
    if date:
        context_parts.append(f"📅 Date     : {date}")
    if weather:
        context_parts.append(f"🌤️  Weather  : {weather}")

    context_str = ""
    if context_parts:
        context_str = "\n\nUser Context:\n" + "\n".join(context_parts)

    prompt = f"""You are an expert fashion stylist and consultant. Answer using ONLY the provided fashion collection data.
{history_str}
{context_str}

Fashion Collection Data:
{fashion_data}

Question: {question}

Instructions:
- Provide stylish, clear outfit suggestions.
- Use line breaks between different outfit ideas for better readability.
- Add relevant fashion emojis (👗👔✨💫🎨👠).
- IMPORTANT — Outfit suggestions rule:
    * Whenever the user asks for outfit suggestions, style advice, "what to wear", or anything
      that involves recommending outfits, you MUST suggest EXACTLY 3 complete outfits.
    * Each outfit must include a top, bottom, shoes, and optionally an accessory.
    * Exception: if the wardrobe data genuinely does not have enough distinct items to build
      3 different outfits for the request (e.g. user only owns 2 red t-shirts), then suggest
      as many as the data allows and briefly explain why you could not reach 3.
- If the user asks "What should I wear", use the weather, date, and location context above
  to suggest weather-appropriate outfits and flag any special occasions.
- Mention the occasion each outfit suits (casual, formal, party, etc.).
- Describe colors, patterns, and styling tips.
- End with a confidence-boosting statement about the looks.
- Use trendy but simple language.
- If asked anything outside of fashion/clothing, reply with exactly:
  "I don't know about this sorry" — single line, nothing else.

Your Fashion Advice:"""

    response = llm.invoke(prompt)
    answer = response.content.strip()

    # Update memory
    conversation_history.append((question, answer))
    if len(conversation_history) > 5:
        conversation_history.pop(0)

    # Extract structured outfit suggestions from the answer
    outfit_suggestions = extract_outfit_suggestions(answer)

    return {
        "answer": answer,
        "outfit_suggestions": outfit_suggestions,
    }