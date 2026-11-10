"""
Tiny offline city lookup used when someone types a city instead of sharing
their location. No paid geocoding service needed. Add more cities as you like.
"""

CITY_COORDS = {
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "gurgaon": (28.4595, 77.0266),
    "gurugram": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "pune": (18.5204, 73.8567),
    "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "chandigarh": (30.7333, 76.7794),
    "kochi": (9.9312, 76.2673),
    "indore": (22.7196, 75.8577),
    "goa": (15.4909, 73.8278),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194),
    "toronto": (43.6532, -79.3832),
    "berlin": (52.5200, 13.4050),
    "paris": (48.8566, 2.3522),
    "singapore": (1.3521, 103.8198),
    "dubai": (25.2048, 55.2708),
    "sydney": (-33.8688, 151.2093),
}


def lookup_city(name):
    if not name:
        return None
    return CITY_COORDS.get(name.strip().lower())
