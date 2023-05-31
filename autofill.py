from PIL import Image, ImageDraw, ImageFont
import os
import math
import random
import config

# Global Constants
COLOR = (0, 0, 0)
XC = 815
WXC = 225
RUNWAY_LENGTHS = {"5": "5400", "14": "5002", "23": "5400", "32": "5002"}
RUNWAY_DIRS = ['32', '5', '14', '23']
FONT = ImageFont.truetype(f"{config.CWD}/fonts/Courier Prime.ttf", 20)
IMG_PATH = f'{config.CWD}/static/told.png'
RUNWAY_AUTO = [10,20,30,40,50,60,70,80,90]

def fill(input_data, metar: dict, runway: str):
    def _find_active_runway(metar, runway):
        wind_direction = metar.get("wind_direction", {}).get("value", "0")
        wind_speed = metar.get("wind_speed", {}).get("value", 0)

        if runway == "Auto":
            runway_orientations = {"5": 50, "14": 140, "23": 230, "32": 320}
            magnetic_variation = -14
            if wind_direction is None:
                return "?", "?", "0", "0"
            else:
                wind_direction = int(wind_direction) + magnetic_variation
                differences = {runway: abs(wind_direction - orientation) for runway, orientation in runway_orientations.items()}
                runway = min(differences, key=differences.get)
    
        runway_length = RUNWAY_LENGTHS[runway]
        wind_difference = abs(wind_direction - int(runway) * 10)
        wind_difference = min(wind_difference, 360 - wind_difference)

        crosswind_component = str(abs(round(wind_speed * math.sin(math.radians(wind_difference)))))
        headwind_component = str(abs(round(wind_speed * math.cos(math.radians(wind_difference)))))

        return runway, runway_length, crosswind_component, headwind_component 

    def _distances(temp: str, headwind: str):
        takeoff = { "0": [845,1510], "10": [910,1625], "20": [980,1745], "30": [1055,1875], "40": [1135,2015]}
        rate_of_climb = {"-20": 830, "-10": 800, "0": 770, "10": 740, "20": 705, "30": 675}
        landing = { "0": [525,1250], "10": [540,1280], "20": [560,1310], "30": [580,1340], "40": [600,1370]}

        if int(temp) < 0:
            temp = "0" 

        # Wind Calculations                
        wind = int(headwind)

        reduction_factor = round(1 - math.floor(wind/9) / 10)
        
        to_distance = [reduction_factor * x for x in takeoff[temp]]
        roc = rate_of_climb[temp]
        land_distance = [reduction_factor * x for x in landing[temp]]

        return to_distance, roc, land_distance

    def _get_data(metar: dict, headwind: str):
        temp = int(round(metar.get("temperature", {}).get("value", 0), -1))
        to_distance, roc, land_distance = _distances(str(temp), headwind)
        wind = f'{metar.get("wind_direction", {}).get("repr", "?")}@{metar.get("wind_speed", {}).get("repr", "?")}'
        wind += "G" + metar["wind_gust"]["repr"] if metar.get("wind_gust") else ""

        data = {
            "takeoff_distance": to_distance,
            "rate_of_climb": roc,
            "landing_distance": land_distance,
            "wind": wind,
            "visibility": metar.get("visibility", {}).get("repr", "?"),
            "layers": " ".join(layer["repr"] for layer in metar.get("clouds", [])) or "CLR",
            "temp_dewpoint": f'{metar.get("temperature", {}).get("repr", "?")}/{metar.get("dewpoint", {}).get("repr", "?")}',
            "altimeter": f'{metar.get("altimeter", {}).get("value", 0):.2f}',
        }

        #   altitude and density altitude calculations
        pa = (29.92 - metar.get("altimeter", {}).get("value", 0)) * 1000 + 79
        data["pressure_altitude"] = str(int(pa))
        data["density_altitude"] = str(int(pa + (120 * (metar.get("temperature", {}).get("value", 0) - 15))))

        return data

    def _data_processor(data):
        return [tuple(str(x) for i,x in enumerate(datum) if i!=0) for datum in data if datum[0] != ' ' and datum[1] not in ('95','123')]

    numbers = _data_processor(input_data)
    img = Image.open(IMG_PATH)
    d1 = ImageDraw.Draw(img)

    y_coords = [184, 212, 254, 291, 344, 373, 402, 425, 466, 505, 678, 700]
    for i, y in enumerate(y_coords):
        d1.text((XC, y), numbers[i][0], fill=COLOR, font=FONT)
        d1.text((XC+130, y), numbers[i][1], fill=COLOR, font=FONT)
        d1.text((XC+242, y), numbers[i][2], fill=COLOR, font=FONT)

    runway, length, crosswind, headwind = _find_active_runway(metar, runway)
    data = _get_data(metar, headwind)

    wx = [("wind", 218), ("visibility", 242), ("layers", 264), ("temp_dewpoint",288), ("altimeter",312), ("density_altitude",358), ("pressure_altitude",380)]
    for key, y in wx:
        d1.text((WXC, y), data[key], fill=COLOR, font=FONT)

    # Runway, length, headwind, crosswind
    runways_info = [("Runway", runway, (WXC, 335)), ("Length", length, (WXC, 405)), ("Headwind", headwind, (WXC, 429)), ("Crosswind", crosswind, (WXC, 451))]
    for name, value, coords in runways_info:
        d1.text(coords, value, fill=COLOR, font=FONT)

    maneuvering_speed = str(round(99 * math.sqrt(input_data[11][1] / 2450), 1))
    d1.text((198, 657), maneuvering_speed, fill=COLOR, font=FONT)

    # Wind Calculations
    wind_factor = 1.0 - math.floor(float(headwind)/9)/10
    takeoff = [wind_factor * x for x in data["takeoff_distance"]]
    d1.text((244, 547), str(round(takeoff[0])), fill=COLOR, font=FONT)
    d1.text((458, 547), str(round(takeoff[1])), fill=COLOR, font=FONT)

    d1.text((193, 607), str(data["rate_of_climb"]), fill=COLOR, font=FONT)

    landing = [wind_factor * x for x in data["landing_distance"]]
    d1.text((248, 632), str(round(landing[0])), fill=COLOR, font=FONT)
    d1.text((457, 632), str(round(landing[1])), fill=COLOR, font=FONT)

    matd = round((takeoff[0] + landing[0]) * 1.3)
    d1.text((222, 568), str(matd), fill=COLOR, font=FONT)
    
    return img
