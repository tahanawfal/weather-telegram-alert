import os
import requests
from datetime import datetime, timezone, timedelta


# =============================
# Configuration
# =============================

OWM_API_KEY = os.environ["OWM_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

LATITUDE = 36.1911
LONGITUDE = 44.0092


# =============================
# Get weather forecast
# =============================

owm_endpoint = "https://api.openweathermap.org/data/2.5/forecast"

parameters = {
    "lat": LATITUDE,
    "lon": LONGITUDE,
    "appid": OWM_API_KEY,
    "units": "metric",
    "cnt": 8
}

response = requests.get(
    url=owm_endpoint,
    params=parameters,
    timeout=30
)

response.raise_for_status()

data = response.json()


# =============================
# Current time UTC+3
# =============================

utc_plus_3 = timezone(timedelta(hours=3))

now = datetime.now(utc_plus_3)

today = now.strftime("%A, %d %B %Y")


# =============================
# Analyze forecast
# =============================

current_forecast = data["list"][0]

temperature = current_forecast["main"]["temp"]
feels_like = current_forecast["main"]["feels_like"]

weather_description = (
    current_forecast["weather"][0]["description"].capitalize()
)

humidity = current_forecast["main"]["humidity"]


will_rain = False
rain_times = []


for forecast in data["list"]:

    weather_code = forecast["weather"][0]["id"]

    if 200 <= weather_code < 600:

        will_rain = True

        forecast_time = datetime.fromtimestamp(
            forecast["dt"],
            tz=timezone.utc
        ).astimezone(utc_plus_3)

        rain_times.append(
            forecast_time.strftime("%H:%M")
        )


# =============================
# Create Telegram message
# =============================

if will_rain:

    rain_text = (
        "🌧️ Rain is expected.\n"
        f"Possible times: {', '.join(rain_times)}"
    )

else:

    rain_text = "☀️ No rain is expected."


message = f"""🌤️ Daily Weather Report

📅 {today}

🌡️ Temperature: {temperature:.1f}°C
🤗 Feels like: {feels_like:.1f}°C
💧 Humidity: {humidity}%
🌤️ Condition: {weather_description}

{rain_text}
"""


# =============================
# Send Telegram message
# =============================

telegram_endpoint = (
    f"https://api.telegram.org/bot"
    f"{TELEGRAM_BOT_TOKEN}/sendMessage"
)

telegram_parameters = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": message
}

telegram_response = requests.get(
    url=telegram_endpoint,
    params=telegram_parameters,
    timeout=30
)

telegram_response.raise_for_status()

print("Weather report sent successfully.")
