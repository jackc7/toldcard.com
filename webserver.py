import os
import datetime
import requests
import logging
import base64
import json
import yaml
from io import BytesIO

from flask import Flask, render_template, request, redirect, send_from_directory, abort, got_request_exception
from flask_apscheduler import APScheduler
from PIL import Image, ImageDraw
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

def load_airplane_data():
    with open("airplanes.yaml", "r") as stream:
        return yaml.safe_load(stream)

airplane_data = load_airplane_data()

def update_metar_if_needed(data):
    metar_time = data["time"]["dt"]
    metar_datetime = datetime.datetime.strptime(metar_time, '%Y-%m-%dT%H:%M:%SZ')
    time_difference = datetime.datetime.utcnow() - metar_datetime

    if TIME_DIFFERENCE_THRESHOLD < time_difference:
        fetch_metar()
        with open(f"{config.CWD}/metar.json", "r") as f:
            data = json.load(f)
        message.send_text(f"webserver.py - METAR is out of date")

    return data

def metar():
    with open(os.path.join(os.getcwd(), "metar.json"), "r") as f:
        data = json.load(f)

    data = update_metar_if_needed(data) # Comment out when unit testing
    metar_datetime = datetime.datetime.strptime(data["time"]["dt"], '%Y-%m-%dT%H:%M:%SZ')

    tz = pytz.timezone("UTC")
    est = tz.normalize(tz.localize(metar_datetime)).astimezone(pytz.timezone("US/Eastern"))
    eastern_time = est.strftime("%I:%M %p").lstrip('0')

    flight_rules_color = FLIGHT_RULES_COLORS.get(data["flight_rules"], "")
    flight_rules = f'<span style="color:{flight_rules_color}">{data["flight_rules"]}</span>' if flight_rules_color else data["flight_rules"]

    return eastern_time, data["raw"], data["pressure_altitude"], data["density_altitude"], flight_rules, data

def user_log(data, request):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    log_data = {
        "timestamp": str(datetime.datetime.now()),
        "ip": ip,
        "agent": request.headers.get('User-Agent'),
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

@app.route('/submit_form', methods=['POST'])
def submit_form():
    description = request.form['description']
    message.send_text(description)
    return redirect("/")

@app.route('/form')
@app.route('/')
def form():
    airplanes = list(airplane_data.keys())
    eastern_time, met, pressure_altitude, density_altitude, flight_rules, _ = metar()
    print(eastern_time, met, pressure_altitude, density_altitude, flight_rules)
    return render_template('form.html', eastern_time=eastern_time, airplanes=airplanes, met=met, pressure_altitude=pressure_altitude, density_altitude=density_altitude, flight_rules=flight_rules)

def fetch_metar():
    try:
        response = requests.get(f"https://avwx.rest/api/metar/KBOS?token={config.AVWX_TOKEN}", timeout=5)
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
    xlinepos = round(26.9 * (told_card_instance.ramp_weight["arm"] - 34) + 102)
    ylinepos = round(652 - ((told_card_instance.ramp_weight["weight"] - 1500) / 1.86))
    
    chart = Image.open(f"{config.CWD}/static/wb.png")
    draw = ImageDraw.Draw(chart) 
    draw.line((xlinepos, 116, xlinepos, 651), fill=(255, 0, 0), width=3)
    draw.line((101, ylinepos, 505, ylinepos), fill=(255, 0, 0), width=3)

    chart_buffer = BytesIO()
    chart.save(chart_buffer, format="PNG")
    return base64.b64encode(chart_buffer.getvalue()).decode()

@app.route('/data', methods=['POST', 'GET'])
def data():
    if request.method == 'GET':
        return redirect('/')
    if request.method == 'POST':
        form_data = request.form
        data = dict(form_data)

        bew, moment = process_form_data(data)
        
        # Handle None values for bew and moment
        if bew is None or moment is None:
            return redirect('/error')

        told_card_instance = ToldCard(bew, moment, float(data["pilots"]), float(data["backseat"]), 
                                  float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        # safe = toldweb.safe_mode(bew, moment, float(data["pilots"]), float(data["backseat"]), 
                                #  float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        
        chart_str = generate_balance_chart(told_card_instance)
        user_log(data, request)
        
        eastern_time, met, pressure_altitude, density_altitude, flight_rules, entire_metar = metar()

        img = autofill.fill(told_card_instance , entire_metar, runway=form_data["runway"])
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
    app.run(host='0.0.0.0', port=8000, debug=False)
