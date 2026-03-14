---
title: Fashion Stylist Chatbot
emoji: 👗
colorFrom: pink
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# Fashion Stylist Chatbot API 👗✨

A personalized AI fashion stylist powered by Google Gemini.

## Endpoints

| Method | Endpoint  | Description                        |
|--------|-----------|------------------------------------|
| GET    | `/`       | Welcome message & endpoint listing |
| GET    | `/health` | Health check                       |
| POST   | `/ask`    | Get fashion advice + outfit JSON   |

## Request Format

```json
POST /ask
{
  "question": "What should I wear today?",
  "location": "Chennai, India"
}
```

## Response Format

```json
{
  "question": "What should I wear today?",
  "answer": "Here are 3 outfits perfect for the weather... 👗✨",
  "outfit_suggestions": [
    {
      "outfit_number": 1,
      "occasion": "Casual",
      "top":    { "name": null, "type": "t-shirt",  "color": "white", "style": "half-sleeve" },
      "bottom": { "name": null, "type": "jeans",    "color": "black", "style": "slim-fit"    },
      "shoes":  { "name": null, "type": "sneakers", "color": "white", "style": "lace-up"     },
      "accessory": { "name": null, "type": null, "color": null, "style": null }
    }
  ],
  "context": {
    "location": "Chennai, India",
    "date": "2026-03-14, Saturday",
    "weather": "34°C (feels like 36°C), Sunny, 78% humidity"
  }
}
```

## Environment Variables

Set this secret in your Hugging Face Space settings:

| Variable         | Description                  |
|------------------|------------------------------|
| `GOOGLE_API_KEY` | Your Google Gemini API key   |
