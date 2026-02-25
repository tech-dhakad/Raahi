"""
Pathway Streaming Pipeline (Concept) + Python Fallback
------------------------------------------------------

Goal:
- Process live tourist location events and environmental data
- Detect crowded / unsafe areas in near real-time
- Designed to use Pathway when available, with a Python fallback
"""

import time
from collections import deque, defaultdict
from typing import Dict, List, Optional

try:
    import pathway as pw  # Optional, real engine on Linux
    PATHWAY_STREAMING_AVAILABLE = True
except Exception as e:
    PATHWAY_STREAMING_AVAILABLE = False
    print(f"Pathway streaming engine not available, using Python fallback. ({e})")


# ----------------- Simple in-memory event buffer (fallback) -----------------

MAX_EVENTS = 10000          # max events in buffer
WINDOW_SECONDS = 300        # 5-minute sliding window

_EVENT_BUFFER: deque = deque()  # holds dicts: {user_id, lat, lng, ts, aqi}


def add_tourist_event(user_id: str, lat: float, lng: float, aqi: Optional[float] = None, ts: Optional[int] = None) -> None:
    """
    Called from Flask/Socket layer whenever a new location_update arrives.
    Stores recent events in a buffer for Python-based aggregation.
    """
    if ts is None:
        ts = int(time.time())

    event = {
        "user_id": str(user_id or ""),
        "lat": float(lat or 0.0),
        "lng": float(lng or 0.0),
        "ts": int(ts),
        "aqi": float(aqi) if aqi is not None else None,
    }
    _EVENT_BUFFER.append(event)

    while len(_EVENT_BUFFER) > MAX_EVENTS:
        _EVENT_BUFFER.popleft()


def _bucket_area(lat: float, lng: float) -> str:
    """
    Naive area bucketing for demo:
    - In real Pathway pipeline you'd map to polygons (Upper Lake, New Market, etc.)
    - Here we use coarse grid labels around Bhopal.
    """
    # Rough boxes for some well-known areas (lat/lng approx)
    if 23.245 <= lat <= 23.265 and 77.39 <= lng <= 77.41:
        return "Upper Lake"
    if 23.225 <= lat <= 23.245 and 77.40 <= lng <= 77.42:
        return "Van Vihar"
    if 23.250 <= lat <= 23.270 and 77.41 <= lng <= 77.43:
        return "New Market"
    if 23.230 <= lat <= 23.250 and 77.42 <= lng <= 77.45:
        return "MP Nagar"
    # Fallback
    return "Bhopal-Other"


def get_crowded_area_alerts_python() -> List[Dict]:
    """
    Python fallback for crowded / unsafe area detection.
    Looks at recent events in a 5-minute window and aggregates by area.
    """
    now = int(time.time())
    counts: Dict[str, int] = defaultdict(int)
    max_aqi: Dict[str, float] = defaultdict(float)

    for ev in list(_EVENT_BUFFER):
        if now - ev["ts"] > WINDOW_SECONDS:
            continue
        area = _bucket_area(ev["lat"], ev["lng"])
        counts[area] += 1
        if ev["aqi"] is not None:
            max_aqi[area] = max(max_aqi[area], ev["aqi"])

    alerts: List[Dict] = []
    for area, cnt in counts.items():
        aqi = max_aqi.get(area, 0.0)

        # thresholds (demo)
        crowded = cnt >= 5
        polluted = aqi >= 150

        if crowded or polluted:
            severity = "medium"
            if crowded and polluted:
                severity = "high"
            elif polluted:
                severity = "medium"
            else:
                severity = "low"

            msg_parts = []
            if crowded:
                msg_parts.append(f"high crowd density ({cnt} users in last {WINDOW_SECONDS//60} min)")
            if polluted:
                msg_parts.append(f"high AQI (~{int(aqi)})")
            message = " and ".join(msg_parts)

            recommendation = ""
            if polluted and crowded:
                recommendation = "Avoid this area right now. Prefer green routes or public transport."
            elif polluted:
                recommendation = "Air quality is poor. Limit outdoor exposure, consider masks or PT."
            elif crowded:
                recommendation = "Area is crowded. Prefer alternate less crowded spots."

            alerts.append(
                {
                    "area": area,
                    "user_count": cnt,
                    "max_aqi": round(aqi, 1),
                    "severity": severity,
                    "message": message,
                    "recommendation": recommendation,
                    "ts": now,
                }
            )

    return alerts


# ----------------- Pathway streaming concept (for PPT / Linux deploy) -----------------

def build_pathway_pipeline():
    """
    Conceptual Pathway pipeline (not run inside Flask on Windows).

    - In a real deployment, you'd:
      * read from Kafka / JSONLines / socket source
      * define a TouristEvent table
      * do windowed aggregations by area
      * write alerts to a sink (HTTP, Kafka, DB)
    """
    if not PATHWAY_STREAMING_AVAILABLE:
        return None

    # Pseudo-code example (will require proper environment to run):
    #
    # class TouristEvent(pw.Schema):
    #     user_id: str
    #     lat: float
    #     lng: float
    #     ts: int
    #     aqi: float
    #
    # events = pw.io.jsonlines.read("location_stream.json", schema=TouristEvent)
    #
    # windowed = (
    #     events
    #     .select(area=_bucket_area(pw.this.lat, pw.this.lng), aqi=pw.this.aqi)
    #     .windowby(pw.this.ts, length=300)
    #     .groupby(pw.this.area)
    #     .reduce(
    #         user_count=pw.reducers.count(),
    #         max_aqi=pw.reducers.max(pw.this.aqi),
    #     )
    # )
    #
    # alerts = windowed.filter(
    #     (pw.this.user_count >= 5) | (pw.this.max_aqi >= 150)
    # )
    #
    # pw.io.jsonlines.write(alerts, "pathway_alerts.json")
    #
    # return alerts

    return None


def get_crowded_area_alerts() -> List[Dict]:
    """
    Public function for Flask/API.
    - If Pathway streaming is running externally, this could read its output.
    - For now, uses Python aggregation so API never breaks.
    """
    # TODO (Linux deploy): If you run a separate Pathway process, you can
    # read its alerts output file / topic here instead of Python fallback.
    return get_crowded_area_alerts_python()







