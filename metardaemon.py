from flask import Flask
from flask_apscheduler import APScheduler
import requests
import json
import config

app = Flask(__name__)

scheduler = APScheduler()

@app.route('/')
def index():
    # Your existing route code
    pass

def fetch_metar():
    try:
        response = requests.get(f"https://avwx.rest/api/metar/KBOS?token={config.AVWX_TOKEN}", timeout=5)
        response.raise_for_status()
        metar_data = response.json()
        with open("metar.json", "w") as file:
            json.dump(metar_data, file, indent=4)

    except requests.RequestException as e:
        app.logger.error(f"Error fetching METAR data: {e}")

# This will run the fetch_metar function every 120 seconds
@scheduler.task('interval', id='fetch_metar_task', seconds=120, misfire_grace_time=900)
def scheduled_fetch_metar():
    fetch_metar()

if __name__ == '__main__':
    scheduler.init_app(app)
    scheduler.start()
    app.run(host='0.0.0.0', port=80, debug=False)
