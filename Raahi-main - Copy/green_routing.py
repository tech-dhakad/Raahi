"""
Green Routing Module using Pathway Framework
Calculates carbon footprint and eco-friendly routes for Bhopal
"""

try:
    import pathway as pw
    # Check if it's the real Pathway package (has required attributes)
    if hasattr(pw, 'schema_from_dict') or hasattr(pw, 'Table'):
        PATHWAY_AVAILABLE = True
    else:
        PATHWAY_AVAILABLE = False
        print("Warning: Pathway framework not properly installed. Using fallback calculations.")
except (ImportError, AttributeError) as e:
    PATHWAY_AVAILABLE = False
    print(f"Warning: Pathway framework not available. Using fallback calculations. ({e})")

import math
from typing import Dict, List, Tuple

# Carbon emission factors (grams CO2 per km)
CARBON_FACTORS = {
    'car': 120,  # grams CO2 per km
    'motorcycle': 60,
    'bicycle': 0,
    'walking': 0,
    'public_transport': 50,
    'electric_vehicle': 20
}

# Bhopal Green Spaces (parks, lakes, eco-friendly areas)
BHOPAL_GREEN_SPACES = [
    {"name": "Upper Lake (Bada Talab)", "lat": 23.2500, "lng": 77.4000, "type": "lake"},
    {"name": "Van Vihar National Park", "lat": 23.2300, "lng": 77.4100, "type": "park"},
    {"name": "Lower Lake (Chhota Talab)", "lat": 23.2550, "lng": 77.4050, "type": "lake"},
    {"name": "Shahpura Lake", "lat": 23.2400, "lng": 77.4200, "type": "lake"},
    {"name": "Kerwa Dam", "lat": 23.2200, "lng": 77.3800, "type": "waterbody"},
    {"name": "Kaliasot Dam", "lat": 23.2700, "lng": 77.4500, "type": "waterbody"},
    {"name": "Rashtriya Manav Sangrahalaya", "lat": 23.2400, "lng": 77.4300, "type": "green_area"},
]

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using Haversine formula (in km)"""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def calculate_carbon_footprint(distance_km: float, vehicle_type: str = 'car') -> float:
    """Calculate carbon footprint in grams CO2"""
    factor = CARBON_FACTORS.get(vehicle_type, CARBON_FACTORS['car'])
    return distance_km * factor

def calculate_eco_score(route_data: Dict) -> float:
    """
    Calculate eco-friendliness score (0-100)
    Higher score = more eco-friendly
    """
    distance = route_data.get('distance_km', 0)
    duration = route_data.get('duration_min', 0)
    carbon = route_data.get('carbon_emission_g', 0)
    
    # Base score
    score = 100
    
    # Penalize for carbon emissions
    if carbon > 0:
        score -= min(50, carbon / 10)  # Max 50 point penalty
    
    # Reward shorter distances
    if distance < 5:
        score += 10
    elif distance < 10:
        score += 5
    
    # Reward routes passing through green spaces
    if route_data.get('passes_green_space', False):
        score += 15
    
    return max(0, min(100, score))

def find_nearby_green_spaces(lat: float, lng: float, radius_km: float = 2.0) -> List[Dict]:
    """Find green spaces near a location"""
    nearby = []
    for space in BHOPAL_GREEN_SPACES:
        dist = calculate_distance(lat, lng, space['lat'], space['lng'])
        if dist <= radius_km:
            space_copy = space.copy()
            space_copy['distance_km'] = dist
            nearby.append(space_copy)
    return sorted(nearby, key=lambda x: x['distance_km'])

def analyze_route_green_friendliness(origin: Tuple[float, float], 
                                     destination: Tuple[float, float],
                                     route_coords: List[Tuple[float, float]],
                                     distance_km: float,
                                     duration_min: float) -> Dict:
    """
    Analyze route for green friendliness using Pathway-style processing
    """
    # Calculate carbon footprint
    carbon_car = calculate_carbon_footprint(distance_km, 'car')
    carbon_public = calculate_carbon_footprint(distance_km, 'public_transport')
    carbon_saved = carbon_car - carbon_public
    
    # Check if route passes through green spaces
    passes_green = False
    green_spaces_on_route = []
    
    for coord in route_coords[::max(1, len(route_coords)//10)]:  # Sample points
        nearby = find_nearby_green_spaces(coord[0], coord[1], 0.5)
        if nearby:
            passes_green = True
            green_spaces_on_route.extend(nearby[:2])  # Max 2 per route
    
    # Remove duplicates
    seen = set()
    unique_green = []
    for gs in green_spaces_on_route:
        key = (gs['lat'], gs['lng'])
        if key not in seen:
            seen.add(key)
            unique_green.append(gs)
    
    route_data = {
        'distance_km': distance_km,
        'duration_min': duration_min,
        'carbon_emission_g': carbon_car,
        'carbon_public_transport_g': carbon_public,
        'carbon_saved_g': carbon_saved,
        'passes_green_space': passes_green,
        'green_spaces_on_route': unique_green,
        'eco_score': 0  # Will be calculated
    }
    
    route_data['eco_score'] = calculate_eco_score(route_data)
    
    return route_data

# Pathway-based real-time processing (if available)
# Note: Pathway framework may not be available on all platforms
# Using fallback implementation that works everywhere
class GreenRouteProcessor:
    """Route processor with optional Pathway support"""
    
    def __init__(self):
        self.pathway_available = PATHWAY_AVAILABLE
        self.schema = None
        if self.pathway_available:
            try:
                # Try to initialize Pathway schema (may fail on Windows)
                if hasattr(pw, 'schema_from_dict'):
                    self.schema = pw.schema_from_dict({
                        'route_id': pw.column_definition(dtype=str),
                        'origin_lat': pw.column_definition(dtype=float),
                        'origin_lng': pw.column_definition(dtype=float),
                        'dest_lat': pw.column_definition(dtype=float),
                        'dest_lng': pw.column_definition(dtype=float),
                        'distance_km': pw.column_definition(dtype=float),
                        'duration_min': pw.column_definition(dtype=float),
                    })
                else:
                    self.pathway_available = False
            except (AttributeError, NameError, Exception) as e:
                print(f"Pathway initialization failed, using fallback: {e}")
                self.pathway_available = False
    
    def process_routes(self, routes_data: List[Dict]) -> List[Dict]:
        """Process routes - uses Pathway if available, otherwise fallback"""
        if self.pathway_available and self.schema is not None:
            try:
                # Try Pathway processing
                if hasattr(pw, 'debug') and hasattr(pw.debug, 'table_from_dict'):
                    routes_table = pw.debug.table_from_dict(routes_data, schema=self.schema)
                    routes_table = routes_table.select(
                        *pw.this,
                        carbon_emission=pw.this.distance_km * CARBON_FACTORS['car']
                    )
                    return routes_table.to_pandas().to_dict('records')
            except (NameError, AttributeError, Exception) as e:
                print(f"Pathway processing failed, using fallback: {e}")
                self.pathway_available = False
        
        # Fallback: process without Pathway
        processed = []
        for route in routes_data:
            route_copy = route.copy()
            route_copy['carbon_emission'] = calculate_carbon_footprint(
                route.get('distance_km', 0), 'car'
            )
            processed.append(route_copy)
        return processed

# Global processor instance
green_processor = GreenRouteProcessor()


