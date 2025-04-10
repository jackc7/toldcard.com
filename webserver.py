import os
import datetime
import requests
import logging
import pandas
import base64
import json
import yaml
from io import BytesIO

from flask import Flask, render_template, request, redirect, send_from_directory, abort, got_request_exception, session
from flask_apscheduler import APScheduler
from PIL import Image, ImageDraw, ImageFont
from logging.handlers import RotatingFileHandler
import user_agents
import pytz

import autofill
from toldweb import ToldCard
import message
import config

TIME_DIFFERENCE_THRESHOLD = datetime.timedelta(hours=1, minutes=15)
FLIGHT_RULES_COLORS = {
    "VFR": "#00ff00",
    "MVFR": "#0000ff",
    "IFR": "#ff0000",
    "LIFR": "#ff00ff"
}


# Logging Setup
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_handler = RotatingFileHandler(f"{config.CWD}/logs/error.log", maxBytes=1000000, backupCount=5)
log_handler.setFormatter(log_formatter)
app_logger = logging.getLogger('app_logger')
app_logger.addHandler(log_handler)
app_logger.setLevel(logging.ERROR)

app = Flask(__name__)
scheduler = APScheduler()
app.secret_key = config.SECRET_KEY

def load_airplane_data():
    with open("airplanes.yaml", "r") as stream:
        return yaml.safe_load(stream)

airplane_data = load_airplane_data()

# Load runways.csv
df = pandas.read_csv(f"{config.CWD}/runways.csv", low_memory=False)

def dms_to_decimal(dms_str):
    def convert_to_decimal(coord):
        # Extract degrees, minutes, seconds, and direction
        d, m, s, direction = int(coord[:3]), int(coord[4:6]), float(coord[7:14]), coord[14]

        # Convert DMS to decimal
        decimal = d + (m / 60.0) + (s / 3600.0)

        # Negate if direction is 'S' or 'W'
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return decimal

    lat, lon = dms_str
    lat_decimal = convert_to_decimal(lat)
    lon_decimal = convert_to_decimal(lon)

    return lat_decimal, lon_decimal

def get_runway_directions(identifier):
    identifier = identifier.upper()
    
    search_result = df.loc[(df['Loc Id'] == identifier) | (df['ICAO Id'] == identifier)]
    
    if search_result.empty:
        return [], None

    loc_id = search_result.iloc[0]['Loc Id']
    runway_ids = df.loc[df['Loc Id'] == loc_id, 'Runway Id'].unique()
    
    directions = []
    coordinates = None
    
    for runway_id in runway_ids:
        if isinstance(runway_id, str) and '/' in runway_id:
            directions.extend(runway_id.split('/'))
            # Extract the first valid coordinate pair
            if coordinates is None:
                base_latitude = search_result.iloc[0]['Base Latitude DMS']
                base_longitude = search_result.iloc[0]['Base Longitude DMS']
                coordinates = (base_latitude, base_longitude)
    
    # Filter out any runway ID that contains letters and remove duplicates
    filtered_directions = list(set([d[:-1] if d[-1].isalpha() else d for d in directions if not any(char.isalpha() for char in d[:-1])]))
    filtered_directions.sort()
    
    return filtered_directions, dms_to_decimal(coordinates)

def update_metar_if_needed(data):
    metar_time = data["time"]["dt"]
    metar_datetime = datetime.datetime.strptime(metar_time, '%Y-%m-%dT%H:%M:%SZ')
    metar_datetime = metar_datetime.replace(tzinfo=datetime.timezone.utc)
    
    time_difference = datetime.datetime.now(datetime.timezone.utc) - metar_datetime

    if TIME_DIFFERENCE_THRESHOLD < time_difference:
        fetch_metar()
        with open(f"{config.CWD}/metar.json", "r") as f:
            data = json.load(f)
        print(f"webserver.py - METAR is out of date")

    return data

def metar(airport: str):
    if airport == "kewb":
        with open(os.path.join(os.getcwd(), "metar.json"), "r") as f:
            data = json.load(f)
    else: 
        r = requests.get(f"https://avwx.rest/api/metar/{airport}?token={config.AVWX_TOKEN}")
        data = r.json()
        
    data = update_metar_if_needed(data) # Comment out when unit testing
    metar_datetime = datetime.datetime.strptime(data["time"]["dt"], '%Y-%m-%dT%H:%M:%SZ')
    metar_datetime = metar_datetime.replace(tzinfo=datetime.timezone.utc)

    est = metar_datetime.astimezone(pytz.timezone("US/Eastern"))
    eastern_time = est.strftime("%I:%M %p").lstrip('0')

    flight_rules_color = FLIGHT_RULES_COLORS.get(data["flight_rules"], "")
    flight_rules = f'<span style="color:{flight_rules_color}">{data["flight_rules"]}</span>' if flight_rules_color else data["flight_rules"]

    return eastern_time, data["raw"], data["pressure_altitude"], data["density_altitude"], flight_rules, data

