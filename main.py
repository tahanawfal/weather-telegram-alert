import os
import sys
from datetime import datetime, timezone

import requests

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/forecast"
TELEGRAM_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"


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
    response = requests.get(OPENWEATHER_URL, params=params, timeout=15)
    response.raise_for_status()  # raises an exception for 4xx/5xx responses
    return response.json()


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


def build_message(city_label: str, entries: list[dict]) -> str:
    """Turn the list of forecast entries into a readable Telegram message."""
    if not entries:
        return f"⚠️ No forecast data available for {city_label} today."

    today_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    lines = [f"🌤 Weather forecast for {city_label} — {today_str}\n"]

    temps = [entry["main"]["temp"] for entry in entries]
    lines.append(f"High: {max(temps):.1f}°C | Low: {min(temps):.1f}°C\n")

    for entry in entries:
        time_str = entry["dt_txt"].split(" ")[1][:5]  # "HH:MM"
        temp = entry["main"]["temp"]
        feels_like = entry["main"]["feels_like"]
        description = entry["weather"][0]["description"].capitalize()
        humidity = entry["main"]["humidity"]
        wind_speed = entry["wind"]["speed"]

        lines.append(
            f"{time_str} UTC — {description}, {temp:.1f}°C "
            f"(feels like {feels_like:.1f}°C), humidity {humidity}%, "
            f"wind {wind_speed} m/s"
        )

    return "\n".join(lines)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send a text message through the Telegram Bot API."""
    url = TELEGRAM_URL_TEMPLATE.format(token=bot_token)
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    response = requests.post(url, data=payload, timeout=15)
    response.raise_for_status()


def main() -> None:
    try:
        api_key = get_env_var("OWM_API_KEY")
        bot_token = get_env_var("TELEGRAM_BOT_TOKEN")
        chat_id = get_env_var("TELEGRAM_CHAT_ID")
        city = get_env_var("CITY_NAME", required=False, default="Erbil,IQ")

        forecast_data = fetch_forecast(api_key, city)
        todays_entries = filter_todays_entries(forecast_data)
        message = build_message(city, todays_entries)

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
