import os
import sys
from datetime import datetime, timezone

import requests

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
AIR_POLLUTION_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
TELEGRAM_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

# AQI scale used by OpenWeatherMap's air_pollution endpoint: 1 (Good) to 5 (Very Poor)
AQI_LABELS = {
    1: ("Good", "🟢"),
    2: ("Fair", "🟡"),
    3: ("Moderate", "🟠"),
    4: ("Poor", "🔴"),
    5: ("Very Poor", "🟣"),
}


def get_env_var(name: str, required: bool = True, default: str | None = None) -> str:
    """Read an environment variable, raising a clear error if it's missing."""
    value = os.environ.get(name, default)
    if required and not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


def fetch_forecast(api_key: str, city: str) -> dict:
    """Call the OpenWeatherMap forecast endpoint and return the parsed JSON."""
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",  # Celsius, since we're not in the US
    }
    response = requests.get(FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()  # raises an exception for 4xx/5xx responses
    return response.json()


def fetch_air_quality(api_key: str, lat: float, lon: float) -> dict | None:
    """
    Call the OpenWeatherMap air pollution endpoint and return the parsed JSON.
    Returns None on failure instead of crashing the whole script, since air
    quality is a "nice to have" addition, not the core of the message.
    """
    params = {"lat": lat, "lon": lon, "appid": api_key}
    try:
        response = requests.get(AIR_POLLUTION_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Warning: could not fetch air quality data: {e}", file=sys.stderr)
        return None


def filter_todays_entries(forecast_data: dict) -> list[dict]:
    """
    The API returns forecasts in 3-hour steps for the next 5 days.
    We only want the entries that fall on today's date (UTC).
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todays_entries = [
        entry for entry in forecast_data.get("list", [])
        if entry["dt_txt"].startswith(today_str)
    ]
    return todays_entries


def weather_emoji(description: str) -> str:
    """Pick a rough emoji to match the weather description."""
    description = description.lower()
    if "thunder" in description:
        return "⛈️"
    if "snow" in description:
        return "❄️"
    if "rain" in description or "drizzle" in description:
        return "🌧️"
    if "cloud" in description:
        return "☁️"
    if "clear" in description:
        return "☀️"
    if "mist" in description or "fog" in description or "haze" in description:
        return "🌫️"
    return "🌡️"


def build_advice(entries: list[dict], aqi: int | None) -> list[str]:
    """
    Look at today's numbers and turn them into plain, practical suggestions
    — the kind of thing you'd actually want to know before leaving the house.
    """
    advice = []

    temps = [entry["main"]["temp"] for entry in entries]
    max_temp = max(temps)
    min_temp = min(temps)
    max_pop = max((entry.get("pop", 0) for entry in entries), default=0)
    max_wind = max((entry["wind"]["speed"] for entry in entries), default=0)
    min_visibility = min((entry.get("visibility", 10000) for entry in entries), default=10000)

    if max_temp >= 38:
        advice.append("🥵 It's going to be brutally hot — drink plenty of water and avoid the midday sun if you can.")
    elif max_temp >= 30:
        advice.append("☀️ A hot one today — stay hydrated, especially if you're out in the afternoon.")
    elif min_temp <= 5:
        advice.append("🧥 Chilly out there — grab a jacket before you head out.")

    if max_pop >= 0.6:
        advice.append("☔ Rain is likely today — an umbrella would be a smart move.")
    elif max_pop >= 0.3:
        advice.append("🌦️ There's a decent chance of rain — keep an umbrella nearby just in case.")

    if max_wind >= 10:
        advice.append("💨 Expect strong winds — secure loose items if you're outside.")

    if min_visibility < 4000:
        advice.append("🌫️ Visibility will drop at times — take it slow if you're driving.")

    if aqi is not None:
        label, emoji = AQI_LABELS.get(aqi, ("Unknown", "⚪"))
        if aqi >= 4:
            advice.append(f"{emoji} Air quality is {label.lower()} today — consider limiting time outdoors, especially if you're sensitive to pollution.")
        elif aqi == 3:
            advice.append(f"{emoji} Air quality is {label.lower()} — fine for most people, but sensitive groups should take it easy outside.")

    if not advice:
        advice.append("👍 Nothing extreme in today's forecast — should be a comfortable day.")

    return advice


def build_message(city_label: str, entries: list[dict], aqi: int | None) -> str:
    """Turn the forecast + air quality data into a friendly Telegram message."""
    if not entries:
        return f"⚠️ No forecast data available for {city_label} today."

    today_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    lines = [f"👋 Good morning! Here's the weather for *{city_label}* — {today_str}\n"]

    temps = [entry["main"]["temp"] for entry in entries]
    lines.append(f"🌡️ High: {max(temps):.1f}°C | Low: {min(temps):.1f}°C")

    if aqi is not None:
        label, emoji = AQI_LABELS.get(aqi, ("Unknown", "⚪"))
        lines.append(f"{emoji} Air quality: {label} (AQI {aqi}/5)")

    lines.append("")  # blank line
    lines.append("📋 What to expect today:")
    for advice_line in build_advice(entries, aqi):
        lines.append(f"  {advice_line}")

    lines.append("")  # blank line
    lines.append("⏰ Hour-by-hour:")
    for entry in entries:
        time_str = entry["dt_txt"].split(" ")[1][:5]  # "HH:MM"
        temp = entry["main"]["temp"]
        feels_like = entry["main"]["feels_like"]
        description = entry["weather"][0]["description"].capitalize()
        humidity = entry["main"]["humidity"]
        wind_speed = entry["wind"]["speed"]
        visibility_km = entry.get("visibility", 10000) / 1000
        emoji = weather_emoji(description)

        lines.append(
            f"{emoji} {time_str} UTC — {description}, {temp:.1f}°C "
            f"(feels like {feels_like:.1f}°C), humidity {humidity}%, "
            f"wind {wind_speed} m/s, visibility {visibility_km:.1f} km"
        )

    return "\n".join(lines)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send a text message through the Telegram Bot API."""
    url = TELEGRAM_URL_TEMPLATE.format(token=bot_token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, data=payload, timeout=15)
    response.raise_for_status()


def main() -> None:
    try:
        api_key = get_env_var("OWM_API_KEY")
        bot_token = get_env_var("TELEGRAM_BOT_TOKEN")
        chat_id = get_env_var("TELEGRAM_CHAT_ID")
        city = get_env_var("CITY_NAME", required=False, default="Erbil,IQ")
        lat = float(get_env_var("CITY_LAT", required=False, default="36.19"))
        lon = float(get_env_var("CITY_LON", required=False, default="43.99"))

        forecast_data = fetch_forecast(api_key, city)
        todays_entries = filter_todays_entries(forecast_data)

        air_quality_data = fetch_air_quality(api_key, lat, lon)
        aqi = None
        if air_quality_data and air_quality_data.get("list"):
            aqi = air_quality_data["list"][0]["main"]["aqi"]

        message = build_message(city, todays_entries, aqi)

        send_telegram_message(bot_token, chat_id, message)
        print("Message sent successfully.")

    except requests.exceptions.RequestException as e:
        print(f"Network/API error: {e}", file=sys.stderr)
        sys.exit(1)
    except EnvironmentError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
