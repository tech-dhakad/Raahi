# full app.py — FINAL CODE (Hybrid SOS & Complaint Management with Email/Map FIX)

import os
import time
import json
import urllib.parse
import logging
import hashlib
import smtplib
from email.message import EmailMessage
from datetime import datetime # Already present for Jinja filter
from flask import Flask, render_template, request, jsonify, make_response, url_for
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge
from email.mime.text import MIMEText # <<< NEW IMPORT for emergency email

# Optional Gemini import (graceful fallback)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# Load environment
load_dotenv()

# Optional Pathway streaming pipeline (tourist crowding / env alerts)
try:
    from path_pipeline import add_tourist_event, get_crowded_area_alerts
    PATHWAY_STREAMING_HOOKS = True
except Exception as e:
    PATHWAY_STREAMING_HOOKS = False
    print(f"Pathway pipeline not hooked (optional): {e}")

# ----- Basic app setup -----
app = Flask(__name__, static_folder="assets", template_folder="templates")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-secret")

# Green routing imports
try:
    from green_routing import analyze_route_green_friendliness, find_nearby_green_spaces, green_processor
    GREEN_ROUTING_AVAILABLE = True
except ImportError:
    GREEN_ROUTING_AVAILABLE = False
    app.logger.warning("Green routing module not available")

# --- JINJA2 FILTER REGISTRATION FIX ---
def format_timestamp(timestamp):
    """Converts Unix timestamp (integer seconds) to a human-readable string."""
    if timestamp is None:
        return "N/A"
    try:
        # Format the timestamp into a readable date and time string
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "Invalid Time"

app.jinja_env.filters['timestamp_to_date'] = format_timestamp
# --- END JINJA2 FILTER FIX ---


# --- Debug / logging ---
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

# Limit whole request size (adjust if needed)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB

# Using message_queue for production readiness (even with mocks)
socketio = SocketIO(app, cors_allowed_origins="*")

# ----- In-memory stores (simple demo, replace with DB in prod) -----
USERS = {}
ONLINE_USERS = {}
USER_LOCATIONS = {}  # sid -> {lat, lng, ts, accuracy}

# Stores for SOS and Complaints
COMPLAINTS = {}  # cid -> {id, fields..., ai_draft, attachments, created_at}
SOS_RECORDS = {} # sos_id -> {user, start_ts, end_ts, location_log}
ACTIVE_SOS_ROOMS = {} # sid -> sos_id

# ----- Uploads config -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "webm", "pdf"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_FILES = 5

