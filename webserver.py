from flask import Flask, render_template, request, redirect, send_from_directory, abort, session
from logging.handlers import RotatingFileHandler
from PIL import Image, ImageDraw
from io import BytesIO

import datetime
import requests
import logging
import base64
import pytz
import json
import yaml
import os

import metardaemon
import autofill
import toldweb
import message
import config

# Set up logging
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_handler = RotatingFileHandler(f"{config.CWD}/logs/error.log", maxBytes=1000000, backupCount=5)
log_handler.setFormatter(log_formatter)
app_logger = logging.getLogger('app_logger')
app_logger.addHandler(log_handler)
app_logger.setLevel(logging.ERROR)

with open("airplanes.yaml", "r") as stream:
    airplane_data = yaml.safe_load(stream)


def metar(supplied_metar=""):
    with open(f"{config.CWD}/metar.json","r") as f:
        data = json.load(f)

    metar_time = data["time"]["dt"]
    metar_datetime = datetime.datetime.strptime(metar_time, '%Y-%m-%dT%H:%M:%SZ')

    # Checks if metar_time is within 1hr 15m, otherwise update METAR
    time_difference = datetime.datetime.utcnow() - metar_datetime

    if datetime.timedelta(0.05208333333) < time_difference:
        metardaemon.get_metar()
        
        with open(f"{config.CWD}/metar.json","r") as f:
            data = json.load(f)

        metar_time = data["time"]["dt"]
        metar_datetime = datetime.datetime.strptime(metar_time, '%Y-%m-%dT%H:%M:%SZ')
        message.send_text(f"webserver.py - METAR is out of date")
        
    # Converts METAR time to Eastern
    tz = pytz.timezone("UTC")
    est = tz.normalize(tz.localize(metar_datetime)).astimezone(pytz.timezone("US/Eastern"))
    est_datetime = est.strftime("%I:%M %p")

    if est_datetime[0] == "0":
        est_datetime = est_datetime[1:]

    if data["flight_rules"] == "VFR":
        flight_rules = "<span style=\"color:#00ff00\">VFR</span>"
    elif data["flight_rules"] == "MVFR":
        flight_rules = "<span style=\"color:#0000ff\">MVFR</span>"
    elif data["flight_rules"] == "IFR":
        flight_rules = "<span style=\"color:#ff0000\">IFR</span>"
    elif data["flight_rules"] == "LIFR":
        flight_rules = "<span style=\"color:#ff00ff\">LIFR</span>"
    else:
        flight_rules = data["flight_rules"]
    
    return est_datetime, data["raw"], data["pressure_altitude"], data["density_altitude"], flight_rules, data

def user_log(data, request):
    # Check if the X-Forwarded-For header is set
    if 'X-Forwarded-For' in request.headers:
        ip = request.headers['X-Forwarded-For']
    else:
        ip = request.remote_addr

    log = [f" {', '.join(x)} |" for x in [(x,y) for x,y in data.items()]]
    log += [f" ip | {ip}", f" agent | {request.headers.get('User-Agent')}"]
    log = "".join(log)
    with open(f"{config.CWD}/logs/datalog.log", "a") as f:
        f.write(str(datetime.datetime.now())+" "+log+"\n")


app = Flask(__name__)
app.config['SERVER_NAME'] = 'toldcard.com'

@app.route('/form')
def index():
    return redirect('/')

@app.route('/disclaimer')
def disclaimer():
    return render_template("disclaimer.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/noplane')
def noplane():
    return render_template("noplane.html")
    
@app.route('/error')
def internal_error():
    return render_template("error.html")

@app.errorhandler(404)
def doesnt_exist(e):
    return redirect('/')

@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html")

@app.route('/favicon.ico') 
def favicon(): 
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# -------------------- Useful Resources --------------------
files = {
    'fsm': 'FSMC172.pdf',
    'aom': 'AOM.pdf',
    'poh': 'POH.pdf',
    'private': 'private.pdf',
    'instrument': 'instrument.pdf',
    'commercial': 'commercial.pdf',
    'instructor': 'cfi.pdf',
    'toldcard': 'toldcard.pdf',
}

@app.route('/<path>')
def serve_file(path):
    if path in files:
        return send_from_directory(os.path.join(app.root_path, 'static'), files[path])
    else:
        abort(404, description="Resource not found")

@app.route('/diagram')
def diagram():
    return "<title>New Bedford Airport Diagram</title>" + requests.get("https://opennav.com/diagrams/KEWB.svg").text
# ----------------------------------------------------------

@app.route('/logs')
def logs():
    with open(f"{config.CWD}/logs/datalog.log", "r") as f:
        log_lines = []
        for line in f:
            log_lines.insert(0, line)
        log_content = ''.join(log_lines)


    return render_template('log.html', log_content=log_content)

# -------------------- Suggestion Box --------------------
@app.route("/message")
def message_box():
    return render_template('message.html')

@app.route('/submit_form', methods=['POST'])
def submit_form():
    description = request.form['description']

    message.send_text(description)

    return redirect('/')

# --------------------------------------------------------

@app.route('/')
def form():
    airplanes = [keys for keys in airplane_data.keys()]
    et, met, pa, da, fr, _ = metar()

    return render_template('form.html', et=et, airplanes=airplanes, met=met, pa=pa, da=da, fr=fr)

@app.route('/data', methods=['POST', 'GET'])
def data():
    if request.method == 'GET':
        return redirect('/')
    if request.method == 'POST':
        form_data = request.form
        data = dict(form_data)

        if not "aircraft" in data.keys():
            return redirect('/noplane')

        if data["aircraft"] != "Custom":
            bew = airplane_data[data["aircraft"]]["bew"]
            moment = airplane_data[data["aircraft"]]["moment"]
        elif data["custom_moment"] != "" and data["custom_weight"] != "" and data["aircraft"] == "Custom":
            bew = data["custom_weight"]
            moment = data["custom_moment"]
        else:
            return redirect('/error')
            
        bew = float(bew)
        moment = float(moment)

        aircraft = form_data["aircraft"]
            
        resp = toldweb.told_card(bew, moment, float(data["pilots"]), float(data["backseat"]), float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        safe = toldweb.safe_mode(bew, moment, float(data["pilots"]), float(data["backseat"]), float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])

        # Generate Balance Envelope Chart
        xlinepos = round(26.9*(resp[2]-34)+102)
        ylinepos = round(652-((resp[1]-1500)/1.86))

        chart = Image.open(f"{config.CWD}/static/wb.png",)
        draw = ImageDraw.Draw(chart) 

        draw.line((xlinepos, 116, xlinepos, 651), fill=(255,0,0), width=3)
        draw.line((101, ylinepos, 505, ylinepos), fill=(255,0,0), width=3)

        chart_buffer = BytesIO()
        chart.save(chart_buffer, format="PNG")
        chart_str = base64.b64encode(chart_buffer.getvalue()).decode()


        user_log(data, request)
        print(type(request.remote_addr), request.remote_addr)
        runway = form_data["runway"]

        et, met, pa, da, fr, entire_metar = metar()

        try:
            img = autofill.fill(resp[3], entire_metar, runway=runway)
            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            autofill_img = f'<img src="data:image/png;base64,{img_str}" alt="Autofill"'
        except Exception as e:
            app_logger.error(f'Error in main: {str(e)}')
            autofill_img = safe

        return render_template("data.html", lines=resp[0], chart_str=chart_str, autofill_img=autofill_img, et=et, met=met, pa=pa, da=da, fr=fr)


if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=80, debug=False)
    except Exception as e:
        app_logger.error(f'Error in main: {str(e)}')
