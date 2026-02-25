# Raahi – Green India Mobility, Safety & Civic Companion

Raahi is a **green mobility and civic safety companion for everyone** – daily commuters, residents, students and visitors – with a strong focus on a **clean, safe and sustainable India**.  
The current implementation is centered around **Bhopal** (green routing, local green spaces etc.), but the vision is to **scale to cities across India**.

Built with **Flask**, **Flask‑SocketIO** and an optional **Pathway** streaming layer, Raahi combines:
- eco‑friendly navigation,
- live safety (SOS) support,
- complaint & governance tools,
- weather, air‑quality and crowd insights.

---

## Features

### 🌱 Green & Sustainable Mobility (Green India Focus)
- **Carbon footprint calculation**: Real‑time CO₂ emission estimates per route (car vs public transport, walking, cycling, EV, etc.).
- **Eco‑friendly route analysis**: Routes get an **eco‑score (0–100)** based on distance, emissions and proximity to green spaces.
- **Green spaces integration (Bhopal for now)**: Lakes, parks and other eco‑friendly areas are integrated into the routing logic.
- **Public transport recommendations**: Suggests lower‑carbon alternatives and highlights where PT is a better choice than private vehicles.
- **Environmental impact score**: City‑level score (0–100) based on AQI, temperature, visibility and wind, via the `weather_service.py` module.

### 🗺️ Real‑Time Map & Navigation
- **Live location sharing**: Real‑time tracking of active users on an interactive map (`/realtime`).
- **Multiple route characteristics** (UI‑dependent): Fastest, shortest and green‑focused options (backend ready via `green_routing.py`).
- **Interactive OpenStreetMap map**: Built with **Leaflet.js** and **OSRM** for routing.
- **City‑aware logic**: Pre‑configured points of interest and green spaces for Bhopal, with a design that can be extended to other cities.

### 🚨 Safety & SOS for Everyone
- **SOS emergency system (`/sos`)**: One‑tap SOS sends:
  - live location updates,
  - an **emergency email** to a configured relative/authority,
  - a list of nearby **police stations, hospitals and green safe zones**.
- **Green safe zones in emergencies**: Nearby lakes/parks/green spaces are surfaced as additional safe areas during SOS.
- **Automatic SOS resolution audit**: Tracks duration, path taken and estimates carbon footprint of the emergency response.

### 🧾 Civic Complaints & Governance (Not Just Tourists)
- **Complaint reporting (`/fraude`)**: Any citizen can file issues such as:
  - fraud/scam,
  - public cleanliness,
  - environment issues,
  - infrastructure and safety concerns.
- **AI‑assisted complaint drafting** (via Gemini, optional): Generates a formal email draft to be sent to authorities.
- **Email dispatch with attachments**: Sends complaint details and supporting media to a configured recipient mailbox.
- **Feedback & rating**: Simple rating endpoint for complaint resolution experience (`/api/complaint_rating/<cid>`).

### 🌤️ Weather, Air Quality & Crowd Intelligence
- **Weather and AQI (`/api/weather`)**:
  - current weather data (temp, humidity, wind, visibility),
  - **AQI with health labels and color codes**,
  - environment‑aware **green route recommendations** (walk, cycle, PT).
- **Crowded / unsafe area alerts (`/api/pathway/alerts`)**:
  - Python fallback aggregates recent user locations,
  - identifies crowded or high‑AQI areas (e.g. Upper Lake, Van Vihar, MP Nagar),
  - suggests avoiding hotspots and preferring greener, less crowded options.

---

## Tech Stack

- **Backend**: Flask, Flask‑SocketIO
- **Real‑time / Streaming (optional)**: Pathway (`green_routing.py`, `path_pipeline.py`)
- **Frontend**: HTML, CSS, JavaScript, Leaflet.js, OpenStreetMap
- **Routing**: OSRM (Open Source Routing Machine)
- **Email & Notifications**: SMTP (Gmail / other), SOS & complaint workflows
- **AI (optional)**: Google Gemini (`google-generativeai`) for complaint drafting and suggestions
- **Weather & AQI**: OpenWeatherMap APIs (with graceful mock fallback)

---

## Getting Started

### Prerequisites
- Python 3.9+ (recommended)
- `pip` for dependency management
- (Optional but recommended) a virtual environment

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/raahi.git
   cd raahi
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file in the project root**
   ```env
   # Flask / security
   SECRET_KEY=your-secret-key

   # Email / SMTP (for SOS + complaints)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=your-app-password-or-smtp-password
   RECIPIENT=recipient-email@gmail.com        # Where SOS + complaints are sent
   FROM_EMAIL=your-email@gmail.com            # Optional, defaults to SMTP_USER

   # AI (optional, for smarter complaint drafts & tips)
   GEMINI_API_KEY=your-gemini-api-key

   # Weather & AQI (optional – falls back to mock data if absent)
   OPENWEATHER_API_KEY=your-openweather-api-key
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   - Navigate to `http://localhost:5000`
   - Key pages:
     - `/` – Home
     - `/realtime` – Real‑time map & presence
     - `/sos` – SOS emergency screen
     - `/fraude` – Complaint reporting
     - `/weather` – Weather & environment dashboard

---

## Key Modules

- **`app.py`**
  - Main Flask app and Socket.IO server.
  - Routes for pages (`/`, `/realtime`, `/sos`, `/fraude`, `/weather`).
  - APIs for green routing, weather, complaints, SOS and crowd alerts.

- **`green_routing.py`**
  - Green routing logic and eco‑score system.
  - Carbon footprint calculations for different vehicle types.
  - Green spaces database for Bhopal and “nearby green space” finder.
  - Optional Pathway‑based route processing (with Python fallback).

- **`path_pipeline.py`**
  - Conceptual Pathway streaming pipeline for live tourist/citizen movement.
  - Python fallback implements in‑memory sliding‑window aggregation to detect crowded / polluted areas.

- **`weather_service.py`**
  - Weather and AQI integration (OpenWeatherMap + mock fallback).
  - Environmental alerts, green route recommendations and impact scores.

---

## API Overview

- **Green routing**
  - `POST /api/green_route_analysis` – Analyze a route for eco‑friendliness.
  - `GET /api/green_spaces` – Get nearby green spaces for a given lat/lng.

- **Weather & environment**
  - `GET /api/weather` – Weather, AQI, alerts, green recommendations and environmental score.
  - `GET /api/pathway/alerts` – Crowd + pollution based area alerts (Python/Pathway).

- **Safety & complaints**
  - `GET /sos` – SOS page (Socket.IO‑driven).
  - `POST /api/report_issue` – Submit a civic/fraud/environment complaint.
  - `GET /complaint_view/<cid>` – View a specific complaint + AI draft.
  - `POST /api/complaint_rating/<cid>` – Rate complaint resolution.

---

## Vision – From Bhopal to a Green India 🇮🇳

Raahi started as a **Hack for Green Bharat** project with a focus on **sustainable transportation and environmental awareness in Bhopal**.  
The broader goal is to evolve into a **pan‑India platform** that:
- nudges citizens towards **low‑carbon mobility** (walk, cycle, PT, EV),
- makes **civic complaints and safety** simple, transparent and data‑driven,
- uses **real‑time data, weather and AI** to keep people informed and safe,
- promotes **Green India: cleaner air, safer streets and smarter cities**.

Contributions, city‑specific datasets and feature ideas for other Indian cities are very welcome.

---

## License

This project is licensed under the **MIT License**.

---

## Credits & Contributors

- Built originally for the **Hack for Green Bharat** initiative.
- Extended as a **citizen‑first Green India companion**, not limited to tourists.


