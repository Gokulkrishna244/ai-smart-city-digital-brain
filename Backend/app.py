from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from database import assign_incident, get_grievances, get_incidents, get_prediction_count_today, get_recent_predictions, init_db, save_grievance, save_prediction, update_grievance_status, update_incident_status, upsert_incident
from ml_model import get_model_summary, predict_energy, predict_pollution, predict_traffic
import pandas as pd
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
import re
import json
import os
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
@app.after_request
def allow_local_file_dashboard(response):
    """Allow this project's file:// dashboard during local demonstrations."""
    if request.headers.get("Origin") == "null":
        response.headers["Access-Control-Allow-Origin"] = "null"
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
    return response


CORS(app, resources={r"/*": {"origins": r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"}})


init_db()

GEOCODER_URL = os.environ.get("URBANOS_GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
GEOCODER_CACHE = {}
GEOCODER_LOCK = threading.Lock()
GEOCODER_LAST_REQUEST = 0.0


CITY_COORDINATES = {
    "Delhi": {"code": "DL", "lat": 28.6139, "lng": 77.2090, "zone": "North Corridor"},
    "Mumbai": {"code": "MB", "lat": 19.0760, "lng": 72.8777, "zone": "Western Suburbs"},
    "Bengaluru": {"code": "BL", "lat": 12.9716, "lng": 77.5946, "zone": "IT Corridor"},
    "Chennai": {"code": "CH", "lat": 13.0827, "lng": 80.2707, "zone": "Coastal Basin"},
    "Kolkata": {"code": "KL", "lat": 22.5726, "lng": 88.3639, "zone": "Riverfront Belt"},
    "Hyderabad": {"code": "HY", "lat": 17.3850, "lng": 78.4867, "zone": "Tech Valley"},
    "Pune": {"code": "PN", "lat": 18.5204, "lng": 73.8567, "zone": "Deccan Corridor"},
    "Ahmedabad": {"code": "AH", "lat": 23.0225, "lng": 72.5714, "zone": "Sabarmati Grid"},
    "Jaipur": {"code": "JP", "lat": 26.9124, "lng": 75.7873, "zone": "Pink City Ring"},
    "Lucknow": {"code": "LK", "lat": 26.8467, "lng": 80.9462, "zone": "Gomti Corridor"},
    "Surat": {"code": "ST", "lat": 21.1702, "lng": 72.8311, "zone": "Industrial Belt"},
    "Kanpur": {"code": "KN", "lat": 26.4499, "lng": 80.3319, "zone": "Ganga Industrial Zone"},
    "Nagpur": {"code": "NG", "lat": 21.1458, "lng": 79.0882, "zone": "Central Logistics Hub"},
    "Indore": {"code": "IN", "lat": 22.7196, "lng": 75.8577, "zone": "Malwa Urban Grid"},
    "Bhopal": {"code": "BP", "lat": 23.2599, "lng": 77.4126, "zone": "Lake District"},
    "Patna": {"code": "PT", "lat": 25.5941, "lng": 85.1376, "zone": "Ganga Corridor"},
    "Vadodara": {"code": "VD", "lat": 22.3072, "lng": 73.1812, "zone": "Central Gujarat Grid"},
    "Ghaziabad": {"code": "GZ", "lat": 28.6692, "lng": 77.4538, "zone": "NCR East"},
    "Ludhiana": {"code": "LD", "lat": 30.9010, "lng": 75.8573, "zone": "Punjab Industrial Grid"},
    "Agra": {"code": "AG", "lat": 27.1767, "lng": 78.0081, "zone": "Yamuna Heritage Zone"},
    "Nashik": {"code": "NS", "lat": 19.9975, "lng": 73.7898, "zone": "Godavari Corridor"},
    "Faridabad": {"code": "FB", "lat": 28.4089, "lng": 77.3178, "zone": "NCR South"},
    "Meerut": {"code": "MR", "lat": 28.9845, "lng": 77.7064, "zone": "Upper Doab Grid"},
    "Rajkot": {"code": "RJ", "lat": 22.3039, "lng": 70.8022, "zone": "Saurashtra Hub"},
    "Varanasi": {"code": "VR", "lat": 25.3176, "lng": 82.9739, "zone": "Heritage Riverfront"},
    "Srinagar": {"code": "SR", "lat": 34.0837, "lng": 74.7973, "zone": "Kashmir Valley Grid"},
    "Kochi": {"code": "KC", "lat": 9.9312, "lng": 76.2673, "zone": "Coastal Mobility Grid"},
    "Bhubaneswar": {"code": "BH", "lat": 20.2961, "lng": 85.8245, "zone": "Temple City Grid"},
    "Guwahati": {"code": "GU", "lat": 26.1445, "lng": 91.7362, "zone": "Brahmaputra Corridor"},
    "Chandigarh": {"code": "CD", "lat": 30.7333, "lng": 76.7794, "zone": "Tricity Grid"},
}

REAL_AREA_POINTS = {
    "Delhi": [
        {"name": "Connaught Place", "code": "CP", "lat": 28.6315, "lng": 77.2167, "zone": "Central Delhi"},
        {"name": "Karol Bagh", "code": "KB", "lat": 28.6517, "lng": 77.1907, "zone": "Market Corridor"},
        {"name": "Saket", "code": "SK", "lat": 28.5245, "lng": 77.2066, "zone": "South Delhi"},
        {"name": "Dwarka", "code": "DW", "lat": 28.5921, "lng": 77.0460, "zone": "Airport Corridor"},
        {"name": "Rohini", "code": "RH", "lat": 28.7041, "lng": 77.1025, "zone": "Northwest Delhi"},
        {"name": "Lajpat Nagar", "code": "LN", "lat": 28.5677, "lng": 77.2433, "zone": "Ring Road"},
        {"name": "Nehru Place", "code": "NP", "lat": 28.5494, "lng": 77.2513, "zone": "Business District"},
        {"name": "Chandni Chowk", "code": "CC", "lat": 28.6506, "lng": 77.2303, "zone": "Old Delhi"},
        {"name": "Hauz Khas", "code": "HK", "lat": 28.5494, "lng": 77.2001, "zone": "South Urban Village"},
        {"name": "Janakpuri", "code": "JP", "lat": 28.6219, "lng": 77.0878, "zone": "West Delhi"},
        {"name": "Mayur Vihar", "code": "MV", "lat": 28.6084, "lng": 77.2956, "zone": "East Delhi"},
        {"name": "Vasant Kunj", "code": "VK", "lat": 28.5200, "lng": 77.1580, "zone": "Airport Ridge"},
    ],
    "Mumbai": [
        {"name": "Bandra", "code": "BD", "lat": 19.0596, "lng": 72.8295, "zone": "Western Line"},
        {"name": "Andheri", "code": "AD", "lat": 19.1136, "lng": 72.8697, "zone": "Airport Belt"},
        {"name": "Dadar", "code": "DD", "lat": 19.0178, "lng": 72.8478, "zone": "Central Interchange"},
        {"name": "Powai", "code": "PW", "lat": 19.1176, "lng": 72.9060, "zone": "Lake District"},
        {"name": "Colaba", "code": "CB", "lat": 18.9067, "lng": 72.8147, "zone": "South Mumbai"},
        {"name": "Worli", "code": "WL", "lat": 19.0176, "lng": 72.8162, "zone": "Sea Link"},
        {"name": "Lower Parel", "code": "LP", "lat": 18.9936, "lng": 72.8256, "zone": "Mill District"},
        {"name": "Goregaon", "code": "GG", "lat": 19.1646, "lng": 72.8493, "zone": "Western Suburbs"},
        {"name": "Borivali", "code": "BV", "lat": 19.2307, "lng": 72.8567, "zone": "North Suburban"},
        {"name": "Chembur", "code": "CH", "lat": 19.0522, "lng": 72.9005, "zone": "Harbour Line"},
        {"name": "Kurla", "code": "KL", "lat": 19.0726, "lng": 72.8845, "zone": "Central Link"},
        {"name": "Malad", "code": "ML", "lat": 19.1860, "lng": 72.8484, "zone": "Western Retail Belt"},
    ],
    "Bengaluru": [
        {"name": "Whitefield", "code": "WF", "lat": 12.9698, "lng": 77.7499, "zone": "IT Corridor"},
        {"name": "Electronic City", "code": "EC", "lat": 12.8452, "lng": 77.6602, "zone": "Tech Expressway"},
        {"name": "Koramangala", "code": "KG", "lat": 12.9352, "lng": 77.6245, "zone": "Inner Ring"},
        {"name": "Indiranagar", "code": "IN", "lat": 12.9784, "lng": 77.6408, "zone": "East Bengaluru"},
        {"name": "MG Road", "code": "MG", "lat": 12.9758, "lng": 77.6068, "zone": "CBD"},
        {"name": "Jayanagar", "code": "JY", "lat": 12.9250, "lng": 77.5938, "zone": "South Grid"},
        {"name": "Marathahalli", "code": "MH", "lat": 12.9569, "lng": 77.7011, "zone": "Outer Ring Road"},
        {"name": "Hebbal", "code": "HB", "lat": 13.0358, "lng": 77.5970, "zone": "Airport Road"},
        {"name": "Yeshwanthpur", "code": "YP", "lat": 13.0285, "lng": 77.5409, "zone": "Industrial Link"},
        {"name": "Rajajinagar", "code": "RJ", "lat": 12.9915, "lng": 77.5550, "zone": "West Bengaluru"},
        {"name": "BTM Layout", "code": "BT", "lat": 12.9166, "lng": 77.6101, "zone": "South Ring"},
        {"name": "Banashankari", "code": "BS", "lat": 12.9255, "lng": 77.5468, "zone": "Southwest Corridor"},
    ],
    "Chennai": [
        {"name": "T. Nagar", "code": "TN", "lat": 13.0418, "lng": 80.2341, "zone": "Retail Core"},
        {"name": "Adyar", "code": "AY", "lat": 13.0067, "lng": 80.2578, "zone": "River Corridor"},
        {"name": "Velachery", "code": "VC", "lat": 12.9756, "lng": 80.2207, "zone": "South Link"},
        {"name": "Anna Nagar", "code": "AN", "lat": 13.0850, "lng": 80.2101, "zone": "Northwest Grid"},
        {"name": "Nungambakkam", "code": "NG", "lat": 13.0604, "lng": 80.2496, "zone": "Central Chennai"},
        {"name": "Mylapore", "code": "MY", "lat": 13.0339, "lng": 80.2687, "zone": "Heritage Core"},
        {"name": "Guindy", "code": "GD", "lat": 13.0067, "lng": 80.2206, "zone": "Industrial Link"},
        {"name": "Tambaram", "code": "TB", "lat": 12.9249, "lng": 80.1000, "zone": "South Terminal"},
        {"name": "Porur", "code": "PR", "lat": 13.0382, "lng": 80.1565, "zone": "West Ring"},
        {"name": "OMR", "code": "OM", "lat": 12.9052, "lng": 80.2270, "zone": "IT Expressway"},
        {"name": "Perambur", "code": "PB", "lat": 13.1210, "lng": 80.2326, "zone": "North Chennai"},
        {"name": "Thiruvanmiyur", "code": "TV", "lat": 12.9830, "lng": 80.2594, "zone": "Coastal IT Link"},
    ],
    "Kolkata": [
        {"name": "Salt Lake", "code": "SL", "lat": 22.5720, "lng": 88.4212, "zone": "Sector V Belt"},
        {"name": "Park Street", "code": "PS", "lat": 22.5531, "lng": 88.3520, "zone": "Central Avenue"},
        {"name": "Howrah", "code": "HW", "lat": 22.5958, "lng": 88.2636, "zone": "Bridge Corridor"},
        {"name": "New Town", "code": "NT", "lat": 22.5797, "lng": 88.4697, "zone": "East Township"},
        {"name": "Ballygunge", "code": "BG", "lat": 22.5279, "lng": 88.3658, "zone": "South Kolkata"},
        {"name": "Gariahat", "code": "GH", "lat": 22.5197, "lng": 88.3668, "zone": "Market Corridor"},
        {"name": "Dum Dum", "code": "DM", "lat": 22.6420, "lng": 88.4310, "zone": "Airport Corridor"},
        {"name": "Jadavpur", "code": "JD", "lat": 22.4990, "lng": 88.3712, "zone": "University Belt"},
        {"name": "Esplanade", "code": "ES", "lat": 22.5646, "lng": 88.3526, "zone": "CBD"},
        {"name": "Behala", "code": "BH", "lat": 22.4980, "lng": 88.3107, "zone": "Southwest Kolkata"},
        {"name": "Alipore", "code": "AP", "lat": 22.5252, "lng": 88.3309, "zone": "Administrative Belt"},
        {"name": "Rajarhat", "code": "RH", "lat": 22.6236, "lng": 88.4598, "zone": "Northeast Growth Area"},
    ],
    "Hyderabad": [
        {"name": "HITEC City", "code": "HC", "lat": 17.4435, "lng": 78.3772, "zone": "Cyberabad"},
        {"name": "Gachibowli", "code": "GB", "lat": 17.4401, "lng": 78.3489, "zone": "Financial District"},
        {"name": "Banjara Hills", "code": "BH", "lat": 17.4126, "lng": 78.4482, "zone": "Central Hills"},
        {"name": "Secunderabad", "code": "SC", "lat": 17.4399, "lng": 78.4983, "zone": "North Terminal"},
        {"name": "Jubilee Hills", "code": "JH", "lat": 17.4326, "lng": 78.4071, "zone": "West Hills"},
        {"name": "Madhapur", "code": "MP", "lat": 17.4483, "lng": 78.3915, "zone": "Tech Corridor"},
        {"name": "Kukatpally", "code": "KP", "lat": 17.4948, "lng": 78.3996, "zone": "Northwest Residential"},
        {"name": "Begumpet", "code": "BP", "lat": 17.4435, "lng": 78.4622, "zone": "Central Link"},
        {"name": "Ameerpet", "code": "AM", "lat": 17.4375, "lng": 78.4483, "zone": "Transit Hub"},
        {"name": "Charminar", "code": "CM", "lat": 17.3616, "lng": 78.4747, "zone": "Old City"},
        {"name": "Kondapur", "code": "KD", "lat": 17.4647, "lng": 78.3648, "zone": "West IT Belt"},
        {"name": "Mehdipatnam", "code": "MD", "lat": 17.3957, "lng": 78.4333, "zone": "Inner Ring"},
    ],
}

LOCAL_STREET_POINTS = {
    "Delhi": [
        ("Barakhamba Road", "Connaught Place", 28.6293, 77.2267), ("Janpath", "Connaught Place", 28.6254, 77.2190),
        ("Ajmal Khan Road", "Karol Bagh", 28.6507, 77.1905), ("Press Enclave Road", "Saket", 28.5289, 77.2195),
        ("Sector 10 Dwarka", "Dwarka", 28.5811, 77.0574), ("Sector 9 Rohini", "Rohini", 28.7163, 77.1171),
        ("Veer Savarkar Marg", "Lajpat Nagar", 28.5702, 77.2381), ("Outer Ring Road", "Nehru Place", 28.5481, 77.2537),
    ],
    "Mumbai": [
        ("Linking Road", "Bandra", 19.0655, 72.8338), ("Hill Road", "Bandra", 19.0552, 72.8278),
        ("S. V. Road", "Andheri", 19.1197, 72.8464), ("Marol Maroshi Road", "Andheri", 19.1171, 72.8802),
        ("L. J. Road", "Dadar", 19.0290, 72.8400), ("Hiranandani Gardens", "Powai", 19.1197, 72.9073),
        ("Colaba Causeway", "Colaba", 18.9145, 72.8237), ("Dr Annie Besant Road", "Worli", 19.0084, 72.8171),
    ],
    "Bengaluru": [
        ("ITPL Main Road", "Whitefield", 12.9850, 77.7375), ("Varthur Road", "Whitefield", 12.9560, 77.7212),
        ("Neeladri Road", "Electronic City", 12.8419, 77.6470), ("Hosur Road", "Electronic City", 12.8495, 77.6690),
        ("80 Feet Road", "Koramangala", 12.9359, 77.6267), ("100 Feet Road", "Indiranagar", 12.9780, 77.6408),
        ("Brigade Road", "MG Road", 12.9719, 77.6071), ("Bellary Road", "Hebbal", 13.0351, 77.5970),
    ],
    "Chennai": [
        ("Usman Road", "T. Nagar", 13.0416, 80.2317), ("Pondy Bazaar", "T. Nagar", 13.0409, 80.2397),
        ("L. B. Road", "Adyar", 13.0068, 80.2566), ("Velachery Main Road", "Velachery", 12.9762, 80.2185),
        ("Second Avenue", "Anna Nagar", 13.0851, 80.2104), ("College Road", "Nungambakkam", 13.0669, 80.2448),
        ("Sardar Patel Road", "Guindy", 13.0107, 80.2206), ("Rajiv Gandhi Salai", "OMR", 12.9136, 80.2295),
    ],
    "Kolkata": [
        ("Sector V", "Salt Lake", 22.5760, 88.4315), ("Broadway Road", "Salt Lake", 22.5865, 88.4172),
        ("Park Street", "Park Street", 22.5520, 88.3532), ("A. J. C. Bose Road", "Park Street", 22.5418, 88.3542),
        ("Howrah Station Road", "Howrah", 22.5839, 88.3434), ("Major Arterial Road", "New Town", 22.5787, 88.4714),
        ("Rash Behari Avenue", "Gariahat", 22.5173, 88.3657), ("Jessore Road", "Dum Dum", 22.6369, 88.4178),
    ],
    "Hyderabad": [
        ("Cyber Towers Road", "HITEC City", 17.4504, 78.3812), ("Kondapur Main Road", "HITEC City", 17.4615, 78.3656),
        ("Financial District Road", "Gachibowli", 17.4149, 78.3445), ("Road No. 12", "Banjara Hills", 17.4096, 78.4384),
        ("S. P. Road", "Secunderabad", 17.4418, 78.4910), ("Road No. 36", "Jubilee Hills", 17.4315, 78.4066),
        ("Madhapur Main Road", "Madhapur", 17.4487, 78.3916), ("KPHB Road", "Kukatpally", 17.4933, 78.3995),
    ],
}


NATIONAL_STATE_CITY_DATA = [
    {"state": "Andhra Pradesh", "type": "State", "capital": "Amaravati", "cities": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati", "Kakinada", "Rajahmundry", "Kadapa", "Anantapur"]},
    {"state": "Arunachal Pradesh", "type": "State", "capital": "Itanagar", "cities": ["Itanagar", "Naharlagun", "Pasighat", "Tawang", "Ziro", "Bomdila", "Aalo"]},
    {"state": "Assam", "type": "State", "capital": "Dispur", "cities": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur", "Nagaon", "Tinsukia", "Sivasagar"]},
    {"state": "Bihar", "type": "State", "capital": "Patna", "cities": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Begusarai", "Ara", "Katihar"]},
    {"state": "Chhattisgarh", "type": "State", "capital": "Raipur", "cities": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon", "Jagdalpur", "Ambikapur"]},
    {"state": "Goa", "type": "State", "capital": "Panaji", "cities": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Bicholim"]},
    {"state": "Gujarat", "type": "State", "capital": "Gandhinagar", "cities": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh", "Gandhinagar", "Anand"]},
    {"state": "Haryana", "type": "State", "capital": "Chandigarh", "cities": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Hisar", "Karnal", "Rohtak", "Sonipat", "Panchkula"]},
    {"state": "Himachal Pradesh", "type": "State", "capital": "Shimla", "cities": ["Shimla", "Dharamshala", "Mandi", "Solan", "Kullu", "Bilaspur", "Chamba", "Una"]},
    {"state": "Jharkhand", "type": "State", "capital": "Ranchi", "cities": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar", "Hazaribagh", "Giridih"]},
    {"state": "Karnataka", "type": "State", "capital": "Bengaluru", "cities": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi", "Davangere", "Ballari", "Shivamogga", "Tumakuru"]},
    {"state": "Kerala", "type": "State", "capital": "Thiruvananthapuram", "cities": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Kannur", "Alappuzha", "Palakkad"]},
    {"state": "Madhya Pradesh", "type": "State", "capital": "Bhopal", "cities": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Satna", "Rewa"]},
    {"state": "Maharashtra", "type": "State", "capital": "Mumbai", "cities": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Aurangabad", "Solapur", "Kolhapur", "Amravati"]},
    {"state": "Manipur", "type": "State", "capital": "Imphal", "cities": ["Imphal", "Thoubal", "Bishnupur", "Kakching", "Churachandpur", "Ukhrul"]},
    {"state": "Meghalaya", "type": "State", "capital": "Shillong", "cities": ["Shillong", "Tura", "Jowai", "Nongpoh", "Williamnagar", "Baghmara"]},
    {"state": "Mizoram", "type": "State", "capital": "Aizawl", "cities": ["Aizawl", "Lunglei", "Champhai", "Serchhip", "Kolasib", "Saiha"]},
    {"state": "Nagaland", "type": "State", "capital": "Kohima", "cities": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha", "Zunheboto"]},
    {"state": "Odisha", "type": "State", "capital": "Bhubaneswar", "cities": ["Bhubaneswar", "Cuttack", "Rourkela", "Puri", "Sambalpur", "Balasore", "Berhampur"]},
    {"state": "Punjab", "type": "State", "capital": "Chandigarh", "cities": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali", "Hoshiarpur"]},
    {"state": "Rajasthan", "type": "State", "capital": "Jaipur", "cities": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Alwar", "Bharatpur"]},
    {"state": "Sikkim", "type": "State", "capital": "Gangtok", "cities": ["Gangtok", "Namchi", "Gyalshing", "Mangan", "Rangpo"]},
    {"state": "Tamil Nadu", "type": "State", "capital": "Chennai", "cities": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Vellore", "Erode", "Thoothukudi"]},
    {"state": "Telangana", "type": "State", "capital": "Hyderabad", "cities": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam", "Ramagundam", "Mahbubnagar"]},
    {"state": "Tripura", "type": "State", "capital": "Agartala", "cities": ["Agartala", "Udaipur", "Dharmanagar", "Kailashahar", "Belonia"]},
    {"state": "Uttar Pradesh", "type": "State", "capital": "Lucknow", "cities": ["Lucknow", "Kanpur", "Varanasi", "Agra", "Prayagraj", "Ghaziabad", "Noida", "Meerut", "Bareilly", "Aligarh"]},
    {"state": "Uttarakhand", "type": "State", "capital": "Dehradun", "cities": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rudrapur", "Nainital", "Rishikesh"]},
    {"state": "West Bengal", "type": "State", "capital": "Kolkata", "cities": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Kharagpur", "Bardhaman", "Malda"]},
    {"state": "Andaman and Nicobar Islands", "type": "Union Territory", "capital": "Port Blair", "cities": ["Port Blair", "Mayabunder", "Diglipur", "Rangat"]},
    {"state": "Chandigarh", "type": "Union Territory", "capital": "Chandigarh", "cities": ["Chandigarh"]},
    {"state": "Dadra and Nagar Haveli and Daman and Diu", "type": "Union Territory", "capital": "Daman", "cities": ["Daman", "Diu", "Silvassa"]},
    {"state": "Delhi", "type": "Union Territory", "capital": "New Delhi", "cities": ["New Delhi", "Delhi", "Dwarka", "Rohini", "Saket", "Karol Bagh"]},
    {"state": "Jammu and Kashmir", "type": "Union Territory", "capital": "Srinagar/Jammu", "cities": ["Srinagar", "Jammu", "Anantnag", "Baramulla", "Udhampur", "Kathua"]},
    {"state": "Ladakh", "type": "Union Territory", "capital": "Leh", "cities": ["Leh", "Kargil"]},
    {"state": "Lakshadweep", "type": "Union Territory", "capital": "Kavaratti", "cities": ["Kavaratti", "Agatti", "Minicoy", "Amini"]},
    {"state": "Puducherry", "type": "Union Territory", "capital": "Puducherry", "cities": ["Puducherry", "Karaikal", "Mahe", "Yanam"]},
]

EXPANDED_STATE_CITY_DATA = {
    "Andhra Pradesh": ["Srikakulam", "Vizianagaram", "Visakhapatnam", "Anakapalle", "Kakinada", "Rajamahendravaram", "Amalapuram", "Eluru", "Bhimavaram", "Vijayawada", "Machilipatnam", "Guntur", "Tenali", "Narasaraopet", "Bapatla", "Ongole", "Nellore", "Tirupati", "Chittoor", "Madanapalle", "Kadapa", "Proddatur", "Kurnool", "Nandyal", "Anantapur", "Hindupur", "Dharmavaram"],
    "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Pasighat", "Tawang", "Ziro", "Bomdila", "Aalo", "Tezu", "Roing", "Namsai", "Changlang", "Khonsa", "Seppa", "Yingkiong", "Daporijo", "Koloriang"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur", "Nagaon", "Tinsukia", "Sivasagar", "Goalpara", "Dhubri", "Bongaigaon", "Barpeta", "Nalbari", "Mangaldoi", "North Lakhimpur", "Dhemaji", "Karimganj", "Hailakandi", "Diphu", "Kokrajhar"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Begusarai", "Ara", "Katihar", "Munger", "Chhapra", "Bettiah", "Saharsa", "Sasaram", "Hajipur", "Siwan", "Motihari", "Kishanganj", "Buxar", "Jehanabad", "Jamui", "Nawada"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon", "Jagdalpur", "Ambikapur", "Raigarh", "Dhamtari", "Mahasamund", "Kanker", "Janjgir", "Kawardha", "Balod", "Bemetara", "Surajpur", "Dantewada"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Bicholim", "Curchorem", "Sanquelim", "Valpoi", "Canacona", "Cuncolim", "Quepem", "Sanguem"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh", "Gandhinagar", "Anand", "Nadiad", "Morbi", "Mehsana", "Bharuch", "Navsari", "Vapi", "Valsad", "Patan", "Palanpur", "Godhra", "Dahod", "Porbandar", "Gondal", "Veraval", "Surendranagar", "Amreli", "Bhuj"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Hisar", "Karnal", "Rohtak", "Sonipat", "Panchkula", "Yamunanagar", "Kurukshetra", "Kaithal", "Rewari", "Bhiwani", "Sirsa", "Jind", "Palwal", "Fatehabad", "Narnaul", "Bahadurgarh"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Mandi", "Solan", "Kullu", "Bilaspur", "Chamba", "Una", "Hamirpur", "Nahan", "Palampur", "Manali", "Kangra", "Nurpur", "Sundernagar", "Paonta Sahib"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar", "Hazaribagh", "Giridih", "Ramgarh", "Medininagar", "Chaibasa", "Dumka", "Sahibganj", "Godda", "Pakur", "Lohardaga", "Gumla", "Simdega"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Dharwad", "Belagavi", "Davangere", "Ballari", "Shivamogga", "Tumakuru", "Udupi", "Hassan", "Mandya", "Vijayapura", "Kalaburagi", "Bidar", "Raichur", "Koppal", "Chitradurga", "Chikkamagaluru", "Bagalkot", "Haveri", "Gadag", "Karwar", "Kolar"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Kannur", "Alappuzha", "Palakkad", "Kottayam", "Malappuram", "Manjeri", "Kasaragod", "Kanhangad", "Pathanamthitta", "Idukki", "Kalpetta", "Muvattupuzha", "Thalassery", "Ponnani", "Ottappalam"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Satna", "Rewa", "Ratlam", "Dewas", "Chhindwara", "Katni", "Singrauli", "Burhanpur", "Khandwa", "Bhind", "Morena", "Sehore", "Vidisha", "Hoshangabad", "Shivpuri", "Mandsaur", "Neemuch", "Damoh"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Chhatrapati Sambhajinagar", "Aurangabad", "Solapur", "Kolhapur", "Amravati", "Navi Mumbai", "Kalyan", "Dombivli", "Vasai", "Virar", "Mira Bhayandar", "Bhiwandi", "Ulhasnagar", "Akola", "Latur", "Dhule", "Ahmednagar", "Jalgaon", "Nanded", "Sangli", "Satara", "Chandrapur", "Parbhani", "Beed", "Osmanabad", "Yavatmal", "Wardha", "Ratnagiri"],
    "Manipur": ["Imphal", "Thoubal", "Bishnupur", "Kakching", "Churachandpur", "Ukhrul", "Senapati", "Tamenglong", "Jiribam", "Moreh", "Kangpokpi", "Noney"],
    "Meghalaya": ["Shillong", "Tura", "Jowai", "Nongpoh", "Williamnagar", "Baghmara", "Nongstoin", "Mairang", "Resubelpara", "Khliehriat", "Mawkyrwat"],
    "Mizoram": ["Aizawl", "Lunglei", "Champhai", "Serchhip", "Kolasib", "Saiha", "Lawngtlai", "Mamit", "Saitual", "Khawzawl", "Hnahthial"],
    "Nagaland": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha", "Zunheboto", "Mon", "Phek", "Kiphire", "Longleng", "Peren", "Chumoukedima"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Puri", "Sambalpur", "Balasore", "Berhampur", "Baripada", "Bhadrak", "Jharsuguda", "Jeypore", "Koraput", "Dhenkanal", "Angul", "Kendrapara", "Jagatsinghpur", "Rayagada", "Bargarh", "Keonjhar"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali", "Hoshiarpur", "Pathankot", "Moga", "Abohar", "Batala", "Khanna", "Malerkotla", "Barnala", "Firozpur", "Kapurthala", "Faridkot", "Rupnagar", "Sangrur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Alwar", "Bharatpur", "Sikar", "Pali", "Bhilwara", "Tonk", "Kishangarh", "Beawar", "Hanumangarh", "Sri Ganganagar", "Churu", "Jhunjhunu", "Dausa", "Barmer", "Jaisalmer", "Bundi", "Dholpur", "Nagaur"],
    "Sikkim": ["Gangtok", "Namchi", "Gyalshing", "Mangan", "Rangpo", "Singtam", "Jorethang", "Ravangla", "Pakyong"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Vellore", "Erode", "Thoothukudi", "Tiruppur", "Thanjavur", "Dindigul", "Nagercoil", "Kanchipuram", "Cuddalore", "Karur", "Sivakasi", "Hosur", "Ambur", "Kumbakonam", "Pollachi", "Rajapalayam", "Nagapattinam", "Ramanathapuram"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam", "Ramagundam", "Mahbubnagar", "Nalgonda", "Adilabad", "Suryapet", "Miryalaguda", "Siddipet", "Jagtial", "Mancherial", "Kamareddy", "Vikarabad", "Wanaparthy", "Bhongir"],
    "Tripura": ["Agartala", "Udaipur", "Dharmanagar", "Kailashahar", "Belonia", "Khowai", "Ambassa", "Sonamura", "Sabroom", "Bishalgarh"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Agra", "Prayagraj", "Ghaziabad", "Noida", "Meerut", "Bareilly", "Aligarh", "Moradabad", "Saharanpur", "Gorakhpur", "Ayodhya", "Firozabad", "Jhansi", "Muzaffarnagar", "Mathura", "Rampur", "Shahjahanpur", "Farrukhabad", "Mau", "Hapur", "Etawah", "Mirzapur", "Bulandshahr", "Sambhal", "Amroha", "Hardoi", "Fatehpur", "Raebareli", "Orai", "Sitapur", "Bahraich", "Basti", "Azamgarh"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rudrapur", "Nainital", "Rishikesh", "Kashipur", "Pithoragarh", "Almora", "Mussoorie", "Kotdwar", "Ramnagar", "Chamoli", "Tehri", "Uttarkashi"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Kharagpur", "Bardhaman", "Malda", "Haldia", "Berhampore", "Krishnanagar", "Jalpaiguri", "Raiganj", "Balurghat", "Bankura", "Purulia", "Darjeeling", "Cooch Behar", "Alipurduar", "Chandannagar", "Barrackpore", "Serampore"],
    "Andaman and Nicobar Islands": ["Port Blair", "Mayabunder", "Diglipur", "Rangat", "Hut Bay", "Car Nicobar", "Campbell Bay", "Bambooflat"],
    "Chandigarh": ["Chandigarh", "Manimajra"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa", "Amli", "Naroli", "Khanvel"],
    "Delhi": ["New Delhi", "Delhi", "Dwarka", "Rohini", "Saket", "Karol Bagh", "Connaught Place", "Lajpat Nagar", "Nehru Place", "Chandni Chowk", "Hauz Khas", "Janakpuri", "Mayur Vihar", "Vasant Kunj", "Pitampura", "Rajouri Garden", "Okhla", "Narela"],
    "Jammu and Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla", "Udhampur", "Kathua", "Sopore", "Pulwama", "Kupwara", "Poonch", "Rajouri", "Kulgam", "Shopian", "Ganderbal"],
    "Ladakh": ["Leh", "Kargil", "Nubra", "Diskit", "Drass", "Padum", "Nyoma"],
    "Lakshadweep": ["Kavaratti", "Agatti", "Minicoy", "Amini", "Andrott", "Kalpeni", "Kadmat", "Chetlat"],
    "Puducherry": ["Puducherry", "Karaikal", "Mahe", "Yanam", "Oulgaret", "Villianur"],
}

for region in NATIONAL_STATE_CITY_DATA:
    expanded_cities = EXPANDED_STATE_CITY_DATA.get(region["state"], [])
    region["cities"] = list(dict.fromkeys([region["capital"], *region["cities"], *expanded_cities]))


def build_live_city_data():
    data_dir = Path(__file__).resolve().parent.parent / 'Dataset'
    traffic = pd.read_csv(data_dir / 'traffic_data.csv')
    pollution = pd.read_csv(data_dir / 'pollution_data.csv')
    energy = pd.read_csv(data_dir / 'energy_data.csv')
    hour = datetime.now().hour
    traffic_labels = ["Low", "Medium", "High", "Severe"]
    pollution_labels = ["Good", "Moderate", "Poor", "Dangerous"]
    energy_labels = ["Normal", "High", "Critical"]
    base_rows = []

    for index, (city, geo) in enumerate(CITY_COORDINATES.items()):
        traffic_seed = len(traffic[traffic["label"].isin(["High", "Medium"])]) + hour + index
        pollution_seed = len(pollution[pollution["label"].isin(["Poor", "Dangerous"])]) + hour + (index * 2)
        energy_seed = len(energy[energy["label"].isin(["High", "Critical"])]) + hour + (index * 3)
        traffic_status = traffic_labels[min(traffic_seed % len(traffic_labels), len(traffic_labels) - 1)]
        pollution_status = pollution_labels[pollution_seed % len(pollution_labels)]
        energy_status = energy_labels[energy_seed % len(energy_labels)]
        incident_level = "critical" if "Severe" in traffic_status or "Dangerous" in pollution_status else "warning" if "High" in [traffic_status, energy_status] or pollution_status == "Poor" else "stable"
        score = max(64, 98 - (traffic_labels.index(traffic_status) * 7) - (pollution_labels.index(pollution_status) * 5) - (energy_labels.index(energy_status) * 4))
        base_rows.append({
            "city": city,
            "display_name": city,
            "place_type": "city",
            "depth": 0,
            "code": geo["code"],
            "zone": geo["zone"],
            "lat": geo["lat"],
            "lng": geo["lng"],
            "traffic": traffic_status,
            "pollution": pollution_status,
            "energy": energy_status,
            "score": score,
            "level": incident_level,
            "vehicles": 900 + (traffic_seed * 37),
            "aqi": 42 + (pollution_labels.index(pollution_status) * 38) + index,
            "load": 62 + (energy_labels.index(energy_status) * 14) + index,
        })

        for area_index, area in enumerate(REAL_AREA_POINTS.get(city, []), start=1):
            local_seed = index + area_index + hour
            area_traffic = traffic_labels[(traffic_seed + area_index) % len(traffic_labels)]
            area_pollution = pollution_labels[(pollution_seed + area_index) % len(pollution_labels)]
            area_energy = energy_labels[(energy_seed + area_index) % len(energy_labels)]
            area_level = "critical" if area_traffic == "Severe" or area_pollution == "Dangerous" else "warning" if area_traffic == "High" or area_pollution == "Poor" or area_energy == "High" else "stable"
            area_score = max(60, 98 - (traffic_labels.index(area_traffic) * 7) - (pollution_labels.index(area_pollution) * 5) - (energy_labels.index(area_energy) * 4))
            base_rows.append({
                "city": area["name"],
                "display_name": f"{area['name']}, {city}",
                "parent_city": city,
                "place_type": "area",
                "depth": 1,
                "code": area["code"],
                "zone": area["zone"],
                "lat": area["lat"],
                "lng": area["lng"],
                "traffic": area_traffic,
                "pollution": area_pollution,
                "energy": area_energy,
                "score": area_score,
                "level": area_level,
                "vehicles": 420 + (local_seed * 31),
                "aqi": 38 + (pollution_labels.index(area_pollution) * 34) + area_index + index,
                "load": 58 + (energy_labels.index(area_energy) * 13) + area_index,
            })

        for street_index, (street, parent_area, lat, lng) in enumerate(LOCAL_STREET_POINTS.get(city, []), start=1):
            local_seed = index + street_index + hour + 5
            street_traffic = traffic_labels[(traffic_seed + street_index + 1) % len(traffic_labels)]
            street_pollution = pollution_labels[(pollution_seed + street_index + 2) % len(pollution_labels)]
            street_energy = energy_labels[(energy_seed + street_index) % len(energy_labels)]
            street_level = "critical" if street_traffic == "Severe" or street_pollution == "Dangerous" else "warning" if street_traffic == "High" or street_pollution == "Poor" or street_energy == "High" else "stable"
            street_score = max(58, 97 - (traffic_labels.index(street_traffic) * 7) - (pollution_labels.index(street_pollution) * 5) - (energy_labels.index(street_energy) * 4))
            base_rows.append({
                "city": street,
                "display_name": f"{street}, {parent_area}, {city}",
                "parent_city": city,
                "parent_area": parent_area,
                "place_type": "street_corridor",
                "depth": 2,
                "code": f"{geo['code']}-S{street_index:02d}",
                "zone": f"{parent_area} street corridor",
                "lat": lat,
                "lng": lng,
                "traffic": street_traffic,
                "pollution": street_pollution,
                "energy": street_energy,
                "score": street_score,
                "level": street_level,
                "vehicles": 180 + (local_seed * 19),
                "aqi": 34 + (pollution_labels.index(street_pollution) * 33) + street_index + index,
                "load": 52 + (energy_labels.index(street_energy) * 12) + street_index,
            })

    return base_rows


def build_live_payload():
    """Dataset-derived telemetry; it remains clearly marked as simulated."""
    cities = build_live_city_data()
    for city in cities:
        if city["level"] == "stable":
            continue
        category = "traffic" if city["traffic"] in ("High", "Severe") else "environment"
        severity = "critical" if city["level"] == "critical" else "high" if city["score"] < 78 else "medium"
        upsert_incident(f"{city['code']}:{category}", city["city"], category, severity,
            f"{city['traffic']} traffic, AQI {city['aqi']}, and {city['load']}% energy load in {city['zone']}.")
    return {"updated_at": datetime.now().isoformat(timespec='seconds'), "data_source": "simulated_dataset", "cities": cities,
        "totals": {"cities": len(cities), "parent_cities": len(CITY_COORDINATES),
        "areas": sum(city.get("place_type") == "area" for city in cities),
        "streets": sum(city.get("place_type") == "street_corridor" for city in cities),
        "critical": sum(city["level"] == "critical" for city in cities), "warnings": sum(city["level"] == "warning" for city in cities),
        "avg_health": round(sum(city["score"] for city in cities) / len(cities), 1)}}


def build_intelligence_payload():
    cities = build_live_city_data()
    focus = sorted(cities, key=lambda item: item["score"])[:8]
    parent_cities = [city for city in cities if city.get("place_type") == "city"]
    model_metrics = get_model_summary()["metrics"]
    predictions = []
    for index, city in enumerate(focus):
        confidence = round(72 + ((city["aqi"] + city["vehicles"] + index) % 24), 1)
        water_demand = "High" if (city["load"] + index) % 3 == 0 else "Normal"
        predictions.append({
            "city": city["city"],
            "traffic": city["traffic"], "traffic_1h": city["traffic"],
            "pollution": city["pollution"], "aqi_6h": [max(20, city["aqi"] + offset) for offset in (-8, -3, 2, 6, 4, -1)],
            "water_demand": water_demand, "water_forecast_kl": round(420 + city["load"] * 4.3 + index * 12, 1),
            "energy": city["energy"], "energy_forecast_mw": round(18 + city["load"] * .42 + index, 1),
            "anomaly": city["level"] != "stable",
            "confidence": confidence,
            "horizon": "1h traffic / 6h AQI",
            "historical_accuracy": {
                module: (details["validation"].get("macro_f1_mean") if details["validation"].get("status") == "validated" else None)
                for module, details in model_metrics.items()
            },
        })
    rankings = []
    for city in sorted(parent_cities, key=lambda item: item["score"], reverse=True):
        water_score = max(55, 100 - abs(city["load"] - 68))
        emergency_score = max(58, city["score"] - (8 if city["level"] == "critical" else 0))
        overall = round((city["score"] + (180 - city["aqi"]) / 1.8 + water_score + emergency_score) / 4, 1)
        rankings.append({"city": city["city"], "overall": overall, "traffic": city["score"], "air": max(0, 180 - city["aqi"]), "water": water_score, "emergency": emergency_score})
    rankings.sort(key=lambda item: item["overall"], reverse=True)
    anomalies = [{
        "city": item["city"], "domain": "traffic" if item["traffic"] in ("High", "Severe") else "air quality",
        "severity": item["level"], "evidence": f"{item['traffic']} traffic, AQI {item['aqi']}, load {item['load']}%",
        "recommendation": "Dispatch traffic response team and enable adaptive signals." if item["traffic"] in ("High", "Severe") else "Verify sensors and prepare an environmental field inspection.",
    } for item in focus if item["level"] != "stable"]
    operations = {
        "parking_available": sum(max(12, 180 - (city["vehicles"] % 170)) for city in cities[:12]),
        "parking_occupancy": round(sum(city["vehicles"] % 100 for city in cities[:12]) / 12, 1),
        "water_watch_zones": sum(item["water_demand"] == "High" for item in predictions),
        "tank_level": round(64 - len(anomalies) * .8, 1), "possible_leaks": max(1, len(anomalies) // 3),
        "energy_peak_zones": sum(city["energy"] == "Critical" for city in cities),
        "power_demand_mw": round(sum(city["load"] for city in parent_cities) * .82, 1),
        "response_teams_ready": 14, "flood_watch_zones": sum(city["pollution"] == "Dangerous" for city in cities[:30]),
    }
    return {
        "data_source": "simulated_dataset",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "predictions": predictions,
        "operations": operations, "anomalies": anomalies, "rankings": rankings,
        "modules": {
            "traffic": {"congestion_zones": sum(city["traffic"] in ("High", "Severe") for city in cities), "vehicle_density": sum(city["vehicles"] for city in parent_cities), "alternate_routes": len(anomalies)},
            "air": {"avg_aqi": round(sum(city["aqi"] for city in parent_cities) / len(parent_cities), 1), "hotspots": sum(city["aqi"] > 120 for city in cities), "pm25_estimate": round(sum(city["aqi"] for city in parent_cities) / len(parent_cities) / 4, 1)},
            "water": {"tank_level": operations["tank_level"], "possible_leaks": operations["possible_leaks"], "watch_zones": operations["water_watch_zones"]},
            "energy": {"demand_mw": operations["power_demand_mw"], "peak_zones": operations["energy_peak_zones"], "load_forecast": "Elevated" if operations["energy_peak_zones"] else "Normal"},
            "parking": {"available": operations["parking_available"], "occupancy": operations["parking_occupancy"], "entries_today": sum(city["vehicles"] for city in parent_cities)},
            "disaster": {"flood_watch": operations["flood_watch_zones"], "weather_risk": "Elevated" if operations["flood_watch_zones"] else "Low", "teams_ready": operations["response_teams_ready"]},
        },
    }


def air_quality_level(pm25):
    if pm25 <= 8:
        return "Good"
    if pm25 <= 15:
        return "Moderate"
    if pm25 <= 25:
        return "Poor"
    return "Dangerous"


def traffic_score(level):
    return {"Low": 1, "Medium": 2, "High": 3, "Severe": 4}.get(level, 2)


def air_score(level):
    return {"Good": 1, "Moderate": 2, "Poor": 3, "Dangerous": 4}.get(level, 2)


def build_realistic_outcome(roads, air_rows, timeline):
    selected_air = max(air_rows, key=lambda row: air_score(row["simple_quality"])) if air_rows else None
    selected_road = max(roads, key=lambda row: traffic_score(row["traffic_level"])) if roads else None
    if not selected_air and timeline:
        selected_air = max(timeline, key=lambda row: air_score(row["quality"]))

    if selected_air:
        quality = selected_air.get("simple_quality") or selected_air.get("quality")
        pm25 = selected_air.get("pm25")
        location = selected_air.get("location", "Selected area")
        time_label = selected_air.get("time_label", "current time")
    else:
        quality = "No data"
        pm25 = None
        location = selected_road["location"] if selected_road else "Selected area"
        time_label = selected_road["time_label"] if selected_road else "current time"

    traffic_level = selected_road["traffic_level"] if selected_road else "Unknown"
    vehicles = selected_road["vehicle_count"] if selected_road else 0
    road_type = selected_road["road_type"] if selected_road else "road"
    risk_index = min(100, (air_score(quality) * 18) + (traffic_score(traffic_level) * 14) + min(22, int(vehicles) // 8))

    if quality == "Dangerous" or traffic_level == "Severe":
        action = "Restrict heavy vehicles, alert field teams, and issue a public air-health warning."
        health = "Avoid outdoor activity; sensitive groups should stay indoors."
        severity = "critical"
    elif quality == "Poor" or traffic_level == "High":
        action = "Increase signal priority, monitor PM2.5 closely, and recommend reduced outdoor exposure."
        health = "Limit long outdoor activity, especially near busy roads."
        severity = "warning"
    elif quality == "Moderate" or traffic_level == "Medium":
        action = "Keep monitoring; normal travel can continue with minor congestion control."
        health = "Air is acceptable for most people."
        severity = "moderate"
    else:
        action = "Normal operations can continue."
        health = "Air is good for regular outdoor activity."
        severity = "good"

    return {
        "location": location,
        "time": time_label,
        "air_quality": quality,
        "pm25": pm25,
        "traffic_level": traffic_level,
        "road_type": road_type,
        "vehicles": vehicles,
        "risk_index": risk_index,
        "severity": severity,
        "headline": f"{location} at {time_label}: {quality} air with {traffic_level} traffic",
        "health_advice": health,
        "action": action,
    }


def build_national_registry_records():
    road_rows = []
    air_rows = []
    hour = datetime.now().hour
    traffic_labels = ["Low", "Medium", "High", "Severe"]
    pollution_labels = ["Good", "Moderate", "Poor", "Dangerous"]
    energy_labels = ["Normal", "High", "Critical"]

    for state_index, region in enumerate(NATIONAL_STATE_CITY_DATA):
        city_names = list(dict.fromkeys([region["capital"], *region["cities"]]))
        for city_index, city in enumerate(city_names):
            seed = state_index + city_index + hour
            traffic_level = traffic_labels[seed % len(traffic_labels)]
            pollution_level = pollution_labels[(seed + 1) % len(pollution_labels)]
            pm25 = 6 + (pollution_labels.index(pollution_level) * 9) + (city_index % 4)
            road_rows.append({
                "id": int(10000 + len(road_rows) + 1),
                "location": city,
                "state": region["state"],
                "region_type": region["type"],
                "capital": region["capital"],
                "time": hour,
                "time_label": f"{hour:02d}:00",
                "weather": "National registry",
                "vehicle_count": int(360 + (seed * 23)),
                "road_type": f"{region['state']} city corridor",
                "traffic_level": traffic_level,
                "summary": f"{city}, {region['state']} has {traffic_level} traffic at {hour:02d}:00",
            })
            air_rows.append({
                "id": int(10000 + len(air_rows) + 1),
                "location": city,
                "state": region["state"],
                "region_type": region["type"],
                "capital": region["capital"],
                "time": hour,
                "time_label": f"{hour:02d}:00",
                "traffic_level": traffic_level,
                "co2": float(360 + (pollution_labels.index(pollution_level) * 55) + city_index),
                "pm25": float(pm25),
                "temperature": float(24 + ((state_index + city_index) % 12)),
                "humidity": float(42 + ((state_index * 3 + city_index) % 32)),
                "quality": pollution_level,
                "simple_quality": air_quality_level(pm25),
                "summary": f"{city}, {region['state']} air is {pollution_level} at {hour:02d}:00 with PM2.5 {pm25:g}",
            })

    return road_rows, air_rows


def build_city_records(search_text=""):
    data_dir = Path(__file__).resolve().parent.parent / 'Dataset'
    traffic = pd.read_csv(data_dir / 'traffic_data.csv')
    pollution = pd.read_csv(data_dir / 'pollution_data.csv')
    query = search_text.strip().lower()
    live_cities = build_live_city_data()
    national_roads, national_air = build_national_registry_records()

    road_rows = []
    for index, row in traffic.iterrows():
        record = {
            "id": int(index + 1),
            "location": row["location"],
            "time": int(row["time"]),
            "time_label": f"{int(row['time']):02d}:00",
            "weather": row["weather"],
            "vehicle_count": int(row["vehicle_count"]),
            "road_type": row["road_type"],
            "traffic_level": row["label"],
            "summary": f"{row['location']} {row['road_type']} road has {row['label']} traffic at {int(row['time']):02d}:00",
        }
        road_rows.append(record)

    for index, city in enumerate(live_cities):
        hour = datetime.now().hour
        record = {
            "id": int(len(road_rows) + 1),
            "location": city["city"],
            "time": hour,
            "time_label": f"{hour:02d}:00",
            "weather": "Dataset-derived demo",
            "vehicle_count": int(city["vehicles"]),
            "road_type": city["zone"],
            "traffic_level": city["traffic"],
            "summary": f"{city['city']} {city['zone']} has {city['traffic']} traffic at {hour:02d}:00",
        }
        road_rows.append(record)

    air_rows = []
    for index, row in pollution.iterrows():
        source = road_rows[index % len(road_rows)]
        pm25 = float(row["pm25"])
        co2 = float(row["co2"])
        record = {
            "id": int(index + 1),
            "location": source["location"],
            "time": source["time"],
            "time_label": source["time_label"],
            "traffic_level": row["traffic_level"],
            "co2": co2,
            "pm25": pm25,
            "temperature": float(row["temperature"]),
            "humidity": float(row["humidity"]),
            "quality": row["label"],
            "simple_quality": air_quality_level(pm25),
            "summary": f"{source['location']} air is {row['label']} at {source['time_label']} with PM2.5 {pm25:g}",
        }
        air_rows.append(record)

    for city in live_cities:
        hour = datetime.now().hour
        pm25 = round(max(5, city["aqi"] / 4), 1)
        record = {
            "id": int(len(air_rows) + 1),
            "location": city["city"],
            "time": hour,
            "time_label": f"{hour:02d}:00",
            "traffic_level": city["traffic"],
            "co2": float(330 + city["aqi"]),
            "pm25": pm25,
            "temperature": float(28 + (city["load"] % 8)),
            "humidity": float(45 + (city["aqi"] % 20)),
            "quality": city["pollution"],
            "simple_quality": air_quality_level(pm25),
            "summary": f"{city['city']} dataset-derived air is {city['pollution']} at {hour:02d}:00 with estimated PM2.5 {pm25:g}",
        }
        air_rows.append(record)

    road_rows.extend(national_roads)
    air_rows.extend(national_air)

    air_timeline = []
    for hour in range(0, 24):
        if query:
            query_air_rows = [record for record in air_rows if query in str(record).lower()]
            sample_pool = query_air_rows or air_rows
        else:
            sample_pool = air_rows
        sample = sample_pool[hour % len(sample_pool)]
        hour_shift = abs(hour - sample["time"]) % 4
        adjusted_pm25 = max(3, sample["pm25"] + (hour_shift * 2) - (2 if hour < 6 else 0))
        air_timeline.append({
            "hour": hour,
            "time_label": f"{hour:02d}:00",
            "location": sample["location"],
            "pm25": round(adjusted_pm25, 1),
            "quality": air_quality_level(adjusted_pm25),
            "traffic_level": sample["traffic_level"],
        })

    def matches(record):
        if not query:
            return True
        values = [str(value).lower() for value in record.values()]
        return any(query in value for value in values)

    matched_roads = [record for record in road_rows if matches(record)]
    matched_air = [record for record in air_rows if matches(record)]
    if query and not matched_roads and not matched_air:
        normalized_query = re.sub(r"[^a-z0-9]", "", query)
        location_names = list(dict.fromkeys(record["location"] for record in road_rows))
        ranked_names = sorted(
            ((SequenceMatcher(None, normalized_query, re.sub(r"[^a-z0-9]", "", name.lower())).ratio(), name)
             for name in location_names), reverse=True,
        )
        if ranked_names and ranked_names[0][0] >= .68:
            closest = ranked_names[0][1]
            matched_roads = [record for record in road_rows if record["location"] == closest]
            matched_air = [record for record in air_rows if record["location"] == closest]
    matched_timeline = [record for record in air_timeline if not query or query in record["location"].lower() or query in record["quality"].lower() or query in record["traffic_level"].lower() or query in record["time_label"]]
    no_match = bool(query and not matched_roads and not matched_air)
    visible_timeline = [] if no_match else (matched_timeline or air_timeline)
    outcome = ({
        "location": search_text,
        "severity": "moderate",
        "risk_index": "--",
        "headline": f"No verified place match for {search_text}",
        "health_advice": "Try a city, area, locality, or street name from the map.",
        "action": "No operational result was generated, preventing an unrelated location from being shown.",
    } if no_match else build_realistic_outcome(matched_roads or road_rows, matched_air or air_rows, visible_timeline))

    return {
        "query": search_text,
        "roads": matched_roads,
        "air": matched_air,
        "air_timeline": visible_timeline,
        "outcome": outcome,
        "totals": {
            "roads": len(road_rows),
            "air": len(air_rows),
            "matched_roads": len(matched_roads),
            "matched_air": len(matched_air),
            "states": len([item for item in NATIONAL_STATE_CITY_DATA if item["type"] == "State"]),
            "union_territories": len([item for item in NATIONAL_STATE_CITY_DATA if item["type"] == "Union Territory"]),
            "national_cities": len(national_roads),
        }
    }


@app.route('/')
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route('/api')
def api_home():
    return jsonify({
        "project": "AI Smart City Digital Brain",
        "status": "running",
        "message": "Intelligent urban decision support system"
    })


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "backend", "database": "ok", "data_source": "simulated_dataset", "timestamp": datetime.now().isoformat(timespec='seconds')})


def geocode_india(query):
    """Return cached, rate-limited OpenStreetMap place matches for a user query."""
    global GEOCODER_LAST_REQUEST
    cache_key = query.casefold()
    if cache_key in GEOCODER_CACHE:
        return GEOCODER_CACHE[cache_key], True
    params = urlencode({
        "q": query, "format": "jsonv2", "addressdetails": 1,
        "countrycodes": "in", "limit": 8, "dedupe": 1,
    })
    try:
        with GEOCODER_LOCK:
            wait_seconds = 1.05 - (time.monotonic() - GEOCODER_LAST_REQUEST)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            geocoder_request = Request(
                f"{GEOCODER_URL}?{params}",
                headers={"User-Agent": "UrbanOS-SmartCity-Capstone/2.5 (educational local dashboard)"},
            )
            with urlopen(geocoder_request, timeout=8) as response:
                raw_results = json.loads(response.read().decode("utf-8"))
            GEOCODER_LAST_REQUEST = time.monotonic()
    except Exception as error:
        raise RuntimeError(str(error)) from error
    results = []
    for item in raw_results:
        address = item.get("address") or {}
        results.append({
            "osm_id": item.get("osm_id"), "osm_type": item.get("osm_type"),
            "name": item.get("name") or item.get("display_name", "").split(",")[0],
            "display_name": item.get("display_name"), "lat": float(item["lat"]), "lng": float(item["lon"]),
            "category": item.get("category"), "type": item.get("type"),
            "locality": address.get("suburb") or address.get("neighbourhood") or address.get("quarter"),
            "city": address.get("city") or address.get("town") or address.get("village"),
            "district": address.get("state_district") or address.get("district"),
            "taluk": address.get("county") or address.get("municipality"),
            "village": address.get("village"),
            "state": address.get("state"), "postcode": address.get("postcode"),
            "boundingbox": [float(value) for value in item.get("boundingbox", [])],
        })
    GEOCODER_CACHE[cache_key] = results
    return results, False


@app.route('/map-search')
def map_search():
    """User-triggered India place search using OpenStreetMap Nominatim."""
    query = str(request.args.get("q", "")).strip()
    scope = str(request.args.get("scope", "india")).strip().lower()
    if len(query) < 2 or len(query) > 160:
        return jsonify({"message": "Enter a place name between 2 and 160 characters."}), 400
    scope_queries = {
        "bengaluru_urban": [f"{query}, Bengaluru Urban, Karnataka"],
        "bengaluru_rural": [f"{query}, Bengaluru Rural, Karnataka"],
        "bengaluru_all": [f"{query}, Bengaluru Urban, Karnataka", f"{query}, Bengaluru Rural, Karnataka"],
        "india": [query],
    }
    if scope not in scope_queries:
        return jsonify({"message": "Unsupported administrative scope."}), 400
    try:
        search_batches = [geocode_india(scoped_query) for scoped_query in scope_queries[scope]]
    except RuntimeError as error:
        return jsonify({"message": "Live map search is temporarily unavailable.", "detail": str(error)}), 503
    results, seen = [], set()
    rural_taluks = ("doddaballapur", "dodballapur", "devanahalli", "hoskote", "hosakote", "nelamangala")
    for batch_index, (batch, _) in enumerate(search_batches):
        for place in batch:
            identity = (place.get("osm_type"), place.get("osm_id"))
            if identity in seen:
                continue
            seen.add(identity)
            district_text = " ".join(filter(None, [place.get("district"), place.get("taluk"), place.get("display_name")])).lower()
            if scope == "bengaluru_rural" or (scope == "bengaluru_all" and batch_index == 1):
                place["administrative_scope"] = "Bengaluru Rural"
            elif scope == "bengaluru_urban" or (scope == "bengaluru_all" and batch_index == 0):
                place["administrative_scope"] = "Bengaluru Urban"
            elif any(taluk in district_text for taluk in rural_taluks) or "rural" in district_text:
                place["administrative_scope"] = "Bengaluru Rural"
            elif "bengaluru" in district_text or "bangalore" in district_text:
                place["administrative_scope"] = "Bengaluru Urban"
            else:
                place["administrative_scope"] = "Other"
            results.append(place)
    cached = all(batch_cached for _, batch_cached in search_batches)
    return jsonify({
        "source": "OpenStreetMap Nominatim", "cached": cached, "scope": scope, "results": results,
        "administrative_reference": {
            "Bengaluru Urban": ["Bengaluru North", "Bengaluru North (Additional/Yelahanka)", "Bengaluru South", "Bengaluru East", "Anekal"],
            "Bengaluru Rural": ["Doddaballapura", "Devanahalli", "Hoskote", "Nelamangala"],
        },
        "attribution": "OpenStreetMap contributors", "telemetry_note": "Map location only; city metrics remain dataset-derived demo values.",
    })


@app.route('/stats')
def stats():
    summary = get_model_summary()
    data_dir = Path(__file__).resolve().parent.parent / 'Dataset'
    traffic = pd.read_csv(data_dir / 'traffic_data.csv')
    pollution = pd.read_csv(data_dir / 'pollution_data.csv')
    energy = pd.read_csv(data_dir / 'energy_data.csv')
    live = build_live_payload()
    return jsonify({
        "city": "Smart City",
        "prediction_scope": ["Traffic", "Pollution", "Energy"],
        "dataset_summary": summary,
        "charts": {
            "traffic_levels": traffic['label'].value_counts().to_dict(),
            "pollution_levels": pollution['label'].value_counts().to_dict(),
            "energy_levels": energy['label'].value_counts().to_dict()
        },
        "recommendations": [
            "Monitor congestion hotspots during peak hours",
            "Prioritize air quality alerts in industrial zones",
            "Optimize energy usage during high-demand periods"
        ],
        "operational": {"network_health": live["totals"]["avg_health"], "connected_zones": live["totals"]["cities"], "active_incidents": len(get_incidents()), "ai_decisions": get_prediction_count_today(), "data_source": "simulated_dataset"}
    })


@app.route('/live-data')
def live_data():
    return jsonify(build_live_payload())


@app.route('/incidents')
def incidents():
    return jsonify({"data_source": "simulated_dataset", "incidents": get_incidents(request.args.get('status', 'open'))})


@app.route('/intelligence')
def intelligence():
    return jsonify(build_intelligence_payload())


@app.route('/platform')
def platform_overview():
    intelligence_data = build_intelligence_payload()
    cities = [item for item in build_live_city_data() if item.get("place_type") == "city"]
    anomalies = intelligence_data["anomalies"]
    root_causes = [{
        "city": item["city"], "issue": item["domain"],
        "probable_causes": ["Peak-hour demand", "Capacity constraint", "Weather-sensitive variation"] if item["domain"] == "traffic" else ["Traffic emissions", "Low dispersion", "Localized activity"],
        "evidence": item["evidence"], "confidence": 78 + (index % 17),
    } for index, item in enumerate(anomalies[:8])]
    return jsonify({
        "data_source": "simulated_dataset", "generated_at": datetime.now().isoformat(timespec="seconds"),
        "flood_prediction": [{"city": city["city"], "risk": round(min(100, 18 + (city["aqi"] % 35) + (city["load"] % 22)), 1), "rainfall_mm": 22 + city["load"] % 48, "drainage_status": "Watch" if city["load"] > 75 else "Normal", "confidence": 82 + index % 12} for index, city in enumerate(cities[:10])],
        "waste": {"collection_efficiency": 87.4, "bins_full": 24, "routes_active": 18, "waste_tonnes": 436.8, "recycling_rate": 41.2},
        "maintenance": [{"asset": name, "location": city["city"], "health": 58 + (index * 7) % 39, "failure_risk": ["Low", "Medium", "High"][index % 3], "next_action": "Inspect within 24 hours" if index % 3 == 2 else "Continue scheduled monitoring"} for index, (name, city) in enumerate(zip(["Traffic signal", "Water pump", "Street light feeder", "Road sensor", "Drainage gate", "Parking gateway", "Air station", "Bus tracker"], cities))],
        "transport": {"buses_active": 1284, "on_time_percent": 82.6, "passengers_today": 486320, "delayed_routes": 17, "fleet_electric_percent": 28.4},
        "roads": {"good_percent": 72.8, "repair_km": 38.6, "potholes_open": 146, "projects_active": 23, "signals_online": 94.1},
        "public_safety": {"patrol_units": 86, "safe_zones": 112, "camera_uptime": 96.8, "open_cases": len(get_incidents("open")), "average_response_min": 11.4},
        "noise": {"average_db": 67.3, "hotspots": 19, "night_violations": 7, "quiet_zones": 42},
        "sustainability": {"score": 76.8, "renewable_percent": 31.4, "green_cover_percent": 22.7, "emissions_change": -4.8, "water_reuse_percent": 18.6},
        "root_causes": root_causes,
        "recommendations": [item["recommendation"] for item in anomalies[:6]],
        "citizen_alerts": [{"title": "Traffic advisory", "location": item["city"], "message": item["evidence"], "severity": item["severity"]} for item in anomalies[:5]],
        "public_services": ["Water tanker request", "Waste pickup", "Streetlight repair", "Pothole report", "Birth certificate", "Property tax", "Emergency contacts", "Transit information"],
        "grievances": get_grievances(20),
    })


@app.route('/grievances', methods=['GET', 'POST'])
def grievances():
    if request.method == 'GET':
        return jsonify({"grievances": get_grievances(), "data_source": "citizen_submissions"})
    payload = request.get_json(silent=True) or {}
    required = ["citizen_name", "category", "location", "description"]
    missing = [field for field in required if not str(payload.get(field, "")).strip()]
    if missing:
        return jsonify({"message": f"Missing required fields: {', '.join(missing)}"}), 400
    description = str(payload["description"]).strip()
    priority = "high" if any(term in description.lower() for term in ("danger", "flood", "fire", "accident", "emergency")) else "medium"
    grievance_id = save_grievance(str(payload["citizen_name"]).strip(), str(payload["category"]).strip(), str(payload["location"]).strip(), description, priority)
    return jsonify({"id": grievance_id, "status": "submitted", "priority": priority}), 201


@app.route('/grievances/<int:grievance_id>', methods=['PATCH'])
def change_grievance(grievance_id):
    status = str((request.get_json(silent=True) or {}).get("status", "")).strip()
    if status not in {"submitted", "in_review", "assigned", "resolved"}:
        return jsonify({"message": "Invalid grievance status."}), 400
    if not update_grievance_status(grievance_id, status):
        return jsonify({"message": "Grievance not found."}), 404
    return jsonify({"id": grievance_id, "status": status})


@app.route('/assistant', methods=['POST'])
def assistant():
    question = str((request.get_json(silent=True) or {}).get("question", "")).strip()
    if not question:
        return jsonify({"message": "question is required"}), 400
    cities = build_live_city_data()
    def normalized(value):
        return re.sub(r"[^a-z0-9]", "", value.lower())

    question_words = re.findall(r"[a-z0-9]+", question.lower())
    phrases = ["".join(question_words[start:end]) for start in range(len(question_words))
               for end in range(start + 1, min(len(question_words), start + 3) + 1)]
    exact = next((city for city in cities if normalized(city["city"]) in normalized(question)), None)
    ranked = sorted(
        ((max((SequenceMatcher(None, normalized(city["city"]), phrase).ratio() for phrase in phrases), default=0), city)
         for city in cities),
        key=lambda item: item[0], reverse=True,
    )
    mentioned = exact or (ranked[0][1] if ranked and ranked[0][0] >= .72 else None)
    location_match = re.search(r"\b(?:in|at|for|near)\s+(.+)$", question, re.IGNORECASE)
    location_query = location_match.group(1).strip(" ?.!") if location_match else question
    if mentioned and location_match and normalized(location_query) != normalized(mentioned["city"]):
        mentioned = None
    live_place = None
    if not mentioned:
        try:
            live_matches, _ = geocode_india(location_query)
            live_place = live_matches[0] if live_matches else None
        except RuntimeError:
            live_place = None
    if live_place:
        return jsonify({
            "answer": (
                f"I found {live_place['display_name']} on OpenStreetMap. "
                "No verified live traffic, weather, AQI, water, or energy sensor feed is connected for this locality, "
                "so UrbanOS will not invent an operational reading. Select the map result to inspect the location."
            ),
            "city": live_place["name"], "confidence": 100.0,
            "data_source": "OpenStreetMap Nominatim", "map_place": live_place,
            "disclaimer": "Live geographic match only; operational telemetry is unavailable for this place.",
        })
    target = mentioned or min(cities, key=lambda item: item["score"])
    answer = (
        f"{target['city']} currently has {target['traffic'].lower()} traffic, AQI {target['aqi']}, "
        f"and {target['load']}% energy load in this dataset-derived scenario. "
        f"Recommended action: {'prioritize traffic diversion and field verification' if target['level'] == 'critical' else 'continue monitoring and verify sensor conditions'} before dispatch."
    )
    return jsonify({
        "answer": answer,
        "city": target["city"],
        "confidence": 86.0,
        "data_source": "simulated_dataset",
        "recommendations": [
            "Prioritize traffic diversion and field verification." if target["traffic"] in ("High", "Severe") else "Keep adaptive monitoring active.",
            "Review outdoor-exposure guidance." if target["aqi"] > 120 else "Continue routine air-quality observation.",
        ],
        "evidence": [
            {"metric": "Traffic classification", "value": target["traffic"], "source": "CSV-trained traffic model scenario"},
            {"metric": "AQI indicator", "value": target["aqi"], "source": "Dataset-derived telemetry"},
            {"metric": "Energy load", "value": f"{target['load']}%", "source": "Dataset-derived telemetry"},
        ],
        "statistics": {"traffic": target["vehicles"], "aqi": target["aqi"], "energy_load": target["load"], "health": target["score"]},
        "disclaimer": "Decision support only; not a live municipal feed.",
    })


@app.route('/digital-twin', methods=['POST'])
def digital_twin():
    payload = request.get_json(silent=True) or {}
    traffic_change = max(-50, min(100, float(payload.get("traffic_change", 15))))
    rain = max(0, min(100, float(payload.get("rain", 20))))
    event_size = max(0, min(100000, float(payload.get("event_size", 10000))))
    power_change = max(-40, min(100, float(payload.get("power_change", 10))))
    water_shortage = max(0, min(100, float(payload.get("water_shortage", 5))))
    congestion_delta = round((traffic_change * .55) + (rain * .22) + (event_size / 2500), 1)
    baseline = {"congestion": 48, "aqi": 92, "energy": 68, "water": 74, "response_time": 12}
    after = {
        "congestion": round(min(100, baseline["congestion"] + congestion_delta), 1),
        "aqi": round(max(10, baseline["aqi"] + (traffic_change * .08) - (rain * .06)), 1),
        "energy": round(min(100, baseline["energy"] + power_change + event_size / 5000 + rain * .03), 1),
        "water": round(max(0, baseline["water"] - water_shortage - event_size / 10000), 1),
        "response_time": round(baseline["response_time"] + max(0, congestion_delta) / 8, 1),
    }
    return jsonify({
        "data_source": "simulated_scenario",
        "congestion_delta": congestion_delta,
        "aqi_delta": round((traffic_change * .08) - (rain * .06), 1),
        "energy_delta": round((event_size / 5000) + (rain * .03), 1),
        "before": baseline, "after": after,
        "recommendation": "Pre-position response teams and enable adaptive signal timing." if congestion_delta > 25 else "Maintain normal operations with enhanced monitoring.",
    })


@app.route('/incidents/<int:incident_id>', methods=['PATCH'])
def change_incident(incident_id):
    payload = request.get_json(silent=True) or {}
    status = payload.get('status', 'acknowledged')
    if status not in {'open', 'acknowledged', 'resolved'}:
        return jsonify({"message": "status must be open, acknowledged, or resolved"}), 400
    team = str(payload.get("assigned_team", "")).strip()
    eta = int(payload.get("response_eta", 0) or 0)
    updated = assign_incident(incident_id, team, eta, status) if team else update_incident_status(incident_id, status)
    if not updated:
        return jsonify({"message": "incident not found"}), 404
    return jsonify({"id": incident_id, "status": status, "assigned_team": team or None, "response_eta": eta or None})


@app.route('/events')
def events():
    def stream():
        yield f"event: city_update\\ndata: {build_live_payload()}\\n\\n"
    return Response(stream(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache'})


@app.route('/city-records')
def city_records():
    return jsonify(build_city_records(request.args.get('q', '')))


@app.route('/state-city-data')
def state_city_data():
    regions = []
    for region in NATIONAL_STATE_CITY_DATA:
        city_names = list(dict.fromkeys([region["capital"], *region["cities"]]))
        regions.append({
            **region,
            "cities": city_names,
            "city_count": len(city_names),
        })
    cities = sum(region["city_count"] for region in regions)
    return jsonify({
        "states": len([item for item in regions if item["type"] == "State"]),
        "union_territories": len([item for item in regions if item["type"] == "Union Territory"]),
        "cities": cities,
        "regions": regions,
    })


@app.route('/capstone-summary')
def capstone_summary():
    state_payload = state_city_data().get_json()
    live_payload = live_data().get_json()
    records = build_city_records('')
    model_summary = get_model_summary()
    data_dir = Path(__file__).resolve().parent.parent / 'Dataset'
    traffic_rows = len(pd.read_csv(data_dir / 'traffic_data.csv'))
    pollution_rows = len(pd.read_csv(data_dir / 'pollution_data.csv'))
    energy_rows = len(pd.read_csv(data_dir / 'energy_data.csv'))
    model_validation_status = "validated" if all(
        model["validation"]["status"] == "validated"
        for model in model_summary["metrics"].values()
    ) else "insufficient_data"

    return jsonify({
        "title": "AI Smart City Digital Brain",
        "objective": "A dataset-driven decision-support prototype for traffic flow, air quality, and energy demand across Indian city scenarios.",
        "modules": [
            {"name": "Traffic Flow", "model": "Random Forest Classifier", "input": "location, hour, weather, vehicle count, road type", "output": "Low, Medium, High, Severe", **model_summary["metrics"]["traffic"]},
            {"name": "Air Quality", "model": "Random Forest Classifier", "input": "CO2, PM2.5, temperature, humidity, traffic level", "output": "Good, Moderate, Poor, Dangerous", **model_summary["metrics"]["pollution"]},
            {"name": "Energy Demand", "model": "Random Forest Classifier", "input": "area, population, temperature, hour, previous usage", "output": "Normal, High, Critical", **model_summary["metrics"]["energy"]},
        ],
        "coverage": {
            "states": state_payload["states"],
            "union_territories": state_payload["union_territories"],
            "cities": state_payload["cities"],
            "live_city_points": live_payload["totals"]["cities"],
            "live_area_points": live_payload["totals"]["areas"],
            "road_records": records["totals"]["roads"],
            "air_records": records["totals"]["air"],
        },
        "datasets": {
            "traffic_rows": traffic_rows,
            "pollution_rows": pollution_rows,
            "energy_rows": energy_rows,
            "national_generated_records": records["totals"]["national_cities"],
        },
        "validation": {
            "model_pipeline": model_summary,
            "model_validation_status": model_validation_status,
            "api_endpoints": ["/health", "/stats", "/live-data", "/city-records", "/state-city-data", "/predict/traffic", "/predict/pollution", "/predict/energy"],
            "strengths": [
                "Searchable national state-city registry",
                "Real map layer with live area markers",
                "Automated traffic, air, and energy decision outcomes",
                "Audit history for prediction activity",
            ],
        },
        "architecture": [
            "City, area, and national registry data",
            "Flask API and data processing layer",
            "Machine learning prediction services",
            "Operational dashboard and map visualization",
            "Decision output, alerts, and audit trail",
        ],
        "generated_at": datetime.now().isoformat(timespec='seconds'),
    })


def run_prediction(predictor, module, area_field):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"message": "Request body must be a JSON object."}), 400
    try:
        result = predictor(payload)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    save_prediction(module, payload.get(area_field, 'Unknown'), result['prediction'])
    return jsonify(result)


@app.route('/predict/traffic', methods=['POST'])
def predict_traffic_route():
    return run_prediction(predict_traffic, 'traffic', 'location')


@app.route('/predict/pollution', methods=['POST'])
def predict_pollution_route():
    return run_prediction(predict_pollution, 'pollution', 'traffic_level')


@app.route('/predict/energy', methods=['POST'])
def predict_energy_route():
    return run_prediction(predict_energy, 'energy', 'area')


@app.route('/predictions')
def predictions():
    return jsonify(get_recent_predictions())


def build_simple_pdf(lines):
    safe_lines = [str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:110] for line in lines]
    commands = ["BT", "/F1 10 Tf", "48 800 Td", "13 TL"]
    for index, line in enumerate(safe_lines[:54]):
        commands.append(f"({line}) Tj")
        if index < len(safe_lines) - 1:
            commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf)); pdf.extend(f"{number} 0 obj\n".encode()); pdf.extend(obj); pdf.extend(b"\nendobj\n")
    xref = len(pdf); pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


@app.route('/reports/incidents.pdf')
def incident_report_pdf():
    incidents = get_incidents(request.args.get("status", ""), 40)
    lines = ["UrbanOS Forensic Incident Report", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "Data source: simulated dataset / operator incident database", ""]
    for item in incidents:
        lines.extend([
            f"Incident #{item['id']} | {item['severity'].upper()} | {item['status'].upper()}",
            f"Location: {item['city']} | Category: {item['category']} | Time: {item['created_at']}",
            f"Cause/Evidence: {item['explanation']}",
            f"Response: {item.get('assigned_team') or 'Unassigned'} | ETA: {item.get('response_eta') or '--'} minutes", "",
        ])
    return Response(build_simple_pdf(lines), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=UrbanOS-Forensic-Incidents.pdf"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
