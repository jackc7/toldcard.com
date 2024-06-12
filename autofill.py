from PIL import Image, ImageDraw, ImageFont
import math
import config
import geomag

COLOR = (0, 0, 0)
XC = 815
WXC = 225
FONT = ImageFont.truetype(f"{config.CWD}/static/fonts/Courier Prime.ttf", 20)
IMG_PATH = f'{config.CWD}/static/told.png'

def _find_active_runway(metar: dict, runway: str, all_runways: list, geo_coords: tuple):
    try:
        wind_direction = metar.get("wind_direction", {}).get("value", "0")
        wind_speed = metar.get("wind_speed", {}).get("value", 0)
    except AttributeError:
        if runway == "Auto":
            return "?", "?", "0", "0"
        else:
            return runway, "0", "0"

    if geo_coords == ():
        magnetic_variation = -14
    else:
        magnetic_variation = (round(geomag.declination(*geo_coords)))
        
    # Modulo ensures wind remains in 0-360 range
    wind_direction = (int(wind_direction) - magnetic_variation) % 360
        
    if runway == "Auto":
        runway_orientations = {runway: int(runway)*10 for runway in all_runways}            
        if wind_direction is None:
            return "?", "0", "0"
        else:
            differences = {runway: abs(wind_direction - orientation) for runway, orientation in runway_orientations.items()}
            runway = min(differences, key=differences.get)
    
    if metar.get("wind_direction", {}).get("repr", "") == "VRB":
        return runway, "0", "0"

    # Adjust wind_difference calculation to maintain directional information
    wind_difference = wind_direction - int(runway) * 10
    wind_difference = wind_difference % 360  # Ensures wind_difference is within [0, 360)
    if wind_difference > 180:  # Use complementary angle if greater than 180
        wind_difference = 360 - wind_difference

    crosswind_component = round(wind_speed * math.sin(math.radians(wind_difference)))
    headwind_component = round(wind_speed * math.cos(math.radians(wind_difference)))
    
    return runway, str(crosswind_component), str(headwind_component) 

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
    temp = int(math.ceil(metar.get("temperature", {}).get("value", 0) / 10)) * 10
    to_distance, roc, land_distance = _distances(str(temp), headwind)

    try:
        wind = f'{metar.get("wind_direction", {}).get("repr", "?")}@{metar.get("wind_speed", {}).get("repr", "?")}'
        wind += "G" + metar["wind_gust"]["repr"] if metar.get("wind_gust") else ""
    except AttributeError:
        wind = "?"

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

    # Altitude and density altitude calculations
    pa = (29.92 - metar.get("altimeter", {}).get("value", 0)) * 1000 + 79
    data["pressure_altitude"] = str(int(pa))
    data["density_altitude"] = str(int(pa + (120 * (metar.get("temperature", {}).get("value", 0) - 15))))

    return data

def round_num(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        if value * 10 == int(value * 10):
            return "{:.1f}".format(value)
        
        return "{:.2f}".format(round(value, 2))

def fill(toldcard: object, metar: dict, runway: str, all_runways: list, geo_coords: tuple):
    img = Image.open(IMG_PATH)
    d1 = ImageDraw.Draw(img)

    y_coords = [184, 212, 254, 291, 344, 373, 402, 425, 466, 505, 678, 700]
    results = toldcard.sort()
    for y, numbers in zip(y_coords, results):
        d1.text((XC, y), round_num(numbers["weight"]), fill=COLOR, font=FONT)
        d1.text((XC+130, y), round_num(numbers["arm"]), fill=COLOR, font=FONT)
        d1.text((XC+242, y), round_num(numbers["moment"]), fill=COLOR, font=FONT)

    runway, crosswind, headwind = _find_active_runway(metar, runway, all_runways, geo_coords)
    data = _get_data(metar, headwind)

    wx = [("wind", 218), ("visibility", 242), ("layers", 264), ("temp_dewpoint",288), ("altimeter",312), ("density_altitude",358), ("pressure_altitude",380)]
    for key, y in wx:
        d1.text((WXC, y), data[key], fill=COLOR, font=FONT)

    # Runway, headwind, crosswind
    runways_info = [("Runway", runway, (WXC, 335)), ("Headwind", headwind, (WXC, 429)), ("Crosswind", crosswind, (WXC, 451))]
    for name, value, coords in runways_info:
        d1.text(coords, value, fill=COLOR, font=FONT)

    maneuvering_speed = str(round(99 * math.sqrt(toldcard.takeoff_weight["weight"] / 2450), 1))
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
