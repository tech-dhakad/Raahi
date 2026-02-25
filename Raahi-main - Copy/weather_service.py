"""
Weather Service Module with Green/Sustainability Features
Provides weather data, air quality, and environmental alerts for Bhopal
"""

import os
import requests
import json
from datetime import datetime
from typing import Dict, Optional

# OpenWeatherMap API (free tier available)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

# Air Quality API (OpenWeatherMap also provides this)
AIR_QUALITY_BASE_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

# Bhopal coordinates
BHOPAL_LAT = 23.2599
BHOPAL_LNG = 77.4126

def get_weather_data(lat: float = BHOPAL_LAT, lng: float = BHOPAL_LNG, use_api: bool = True) -> Dict:
    """
    Get current weather data for a location.
    Falls back to mock data if API key is not available.
    """
    if use_api and OPENWEATHER_API_KEY:
        try:
            url = f"{OPENWEATHER_BASE_URL}/weather"
            params = {
                "lat": lat,
                "lon": lng,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"  # Celsius
            }
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return format_weather_data(data)
        except Exception as e:
            print(f"Weather API error: {e}")
    
    # Fallback to mock data for Bhopal
    return get_mock_weather_data()

def get_air_quality(lat: float = BHOPAL_LAT, lng: float = BHOPAL_LNG, use_api: bool = True) -> Dict:
    """
    Get air quality index (AQI) for a location.
    """
    if use_api and OPENWEATHER_API_KEY:
        try:
            url = f"{AIR_QUALITY_BASE_URL}"
            params = {
                "lat": lat,
                "lon": lng,
                "appid": OPENWEATHER_API_KEY
            }
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return format_air_quality_data(data)
        except Exception as e:
            print(f"Air Quality API error: {e}")
    
    # Fallback to mock data
    return get_mock_air_quality()

def format_weather_data(data: Dict) -> Dict:
    """Format OpenWeatherMap API response"""
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})
    
    return {
        "temperature": round(main.get("temp", 0)),
        "feels_like": round(main.get("feels_like", 0)),
        "humidity": main.get("humidity", 0),
        "pressure": main.get("pressure", 0),
        "description": weather.get("description", "").title(),
        "icon": weather.get("icon", "01d"),
        "wind_speed": round(wind.get("speed", 0) * 3.6, 1),  # Convert m/s to km/h
        "wind_direction": wind.get("deg", 0),
        "visibility": data.get("visibility", 0) / 1000,  # Convert to km
        "clouds": data.get("clouds", {}).get("all", 0),
        "sunrise": data.get("sys", {}).get("sunrise", 0),
        "sunset": data.get("sys", {}).get("sunset", 0),
        "location": data.get("name", "Bhopal"),
        "timestamp": datetime.now().isoformat()
    }

def format_air_quality_data(data: Dict) -> Dict:
    """Format air quality API response"""
    aqi_data = data.get("list", [{}])[0]
    main = aqi_data.get("main", {})
    components = aqi_data.get("components", {})
    
    aqi = main.get("aqi", 1)  # 1-5 scale
    
    # Convert to standard AQI scale (0-500)
    aqi_levels = {
        1: {"value": 50, "level": "Good", "color": "#00e400"},
        2: {"value": 100, "level": "Moderate", "color": "#ffff00"},
        3: {"value": 150, "level": "Unhealthy for Sensitive", "color": "#ff7e00"},
        4: {"value": 200, "level": "Unhealthy", "color": "#ff0000"},
        5: {"value": 300, "level": "Very Unhealthy", "color": "#8f3f97"}
    }
    
    aqi_info = aqi_levels.get(aqi, aqi_levels[1])
    
    return {
        "aqi": aqi_info["value"],
        "aqi_level": aqi_info["level"],
        "aqi_color": aqi_info["color"],
        "pm2_5": components.get("pm2_5", 0),
        "pm10": components.get("pm10", 0),
        "no2": components.get("no2", 0),
        "o3": components.get("o3", 0),
        "co": components.get("co", 0),
        "so2": components.get("so2", 0),
        "timestamp": datetime.now().isoformat()
    }

def get_mock_weather_data() -> Dict:
    """Mock weather data for Bhopal (when API is not available)"""
    return {
        "temperature": 28,
        "feels_like": 30,
        "humidity": 65,
        "pressure": 1013,
        "description": "Partly Cloudy",
        "icon": "02d",
        "wind_speed": 12,
        "wind_direction": 180,
        "visibility": 10,
        "clouds": 40,
        "location": "Bhopal",
        "timestamp": datetime.now().isoformat()
    }