def user_log(data, request, airport):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    log_data = {
        "timestamp": str(datetime.datetime.now()),
        "ip": ip,
        "agent": request.headers.get('User-Agent'),
        "airport": airport,
        **data
    }

    with open(f"{config.CWD}/logs/datalog.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")

@got_request_exception.connect
def handle_exception(sender, exception, **extra):
    app_logger.error("An unhandled exception occurred:", exc_info=exception)

@app.errorhandler(404)
def doesnt_exist(e):
    return redirect('/')

@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html")

@app.route('/favicon.ico') 
def favicon(): 
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

FILES = {
    'fsm': 'FSMC172.pdf',
    'aom': 'AOM.pdf',
    'poh': 'POH.pdf',
    'private': 'private.pdf',
    'instrument': 'instrument.pdf',
    'commercial': 'commercial.pdf',
    'instructor': 'cfi.pdf',
    'toldcard': 'toldcard.pdf',
}
STATIC_PAGES = ["disclaimer", "about", "noplane", "error", "message"]

@app.route('/<path>')
def serve_file(path):
    if path in FILES:
        return send_from_directory(os.path.join(app.root_path, 'static'), FILES[path])
    elif path in STATIC_PAGES:
        return render_template(f"{path}.html")
    else:
        return abort(404, description="Resource not found")

@app.route('/is-airport-supported')
def is_airport_supported():
    airport = request.args.get('airport')
    if airport is None:
        return "what are you doing"
    try:
        info = get_runway_directions(airport)
        if info == ([], None):
            return "false"
    except Exception:
        return "false"
    
    metar = requests.get(f"https://avwx.rest/api/metar/{airport}?token={config.AVWX_TOKEN}").json()
    if "error" in metar.keys():
        return "false"
    
    return "true"
        
    

@app.route('/diagram')
def diagram():
    return "<title>New Bedford Airport Diagram</title>" + requests.get("https://opennav.com/diagrams/KEWB.svg").text

@app.route('/logs')
def logs():
    with open(f"{config.CWD}/logs/datalog.log", "r") as f:
        log_entries = [parse_log_entry(line) for line in f.readlines()[::-1]]
    return render_template('log.html', log_entries=log_entries)

def parse_log_entry(line):
    log_data = json.loads(line.strip())
    ua_string = log_data.get("agent", "Unknown User Agent")
    user_agent = user_agents.parse(ua_string)

    parsed_entry = {
        "timestamp": log_data["timestamp"],
        "airport": log_data.get("airport", "KEWB"),
        "aircraft": log_data.get("aircraft", "Unknown"),
        "custom_weight": log_data.get("custom_weight", None),
        "custom_moment": log_data.get("custom_moment", None),
        "pilots": log_data.get("pilots", 0),
        "backseat": log_data.get("backseat", 0),
        "baggage1": log_data.get("baggage1", 0),
        "baggage2": log_data.get("baggage2", 0),
        "fuelquant": log_data.get("fuelquant", 0),
        "runway": log_data.get("runway", "Unknown"),
        "ip": log_data.get("ip", "Unknown IP"),
        'browser': user_agent.browser.family,
        'os': user_agent.os.family,
        'device': user_agent.device.family
    }

    return parsed_entry

@app.route('/submit-form', methods=['POST'])
def submit_form():
    description = request.form['description']
    message.send_text(description)
    return redirect("/")

@app.route('/form')
@app.route('/')
def form():
    airport = request.args.get('airport')
    if airport is None:
        airport = "kewb"
        runway_directions = ["5", "14", "23", "32"]
        coords = ()
    else:
        airport = airport.upper()
        runway_directions, coords = get_runway_directions(airport)
        
    session['airport'] = airport
    session['runway_directions'] = runway_directions
    session['coords'] = coords

    airplanes = list(airplane_data.keys())
    et, met, pressure_altitude, density_altitude, flight_rules, _ = metar(airport)

    return render_template('form.html', 
                           runway_directions=runway_directions, 
                           et=et, 
                           airplanes=airplanes, 
                           met=met, 
                           pressure_altitude=pressure_altitude, 
                           density_altitude=density_altitude, 
                           flight_rules=flight_rules)

def fetch_metar():
    try:
        response = requests.get(f"https://avwx.rest/api/metar/kewb?token={config.AVWX_TOKEN}", timeout=5)
        response.raise_for_status()
        metar_data = response.json()
        with open("metar.json", "w") as file:
            json.dump(metar_data, file, indent=4)

    except requests.RequestException as e:
        app.logger.error(f"Error fetching METAR data: {e}")

