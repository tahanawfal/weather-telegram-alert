from datetime import datetime
import os
import requests

owm_endpoint = "https://api.openweathermap.org/data/2.5/forecast"
api_key = os.environ.get("OWM_API_KEY")
account_sid = os.environ.get("ACCOUNT_SID")
auth_token = os.environ.get("AUTH_TOKEN")

parameters = {
    "lat": 14.073080,
    "lon": 98.193672,
    "appid": api_key,
    "cnt": 4
}

response = requests.get(url=owm_endpoint, params=parameters)
response.raise_for_status()

data = response.json()

will_rain = False

for hour_data in data["list"]:
    weather_code = hour_data["weather"][0]["id"]
    if int(weather_code) < 700:
        will_rain = True

if will_rain:
    print("Bring an umbrella")