def get_mock_air_quality() -> Dict:
    """Mock air quality data for Bhopal"""
    return {
        "aqi": 85,
        "aqi_level": "Moderate",
        "aqi_color": "#ffff00",
        "pm2_5": 35,
        "pm10": 55,
        "no2": 25,
        "o3": 45,
        "co": 1.2,
        "so2": 8,
        "timestamp": datetime.now().isoformat()
    }

def get_weather_alerts(weather_data: Dict, air_quality: Dict) -> list:
    """
    Generate environmental alerts based on weather and air quality.
    Green/sustainability focused alerts.
    """
    alerts = []
    
    # Air quality alerts
    if air_quality.get("aqi", 0) > 150:
        alerts.append({
            "type": "warning",
            "icon": "⚠️",
            "title": "Poor Air Quality",
            "message": f"Air Quality Index is {air_quality.get('aqi_level', 'Unhealthy')}. Consider staying indoors or using public transport.",
            "severity": "high"
        })
    elif air_quality.get("aqi", 0) > 100:
        alerts.append({
            "type": "info",
            "icon": "ℹ️",
            "title": "Moderate Air Quality",
            "message": "Air quality is moderate. Sensitive individuals should take precautions.",
            "severity": "medium"
        })
    
    # Weather-based green recommendations
    if weather_data.get("temperature", 0) > 35:
        alerts.append({
            "type": "green",
            "icon": "🌡️",
            "title": "Hot Weather Alert",
            "message": "High temperature detected. Consider using public transport or carpooling to reduce heat emissions.",
            "severity": "medium"
        })
    
    if weather_data.get("wind_speed", 0) > 20:
        alerts.append({
            "type": "green",
            "icon": "💨",
            "title": "Windy Conditions",
            "message": "Strong winds detected. Good conditions for outdoor activities and reduced air pollution.",
            "severity": "low"
        })
    
    # Visibility alerts
    if weather_data.get("visibility", 10) < 5:
        alerts.append({
            "type": "warning",
            "icon": "🌫️",
            "title": "Low Visibility",
            "message": "Reduced visibility. Drive carefully and consider alternative routes.",
            "severity": "high"
        })
    
    return alerts

def get_green_route_recommendations(weather_data: Dict, air_quality: Dict) -> list:
    """
    Get green route recommendations based on weather and air quality.
    """
    recommendations = []
    
    # Good air quality - recommend outdoor routes
    if air_quality.get("aqi", 0) < 100:
        recommendations.append({
            "type": "outdoor",
            "icon": "🌳",
            "title": "Great for Green Routes",
            "message": "Air quality is good. Consider walking or cycling through green spaces.",
            "benefit": "Reduces carbon footprint and improves health"
        })
    
    # Moderate temperature - ideal for cycling
    temp = weather_data.get("temperature", 0)
    if 20 <= temp <= 30:
        recommendations.append({
            "type": "cycling",
            "icon": "🚴",
            "title": "Perfect Cycling Weather",
            "message": f"Temperature is {temp}°C - ideal for cycling. Zero carbon emissions!",
            "benefit": "Zero carbon footprint"
        })
    
    # Rainy weather - recommend public transport
    if "rain" in weather_data.get("description", "").lower():
        recommendations.append({
            "type": "public_transport",
            "icon": "🚌",
            "title": "Use Public Transport",
            "message": "Rainy conditions. Public transport is safer and more eco-friendly.",
            "benefit": "70% less carbon than private vehicles"
        })
    
    return recommendations

def get_environmental_impact_score(weather_data: Dict, air_quality: Dict) -> Dict:
    """
    Calculate environmental impact score (0-100).
    Higher score = better environmental conditions.
    """
    score = 100
    
    # Deduct points for poor air quality
    aqi = air_quality.get("aqi", 50)
    if aqi > 150:
        score -= 30
    elif aqi > 100:
        score -= 15
    
    # Deduct points for extreme temperatures (more AC/heating needed)
    temp = weather_data.get("temperature", 25)
    if temp > 35 or temp < 10:
        score -= 10
    
    # Add points for good visibility
    visibility = weather_data.get("visibility", 10)
    if visibility > 8:
        score += 5
    
    # Add points for moderate wind (helps disperse pollution)
    wind = weather_data.get("wind_speed", 0)
    if 10 <= wind <= 20:
        score += 5
    
    return {
        "score": max(0, min(100, score)),
        "level": "Excellent" if score >= 80 else "Good" if score >= 60 else "Moderate" if score >= 40 else "Poor",
        "color": "#22c55e" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
    }