# Scheduler to run fetch_metar function every 120 seconds
@scheduler.task('interval', id='fetch_metar_task', seconds=120, misfire_grace_time=900)
def scheduled_fetch_metar():
    fetch_metar()

def process_form_data(data):
    if not data.get("aircraft"):
        return None, None
    
    if data["aircraft"] == "Custom":
        if data.get("custom_moment") and data.get("custom_weight"):
            bew = float(data["custom_weight"])
            moment = float(data["custom_moment"])
        else:
            return None, None
    else:
        bew = float(airplane_data[data["aircraft"]]["bew"])
        moment = float(airplane_data[data["aircraft"]]["moment"])

    return bew, moment

def generate_balance_chart(told_card_instance):
    arm = told_card_instance.ramp_weight["arm"]
    weight = told_card_instance.ramp_weight["weight"]

    r_model_path = f"{config.CWD}/static/wb.png"
    r_x_origin = 34
    r_x_scale = 26.9
    r_x_offset = 102
    r_y_origin = 1500
    r_y_scale = 1.86  # division-based scale (not multiplication)
    r_y_base = 652

    r_xlinepos = round(r_x_scale * (arm - r_x_origin) + r_x_offset)
    r_ylinepos = round(r_y_base - ((weight - r_y_origin) / r_y_scale))
    r_ylinepos = max(116, min(651, r_ylinepos))

    r_image = Image.open(r_model_path).convert("RGB")
    r_draw = ImageDraw.Draw(r_image)
    r_draw.line((r_xlinepos, 116, r_xlinepos, 651), fill=(255, 0, 0), width=3)
    r_draw.line((101, r_ylinepos, 505, r_ylinepos), fill=(255, 0, 0), width=3)

    s_model_path = f"{config.CWD}/static/wb1.png"
    s_x_origin = 34
    s_x_offset = 73
    s_x_scale = (499 - 73) / (48 - 34)
    s_y_origin = 1500
    s_y_base = 751
    s_y_scale = (751 - 78) / (2600 - 1500)

    s_xlinepos = round(s_x_scale * (arm - s_x_origin) + s_x_offset)
    s_ylinepos = round(s_y_base - ((weight - s_y_origin) * s_y_scale))

    s_image = Image.open(s_model_path).convert("RGB")
    s_draw = ImageDraw.Draw(s_image)
    s_draw.line((s_xlinepos, 81, s_xlinepos, 749), fill=(255, 0, 0), width=3)
    s_draw.line((72, s_ylinepos + 3, 529, s_ylinepos + 3), fill=(255, 0, 0), width=3)

    combined_width = r_image.width + s_image.width
    combined_height = max(r_image.height, s_image.height)
    combined_image = Image.new("RGB", (combined_width, combined_height), (255, 255, 255))
    combined_image.paste(r_image, (0, 0))
    combined_image.paste(s_image, (r_image.width, 0))

    draw_combined = ImageDraw.Draw(combined_image)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = None
    draw_combined.text((10, 10), "Cessna 172R", fill=(0, 0, 0), font=font)
    draw_combined.text((r_image.width + 10, 10), "Cessna 172SP", fill=(0, 0, 0), font=font)

    buffer = BytesIO()
    combined_image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@app.route('/data', methods=['POST', 'GET'])
def data():
    if request.method == 'GET':
        return redirect('/')
    if request.method == 'POST':
        form_data = request.form
        data = dict(form_data)
        
        if data["baggage1"] == "":
            data["baggage1"] = "0"
        if data["baggage2"] == "":
            data["baggage2"] = "0"
        if data["fuelquant"] == "":
            data["fuelquant"] = "318"

        bew, moment = process_form_data(data)
        
        # Handle None values for bew and moment
        if bew is None or moment is None:
            return redirect('/error')

        # Add input to ToldCard class
        told_card_instance = ToldCard(bew, moment, float(data["pilots"]), float(data["backseat"]), 
                                  float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        # safe = toldweb.safe_mode(bew, moment, float(data["pilots"]), float(data["backseat"]), 
                                #  float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        
        chart_str = generate_balance_chart(told_card_instance)

        airport = session.get("airport")
        all_runways = session.get("runway_directions")
        coords = session.get("coords")
        user_log(data, request, airport)

        eastern_time, met, pressure_altitude, density_altitude, flight_rules, entire_metar = metar(airport)
        
        img = autofill.fill(told_card_instance, entire_metar, data["runway"], all_runways, coords)
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        autofill_img = f'<img src="data:image/png;base64,{img_str}" alt="Autofill"'

        return render_template("data.html", lines=told_card_instance.basic_empty, chart_str=chart_str, autofill_img=autofill_img, 
                               eastern_time=eastern_time, met=met, pressure_altitude=pressure_altitude, 
                               density_altitude=density_altitude, flight_rules=flight_rules)

scheduler.init_app(app)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=666, debug=True)
