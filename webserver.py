from flask import Flask, render_template, request, redirect, send_from_directory
from PIL import Image, ImageDraw

import datetime
import requests
import random
import pytz
import json
import os
import re

import toldweb
import metardaemon
import autofill
import message
import config

def generate_image(weight, arm):
    try: 
        xlinepos = round(26.9*(arm-34)+102)
        ylinepos = round(652-((weight-1500)/1.86))

        photo = Image.open(f"{config.CWD}/static/wb.png",)
        draw = ImageDraw.Draw(photo) 

        draw.line((xlinepos, 116, xlinepos, 651), fill=(255,0,0), width=3)
        draw.line((101, ylinepos, 505, ylinepos), fill=(255,0,0), width=3)

        imgname = str(random.randint(0,100000000000))+"g.png"
        filename = f"{config.CWD}/static/tmp/"+imgname
        newfilename = "static/tmp/"+imgname

        photo.save(filename)

        return newfilename
    except Exception as e:
        config.error_log(e)
        return "static/wb.png" 

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
        
    return est_datetime, data["raw"], data["pressure_altitude"], data["density_altitude"], data["flight_rules"], data

def user_log(data, ip):
    log = [f" {', '.join(x)} |" for x in [(x,y) for x,y in data.items()]]
    log += [f" ip | {ip}", f" agent | {request.headers.get('User-Agent')}"]
    log = "".join(log)
    with open(f"{config.CWD}/logs/datalog.log", "a") as f:
        f.write(str(datetime.datetime.now())+" "+log+"\n")


app = Flask(__name__)

@app.route('/form')
def index():
    return redirect('/')

@app.route('/test')
def test():
    return render_template("log.html")

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
@app.route('/fsm')
def fsm():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'FSMC172.pdf')

@app.route('/aom')
def aom():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'AOM.pdf')

@app.route('/poh')
def poh():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'POH.pdf')

@app.route('/private')
def private():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'private.pdf')

@app.route('/instrument')
def instrument():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'instrument.pdf')

@app.route('/commercial')
def commercial():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'commercial.pdf')

@app.route('/instructor')
def cfi():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'cfi.pdf')

@app.route('/diagram')
def diagram():
    return "<title>New Bedford Airport Diagram</title>" + requests.get("https://opennav.com/diagrams/KEWB.svg").text
# ----------------------------------------------------------



@app.route('/logs')
def logs():
    with open(f"{config.CWD}/logs/datalog.log", "r") as f:
        text = f.read()
    formatted = text.replace(' ', '&nbsp;').replace('\n', '<br>')    

    return f"""<!DOCTYPE html><html><link rel="shortcut icon" href="/static/favicon.ico"><code>{formatted}</code></html>"""

@app.route('/')
def form():
    airplanes = ["N172SJ", "N223BW", "N407BW", "N574BW", "N579BW", "N715BW", "N721SA", "N760BW", "N780SA", "N856CP", "N829BW"]
    et, met, pa, da, fr, _ = metar()

    return render_template('form.html', et=et, airplanes=airplanes, met=met, pa=pa, da=da, fr=fr)

@app.route('/data', methods=['POST', 'GET'])
def data():
    airplane_data = {
        "N172SJ": {
            "bew": 1647.52,
            "moment": 64518.62
        },
        "N223BW": {
            "bew": 1646.06,
            "moment": 64793.65
        },
        "N407BW": {
            "bew": 1590.00,
            "moment": 61256.20
        },
        "N574BW": {
            "bew": 1629.40,
            "moment": 63979.60
        },
        "N579BW": {
            "bew": 1632.40,
            "moment": 64091.20
        },
        "N715BW": {
            "bew": 1635.04,
            "moment": 64586.01
        },
        "N721SA": {
            "bew": 1635.27,
            "moment": 64540.67
        },
        "N760BW": {
            "bew": 1650.22,
            "moment": 64633.71
        },
        "N856CP": {
            "bew": 1660.80,
            "moment": 64522.86
        },
        "N829BW": {
            "bew": 1622.40,
            "moment": 64575.70
        },
        "N780SA": {
            "bew": 1656.91,
            "moment": 65130.78
        },
    }

    if request.method == 'GET':
        return redirect('/')
    if request.method == 'POST':
        form_data = request.form
        data = dict(form_data)

        try:
            aircraft = form_data["aircraft"]
        except Exception as e:
            config.error_log(e)
            return render_template("noplane.html")
            
        try:
            resp = toldweb.told_card(airplane_data[aircraft]["bew"], airplane_data[aircraft]["moment"], float(data["pilots"]), float(data["backseat"]), float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
            safe = toldweb.safe_mode(airplane_data[aircraft]["bew"], airplane_data[aircraft]["moment"], float(data["pilots"]), float(data["backseat"]), float(data["baggage1"]), float(data["baggage2"]), data["fuelquant"])
        except Exception as e:
            config.error_log(e)
            return redirect("/error")

        fname = generate_image(resp[1], resp[2])
        user_log(data, request.remote_addr)
        
        runway = form_data["runway"]

        et, met, pa, da, fr, entire_metar = metar()

        try:
            autofill_img = f'<img src="/{autofill.fill(resp[3], entire_metar, runway=runway)}" alt="Autofill">'
        except Exception as e:
            config.error_log(e)
            autofill_img = safe

        return render_template("data.html", lines=resp[0], fname=fname, autofill_img=autofill_img, et=et, met=met, pa=pa, da=da, fr=fr)


########## Link Shortener ##########
@app.route("/set")
def set_link():
    return """<form action="/set-data" method="post"><textarea name="data" cols="50" rows="5"></textarea><br/><input type="submit"/></form>"""

@app.route("/set-data", methods=['POST', 'GET'])
def set_data():
    form_data = dict(request.form)
    with open("data.txt","w") as f:
        f.write(form_data["data"])
    
    return 'Success! <a href="/link">Link</a><br><a href="/set-data">Go Back</a>'

@app.route("/link")
def link():
    regex = r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
    with open("data.txt","r") as f:
        data = f.read()

    if re.search(regex, data):
        return redirect(data)
    else:
        return data
####################################


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