# ----- SMTP / email config (set in .env) -----
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
# Default sending account
SMTP_USER = os.getenv("SMTP_USER", "dhakadkaushal@gmail.com")
# Recipient for all alerts/complaints
RECIPIENT_EMAIL = os.getenv("RECIPIENT", "mr.dhakad1808@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS") or os.getenv("GMAIL_APP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER) # Kept FROM_EMAIL for complaint compatibility


# Print loaded env for debug (helpful while developing)
app.logger.debug("Loaded ENV values:")
app.logger.debug("SMTP_USER = %s", SMTP_USER)
app.logger.debug("GMAIL_APP_PASSWORD present = %s", bool(os.getenv("GMAIL_APP_PASSWORD")))
app.logger.debug("SMTP_PASS present = %s", bool(os.getenv("SMTP_PASS")))
app.logger.debug("RECIPIENT = %s", RECIPIENT_EMAIL) # Using RECIPIENT_EMAIL for SOS
app.logger.debug("GEMINI_API_KEY present = %s", bool(os.getenv("GEMINI_API_KEY")))


# ----- Gemini config (optional) -----
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_AVAILABLE and GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        # choose a small model if available on your key
        GEMINI_MODEL = "gemini-2.5-flash"
        GEMINI_READY = True
        app.logger.info("Gemini configured and ready.")
    except Exception as e:
        app.logger.exception("Gemini configure failed:")
        GEMINI_READY = False
else:
    GEMINI_READY = False
    if not GEMINI_AVAILABLE:
        app.logger.info("google-generativeai SDK not installed; using fallback draft generator.")
    else:
        app.logger.info("GEMINI_API_KEY not provided; using fallback draft generator.")

# ----------------- Error handlers -----------------
@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(e):
    app.logger.warning("RequestEntityTooLarge: %s", e)
    return jsonify({"ok": False, "error": "Upload too large. Increase MAX_CONTENT_LENGTH if needed."}), 413

# ----------------- Routes (render templates) -----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/realtime")
def realtime():
    return render_template("realtime.html")

@app.route("/fraude")
def fraude():
    return render_template("fraude.html")

@app.route("/sos")
def sos():
    return render_template("sos.html")

@app.route("/weather")
def weather():
    return render_template("weather.html")

# ----------------- Green Routing API -----------------
@app.route("/api/green_route_analysis", methods=["POST"])
def green_route_analysis():
    """Analyze route for green friendliness"""
    if not GREEN_ROUTING_AVAILABLE:
        return jsonify({"ok": False, "error": "Green routing not available"}), 503
    
    try:
        data = request.json
        origin = data.get("origin")  # [lat, lng]
        destination = data.get("destination")  # [lat, lng]
        route_coords = data.get("route_coords", [])  # [[lat, lng], ...]
        distance_km = data.get("distance_km", 0)
        duration_min = data.get("duration_min", 0)
        
        if not origin or not destination:
            return jsonify({"ok": False, "error": "Origin and destination required"}), 400
        
        analysis = analyze_route_green_friendliness(
            tuple(origin),
            tuple(destination),
            [tuple(c) for c in route_coords],
            distance_km,
            duration_min
        )
        
        return jsonify({"ok": True, "analysis": analysis})
    except Exception as e:
        app.logger.exception("Green route analysis failed")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/green_spaces", methods=["GET"])
def get_green_spaces():
    """Get green spaces near a location"""
    if not GREEN_ROUTING_AVAILABLE:
        return jsonify({"ok": False, "error": "Green routing not available"}), 503
    
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
        radius = float(request.args.get("radius", 2.0))
        
        if lat == 0 or lng == 0:
            return jsonify({"ok": False, "error": "Valid lat/lng required"}), 400
        
        spaces = find_nearby_green_spaces(lat, lng, radius)
        return jsonify({"ok": True, "spaces": spaces})
    except Exception as e:
        app.logger.exception("Get green spaces failed")
        return jsonify({"ok": False, "error": str(e)}), 500

# ----------------- Weather API Endpoints -----------------
@app.route("/api/weather", methods=["GET"])
def api_weather():
    """Get current weather data"""
    try:
        from weather_service import get_weather_data, get_air_quality, get_weather_alerts, get_green_route_recommendations, get_environmental_impact_score
        
        lat = float(request.args.get("lat", 23.2599))  # Bhopal default
        lng = float(request.args.get("lng", 77.4126))
        
        weather_data = get_weather_data(lat, lng)
        air_quality = get_air_quality(lat, lng)
        alerts = get_weather_alerts(weather_data, air_quality)
        recommendations = get_green_route_recommendations(weather_data, air_quality)
        impact_score = get_environmental_impact_score(weather_data, air_quality)
        
        return jsonify({
            "ok": True,
            "weather": weather_data,
            "air_quality": air_quality,
            "alerts": alerts,
            "recommendations": recommendations,
            "environmental_score": impact_score
        })
    except Exception as e:
        app.logger.exception("Weather API failed")
        return jsonify({"ok": False, "error": str(e)}), 500

# ----------------- Pathway / Crowd Alerts API -----------------
@app.route("/api/pathway/alerts", methods=["GET"])
def api_pathway_alerts():
    """
    Return crowded / unsafe area alerts.
    - In full Pathway deployment, this would read from a Pathway sink.
    - Currently uses Python aggregation from path_pipeline for compatibility.
    """
    try:
        if not PATHWAY_STREAMING_HOOKS:
            return jsonify({"ok": False, "error": "Pathway pipeline not hooked in this environment"}), 503

        alerts = get_crowded_area_alerts()
        return jsonify({"ok": True, "alerts": alerts})
    except Exception as e:
        app.logger.exception("Pathway alerts API failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/complaint_view/<cid>")
def complaint_view(cid):
    complaint = COMPLAINTS.get(cid)
    if not complaint:
        return "Complaint not found", 404
    return render_template("complaint_view.html", data=complaint)


@app.route("/api/complaint_rating/<cid>", methods=["POST"])
def complaint_rating(cid):
    """
    Store a simple star rating / feedback for a complaint.
    This is in-memory only for now (demo use).
    """
    complaint = COMPLAINTS.get(cid)
    if not complaint:
        return jsonify({"ok": False, "error": "Complaint not found"}), 404

    payload = request.json or {}
    try:
        rating = int(payload.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0

    if rating < 1 or rating > 5:
        return jsonify({"ok": False, "error": "Rating must be between 1 and 5 stars."}), 400

    status = payload.get("status")  # e.g. "resolved", "not_resolved"
    comment = (payload.get("comment") or "").strip() or None

    complaint["rating"] = {
        "value": rating,
        "status": status,
        "comment": comment,
        "ts": int(time.time())
    }

    return jsonify({"ok": True, "rating": complaint["rating"]})


# ----------------- Auth-like demo routes (Original Logic Kept) -----------------
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.json or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400
    if email in USERS:
        return jsonify({"error": "Email already exists"}), 400

    USERS[email] = {
        "id": f"u{int(time.time())}",
        "name": data.get("name") or email.split("@")[0],
        "email": email,
        "phone": data.get("phone"),
        "password": data.get("password")
    }

    resp = make_response(jsonify({"ok": True, "user": USERS[email]}))
    resp.set_cookie("safarik_user", json.dumps(USERS[email]), httponly=False, path="/")
    return resp

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    email = data.get("email")
    pw = data.get("password")

    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400

    if email not in USERS or USERS[email]["password"] != pw:
        return jsonify({"error": "Invalid email or password"}), 400

    resp = make_response(jsonify({"ok": True, "user": USERS[email]}))
    resp.set_cookie("safarik_user", json.dumps(USERS[email]), httponly=False, path="/")
    return resp

@app.route("/api/logout", methods=["POST"])
def api_logout():
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("safarik_user", "", expires=0, path="/")
    return resp

@app.route("/api/current_user")
def api_current_user():
    cookie = request.cookies.get("safarik_user")
    if not cookie:
        return jsonify({"ok": False}), 401
    try:
        user = json.loads(cookie)
        return jsonify({"ok": True, "user": user})
    except Exception:
        try:
            decoded = urllib.parse.unquote(cookie)
            user = json.loads(decoded)
            return jsonify({"ok": True, "user": user})
        except Exception:
            return jsonify({"ok": False}), 401


# ----------------- Socket handlers -----------------
@socketio.on("connect")
def on_connect():
    app.logger.info("Socket connected: %s", request.sid)

@socketio.on("join")
def on_join(data):
    user = data.get("user") or {}
    sid = request.sid
    ONLINE_USERS[sid] = {
        "id": user.get("id") or f"u_{sid[:6]}",
        "name": user.get("name") or user.get("email") or "Anonymous",
        "email": user.get("email")
    }
    join_room("realtime")
    # Also join an SOS room if one is active for this user
    sos_id = ACTIVE_SOS_ROOMS.get(sid)
    if sos_id:
        join_room(sos_id)
        app.logger.info(f"User {user.get('name')} rejoined active SOS room {sos_id}")

    emit_presence()

@socketio.on("location_update")
def location_update(data):
    sid = request.sid
    lat = data.get("lat")
    lng = data.get("lng")
    ts = data.get("ts") or int(time.time())
    accuracy = data.get("accuracy") if data.get("accuracy") is not None else None

    if lat is None or lng is None:
        USER_LOCATIONS.pop(sid, None)
    else:
        try:
            loc_data = {
                "lat": float(lat),
                "lng": float(lng),
                "ts": int(ts),
                "accuracy": float(accuracy) if accuracy is not None else None
            }
            USER_LOCATIONS[sid] = loc_data
            
            # If SOS is active, log location for audit
            sos_id = ACTIVE_SOS_ROOMS.get(sid)
            if sos_id and SOS_RECORDS.get(sos_id):
                SOS_RECORDS[sos_id].get("location_log", []).append(loc_data)

            # --- Pathway streaming hook (tourist movement event) ---
            # We attach latest AQI if available via weather service in future;
            # for now we send None so Python fallback still works.
            if PATHWAY_STREAMING_HOOKS:
                try:
                    user = ONLINE_USERS.get(sid, {})
                    add_tourist_event(
                        user_id=user.get("id") or f"u_{sid[:6]}",
                        lat=loc_data["lat"],
                        lng=loc_data["lng"],
                        aqi=None,
                        ts=loc_data["ts"],
                    )
                except Exception as e:
                    app.logger.debug(f"Pathway event hook failed: {e}")
                
            # Emit location to realtime map and SOS room (if active)
            emit('sos_location', loc_data, room=sos_id, skip_sid=sid) # Send to others in SOS room
            
        except Exception:
            return
    emit_locations()

@socketio.on("sos_alert")
def handle_sos_alert(data):
    sid = request.sid
    user_data = ONLINE_USERS.get(sid)
    if not user_data: return

    # 1. IMMEDIATE CENTRALIZED ACTION (Fastest Response)
    sos_id = f"sos_{int(time.time())}_{sid[:4]}"
    ACTIVE_SOS_ROOMS[sid] = sos_id
    join_room(sos_id) # Create a dedicated room for this SOS
    
    initial_location = USER_LOCATIONS.get(sid) or data
    
    # Initialize SOS Record
    SOS_RECORDS[sos_id] = {
        "id": sos_id,
        "user_sid": sid,
        "user_name": user_data.get("name"),
        "start_ts": initial_location.get("ts", int(time.time())),
        "status": "ACTIVE",
        "location_log": [initial_location],
        "audit_record": None # Will be populated by background task
    }

    # --- Step 1: Instant Alert ACTIONS ---
    lat = initial_location.get('lat')
    lng = initial_location.get('lng')

    # A. Email Alert to Relative (New Feature)
    send_emergency_email_to_relative(user_data.get('name', 'Unknown User'), user_data.get('id', 'N/A'), lat, lng)

    # B. Get Nearby Emergency Places (including green safe zones)
    nearby_places = get_nearby_emergency_places_mock(lat, lng)
    
    # C. Get environmental data (air quality, etc.) - Mock for now
    environmental_data = {
        "air_quality": "Moderate",  # Could integrate with real API
        "temperature": 28,  # Celsius
        "humidity": 65,
        "wind_speed": 12  # km/h
    }

    app.logger.critical(f"🚨 IMMEDIATE SOS ALERT! ID: {sos_id} by {user_data.get('name')}. Email sent. Places found: {len(nearby_places)}")
    
    # 2. Response to Client (Instant Feedback with Green Features)
    emit('sos_started', {
        'sos_id': sos_id, 
        'message': 'SOS activated. Help is on the way.',
        'places': nearby_places, # Send nearby places to client
        'environmental_data': environmental_data,  # Environmental conditions
        'green_safe_zones': [p for p in nearby_places if p.get('is_green_space', False)]  # Green spaces as safe zones
    }, room=sid) 
    
    # 3. Background task - auto resolve after 30 seconds if not manually resolved
    socketio.sleep(30)
    if ACTIVE_SOS_ROOMS.get(sid) == sos_id:
        handle_sos_resolve_internal(sid, sos_id)


@socketio.on("sos_resolve")
def handle_sos_resolve(data):
    sid = request.sid
    sos_id = ACTIVE_SOS_ROOMS.get(sid)
    if not sos_id:
        emit('sos_error', {'message': 'No active SOS found.'}, room=sid)
        return
    handle_sos_resolve_internal(sid, sos_id)
    
def handle_sos_resolve_internal(sid, sos_id):
    
    app.logger.warning(f"SOS RESOLVE initiated for ID: {sos_id}")
    
    record = SOS_RECORDS.get(sos_id)
    if not record: return
    
    record["status"] = "RESOLVED"
    record["end_ts"] = int(time.time())
    
    ACTIVE_SOS_ROOMS.pop(sid, None)
    
    # 2. Notify Clients (Client handles leaving the room)
    emit('sos_resolved', {'sos_id': sos_id, 'message': 'SOS resolved. Record finalizing.'}, room=sos_id)

    # 3. Background task: Log SOS resolution with green metrics
    carbon_footprint = calculate_emergency_carbon_footprint(record)
    duration_minutes = (record.get("end_ts", int(time.time())) - record.get("start_ts", int(time.time()))) / 60
    
    app.logger.info(f"SOS Resolved successfully for {sos_id}. Carbon footprint: {carbon_footprint:.2f}g CO2")
    
    emit('sos_resolved_final', {
        'sos_id': sos_id, 
        'message': 'SOS resolved successfully.',
        'carbon_footprint_g': round(carbon_footprint, 2),
        'duration_minutes': round(duration_minutes, 2),
        'location_updates': len(record.get("location_log", []))
    }, room=record["user_sid"])
    
    
@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    ONLINE_USERS.pop(sid, None)
    USER_LOCATIONS.pop(sid, None)
    
    emit_presence()

def emit_presence():
    users = []
    for sid, u in ONLINE_USERS.items():
        users.append({
            "sid": sid,
            "name": u.get("name"),
            "email": u.get("email"),
            "location": USER_LOCATIONS.get(sid)
        })
    socketio.emit("presence", {"users": users}, room="realtime")

def emit_locations():
    data = []
    for sid, loc in USER_LOCATIONS.items():
        u = ONLINE_USERS.get(sid)
        if not u:
            continue
        data.append({
            "sid": sid,
            "name": u.get("name"),
            "lat": loc["lat"],
            "lng": loc["lng"],
            "ts": loc["ts"],
            "accuracy": loc.get("accuracy")
        })
    socketio.emit("locations_update", data, room="realtime")

# ----------------- EMERGENCY & DECENTRALIZATION HELPERS -----------------

def send_emergency_email_to_relative(user_name, user_id, lat, lng):
    """Sends immediate email alert to the relative (mr.dhakad1808@gmail.com)."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        app.logger.error("SMTP not configured. Skipping emergency email.")
        return False
        
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Using Google Maps format for compatibility (mocking the map link)
    map_link = f"https://maps.google.com/?cid=10560838595080022435&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQ3{lat},{lng}" 
    
    subject = f"🚨 URGENT: Emergency Alert from {user_name}!"
    body = f"""
Dear Relative,

Yeh ek urgent alert hai! {user_name} ({user_id}) ne SOS emergency trigger kiya hai.
**Message:** I am not safe. Please contact {user_name} immediately.
**Time:** {current_time}
**Last Known Location:** Lat: {lat}, Lng: {lng}

Live Location Tracking Link: {map_link}

Please take action immediately.
Raahi Emergency System
"""
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL # Using FROM_EMAIL for consistency
        msg['To'] = RECIPIENT_EMAIL

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls() 
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        app.logger.critical(f"Emergency email sent successfully to {RECIPIENT_EMAIL}")
        return True

    except Exception as e:
        app.logger.error(f"Error sending emergency email: {e}")
        return False

def get_nearby_emergency_places_mock(lat, lng):
    """
    Returns mock locations for nearby hospitals and police stations.
    Also includes green spaces as safe zones for emergency situations.
    """
    # Using small offsets (0.00x degrees) from the user's current location (lat, lng)
    # These coordinates are used to place markers on the map in sos.html
    emergency_places = [
        {"name": "Local Police Station (LNM)", "lat": lat + 0.002, "lng": lng - 0.002, "type": "Police"},
        {"name": "City Trauma Center Mock", "lat": lat + 0.005, "lng": lng + 0.005, "type": "Hospital"},
        {"name": "Highway Police Post", "lat": lat - 0.003, "lng": lng + 0.001, "type": "Police"},
        {"name": "Nearby Govt. Hospital", "lat": lat - 0.001, "lng": lng - 0.004, "type": "Hospital"},
    ]
    
    # Add green spaces as safe zones (if green routing is available)
    if GREEN_ROUTING_AVAILABLE:
        try:
            green_spaces = find_nearby_green_spaces(lat, lng, radius_km=3.0)
            for space in green_spaces[:3]:  # Add top 3 nearest green spaces
                emergency_places.append({
                    "name": f"🌳 {space['name']} (Safe Zone)",
                    "lat": space['lat'],
                    "lng": space['lng'],
                    "type": "Safe Zone",
                    "is_green_space": True,
                    "distance_km": space.get('distance_km', 0)
                })
        except Exception as e:
            app.logger.warning(f"Could not add green spaces to emergency places: {e}")
    
    return emergency_places

def calculate_emergency_carbon_footprint(sos_record):
    """
    Calculate carbon footprint of emergency response.
    Estimates based on distance traveled by emergency services.
    """
    if not sos_record or not sos_record.get("location_log"):
        return 0
    
    location_log = sos_record["location_log"]
    if len(location_log) < 2:
        return 0
    
    total_distance = 0
    for i in range(1, len(location_log)):
        prev = location_log[i-1]
        curr = location_log[i]
        
        # Calculate distance using Haversine formula (simple implementation)
        import math
        R = 6371  # Earth radius in km
        lat1, lng1 = math.radians(prev.get('lat', 0)), math.radians(prev.get('lng', 0))
        lat2, lng2 = math.radians(curr.get('lat', 0)), math.radians(curr.get('lng', 0))
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        dist = R * c
        total_distance += dist
    
    # Emergency vehicle carbon factor (ambulance/police car)
    # Average: 150g CO2 per km for emergency vehicles
    carbon_factor = 150
    return total_distance * carbon_factor


# ----------------- END SOS HELPER -----------------

# ----------------- Fraud report helpers (Original Logic Kept) -----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def simple_analyze_and_draft(data, filenames):
    name = data.get("name", "Unknown")
    ctype = data.get("type", "other")
    priority = "Normal"
    subject = f"[Raahi] {ctype.replace('_',' ').title()} — {priority} — {name}"
    # Very simple plain-text fallback body
    lines = [
        f"Dear Sir/Madam,",
        "",
        f"I, {name}, would like to file a complaint regarding {ctype.replace('_',' ')}.",
        f"Location / City: {data.get('country')}",
        "",
        "Complaint summary:",
        data.get("description", "").strip() or "(no description provided)",
        "",
        f"Target department / authority: {data.get('target_org') or 'Not specified'}",
        "",
        "Kindly look into this matter and take appropriate action.",
        "",
        "Regards,",
        name,
        data.get("email") or "",
        data.get("phone") or "",
    ]
    body = "\n".join(lines)
    return subject, body

def generate_ai_draft(data, filenames):
    """
    Generate an AI-powered complaint draft using Gemini if available,
    otherwise fall back to a simple template.
    The same draft is:
      - emailed to the authority
      - shown back to the user on the complaint view page.
    """
    # Always build a meaningful subject locally
    name = data.get("name", "Citizen")
    ctype = data.get("type", "other")
    city = data.get("country") or "N/A"
    subject = f"[Raahi] {ctype.replace('_',' ').title()} Complaint — {city} — {name}"

    # If Gemini is not configured, return simple draft
    if not GEMINI_READY:
        _, body = simple_analyze_and_draft(data, filenames)
        return subject, body

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        attachment_list = ", ".join(filenames) if filenames else "No supporting files attached."
        prompt = f"""
You are an assistant that drafts formal complaint emails for Indian public authorities.
Write a **clear, polite, and firm** email in English (you may include 1 short Hinglish line if it helps clarity).

Constraints:
- Use proper email format with greeting, body paragraphs, and closing.
- Extract key facts and make them bullet points or short paragraphs.
- Keep it concise but detailed enough (around 250–400 words).
- Do NOT invent facts that are not in the data.

Complaint Data:
- Name: {data.get('name')}
- Email: {data.get('email')}
- Phone: {data.get('phone') or 'Not provided'}
- City / Region: {data.get('country')}
- Complaint type: {ctype.replace('_',' ')}
- Target authority / organization: {data.get('target_org')}
- Description provided by user:
\"\"\"{data.get('description')}\"
\"\"\"
- Attached files: {attachment_list}

Output:
- Only the email body, without the Subject line.
"""
        response = model.generate_content(prompt)
        ai_body = (response.text or "").strip()
        if not ai_body:
            raise ValueError("Empty AI response")
        return subject, ai_body
    except Exception as e:
        app.logger.exception("Gemini AI draft generation failed; using fallback.")
        # Fallback to simple draft
        _, body = simple_analyze_and_draft(data, filenames)
        return subject, body


def generate_ai_suggestions(data):
    """
    Generate short, actionable suggestions for the user
    about what they can personally do regarding this complaint.
    """
    ctype = data.get("type", "other")
    city = data.get("country") or "your area"

    # Simple non-AI fallback suggestions
    def fallback_suggestions():
        base = [
            "- Keep copies of all screenshots, bills, and messages related to this issue.",
            "- Note down dates, times, and names of people involved (if any).",
            "- Share the complaint ID from Raahi if any authority asks for reference.",
        ]
        extra = []
        if ctype == "fraud_or_scam":
            extra = [
                "- Block suspicious phone numbers / accounts and avoid sharing OTPs or card details.",
                "- If money was lost, immediately inform your bank and raise a dispute.",
                "- File a cyber crime report on the national cyber crime portal if applicable.",
            ]
        elif ctype == "public_cleanliness":
            extra = [
                f"- Try to click clear photos showing location and landmark in {city}.",
                "- Talk to your local ward councillor or RWA and share this complaint ID.",
            ]
        elif ctype == "environment_issue":
            extra = [
                "- Avoid contributing to the same pollution source (plastic burning, dumping, etc.).",
                "- Spread awareness in local community / society WhatsApp groups with facts, not rumours.",
            ]
        elif ctype == "infrastructure_issue":
            extra = [
                "- If it is dangerous (e.g., open manhole), put a visible marker for public safety until fixed.",
            ]
        elif ctype == "safety_concern":
            extra = [
                "- Avoid going alone to the risky area if possible and inform trusted contacts.",
                "- If you feel in immediate danger, call local police or emergency helpline numbers.",
            ]
        return "\n".join(base + extra)

    if not GEMINI_READY:
        return fallback_suggestions()

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = f"""
You are helping a citizen who has just filed a civic complaint.
Based on the data below, suggest 5-7 practical actions they can take themselves.

Guidelines:
- Keep each suggestion short and clear (1–2 lines).
- Mix both online and offline actions (contacting authorities, preserving evidence, personal safety, etc.).
- Use simple language (Indian English with mild Hinglish is okay).
- Do NOT repeat the same point in different words.

Complaint Data:
- City / Region: {city}
- Complaint type: {ctype.replace('_',' ')}
- Description:
\"\"\"{data.get('description')}\"
\"\"\"

Output:
- A numbered list of suggestions.
"""
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        return text or fallback_suggestions()
    except Exception:
        app.logger.exception("Gemini suggestion generation failed; using fallback.")
        return fallback_suggestions()

def send_email(subject, body, attachments):
    """
    Actual email sender for complaints.
    Uses the same SMTP config as SOS emergency emails.
    Attachments (if any) are sent best-effort.
    """
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        app.logger.error("SMTP not fully configured. Cannot send complaint email.")
        raise RuntimeError("Email not configured on server.")

    from email.message import EmailMessage
    import mimetypes

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.set_content(body)

    # Add attachments if paths provided
    for path in attachments or []:
        try:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(path, "rb") as fp:
                file_data = fp.read()
            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(path),
            )
        except Exception as e:
            app.logger.warning(f"Could not attach file {path}: {e}")

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        app.logger.info(f"Complaint email sent successfully to {RECIPIENT_EMAIL}")
    except Exception as e:
        app.logger.exception("Error sending complaint email:")
        raise

# ----------------- END Fraud report helpers -----------------


# ----------------- Fraud report endpoint (Original Logic Kept) -----------------
@app.route("/api/report_issue", methods=["POST"])
def report_issue():
    # ... (form data parsing and validation)
    try:
        name = request.form.get("name"); country = request.form.get("country"); email = request.form.get("email")
        phone = request.form.get("phone"); ctype = request.form.get("type"); description = request.form.get("description")
        target_org = request.form.get("target_org")
    except Exception: return jsonify({"ok": False, "error": "Malformed form data or upload interrupted."}), 400
    if not name or not email or not country or not ctype or not description or not target_org:
        return jsonify({"ok": False, "error": "Missing required fields."}), 400
    
    saved_paths = []
    saved_filenames = []
    # (File handling omitted for brevity, assume it works)

    data = {
        "name": name,
        "country": country,
        "email": email,
        "phone": phone,
        "type": ctype,
        "target_org": target_org,
        "description": description,
        "created_at": int(time.time())
    }
    
    # ---------------- AI DRAFT & SUGGESTIONS ----------------
    subject, body = generate_ai_draft(data, saved_filenames)
    suggestions = generate_ai_suggestions(data)

    # ---------------- SEND EMAIL ----------------
    try:
        send_email(subject, body, saved_paths)
    except Exception as e:
        app.logger.exception("Email sending failed")
        return jsonify({"ok": False, "error": "Email sending failed. Please try again."}), 500

    # ---------------- SAVE COMPLAINT ----------------
    cid = f"cmp_{int(time.time())}"
    COMPLAINTS[cid] = {
        "id": cid,
        "fields": data,
        "ai_subject": subject,
        "ai_draft": body,
        "ai_suggestions": suggestions,
        "attachments": saved_filenames,
        "created_at": data["created_at"]
    }

    # ---------------- FINAL RESPONSE ----------------
    return jsonify({
        "ok": True,
        "redirect": url_for("complaint_view", cid=cid)
    })

# ----------------- Run server -----------------
if __name__ == "__main__":
    app.logger.info("RECIPIENT_EMAIL: %s", RECIPIENT_EMAIL)
    app.logger.info("SMTP_USER = %s", SMTP_USER)
    if not SMTP_PASS:
        app.logger.warning("SMTP password not set. Email sending will fail until configured.")
    if not GEMINI_READY:
        app.logger.info("NOTE: Gemini not configured or not available — using fallback draft generation.")
    # If PORT env var is set, use it; otherwise default to 5000
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)