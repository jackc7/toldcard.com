from PIL import Image, ImageDraw, ImageFont
import requests
import math
import random
import math
import config

def fill(input_data, metar: dict, runway: str):
    def _find_active_runway(metar, runway):
        """
        Input:
        input_data: list
        metar: dict
        runway: str - must be 5, 14, 23, or 32
        
        Returns --
        Active Runway: str
        Runway Length: str
        Headwind Component: str
        Crosswind Component: str
        """
        runway_lengths = {
            "5": "5400",
            "14": "5002",
            "23": "5400",
            "32": "5002"
        }
        if metar["wind_direction"] == None:
            wind_direction = "0"
        else:
            wind_direction = metar["wind_direction"]["value"]


        if runway == "Auto":
            if wind_direction in [10,20,30,40,50,60,70,80,90]:
                runway = "5"
            elif wind_direction in [100,110,120,130,140,150,160,170,180]:
                runway = "14"
            elif wind_direction in [190,200,210,220,230,240,250,260,270]:
                runway = "23"
            elif wind_direction in [280,290,300,310,320,330,340,350,360]:
                runway = "32"
            else:
                return "?", "?", "0", "0"
    
        runway_length = runway_lengths[runway]
        
        wind_speed = metar["wind_speed"]["value"]
        if wind_speed == None:
            wind_speed = 0


        wind_difference = wind_direction-int(runway)*10

        crosswind_component = round(wind_speed * math.sin(math.radians(wind_difference)))
        headwind_component = round(wind_speed * math.cos(math.radians(wind_difference)))

        return runway, runway_length, str(abs(headwind_component)), str(abs(crosswind_component))
        

    def _get_data(metar: dict, headwind: str):
        if headwind == "" or headwind == None:
            headwind = "0"
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

        data = {}

        if metar["temperature"] == None:
            temp = 0
        else:
            temp = metar["temperature"]["value"]
        
        str_temp = repr(int(round(temp,-1)))

        data["takeoff_distance"], data["rate_of_climb"], data["landing_distance"] = _distances(str_temp, headwind)

        try:
            wind = f'{metar["wind_direction"]["repr"]}@{metar["wind_speed"]["repr"]}'
            if metar["wind_gust"] != None:
                wind += "G" + metar["wind_gust"]["repr"]
        except Exception as e:
            config.error_log(e)
            wind = "?"

        data["wind"] = wind

        if metar["visibility"] == None:
            data["visibility"] = "?"
        else:
            data["visibility"] = metar["visibility"]["repr"]

        layers = ""
        for layer in metar["clouds"]:
            layers += layer["repr"] + " "
        data["layers"] = layers[:-1]
        if layers == "":
            data["layers"] = "CLR"

        if metar["temperature"] == None or metar["dewpoint"] == None:
            data["temp_dewpoint"] = '?'
        else:
            data["temp_dewpoint"] = f'{metar["temperature"]["repr"]}/{metar["dewpoint"]["repr"]}'

        if metar["altimeter"] == None:
            data["altimeter"] = "0"
        else:
            data["altimeter"] = f'{metar["altimeter"]["value"]:.2f}'

        #   altitude and density altitude calculations
        pa = (29.92-metar["altimeter"]["value"])*1000 + 79
        data["pressure_altitude"] = str(int(pa))
        data["density_altitude"] = str(int(pa + (120*(metar["temperature"]["value"] - 15))))

        return data


    COLOR = (0, 0, 0)

    def _data_processor(data):
        cleaned = []
        for datum in data:
            if datum[0] == ' ':
                continue
            elif datum[1] in ('95','123'):
                continue
            into_str = tuple(str(x) for i,x in enumerate(datum) if i!=0)
            cleaned.append(into_str)
        
        return cleaned
            
            
    numbers = _data_processor(input_data)
    img = Image.open(f'{config.CWD}/static/told.png')
    d1 = ImageDraw.Draw(img)
    font = ImageFont.truetype(f"{config.CWD}/fonts/Courier Prime.ttf", 20)
    

    xc = 815
    row1 = [(xc, 184),(xc, 212),(xc, 254),(xc, 291),(xc,344),(xc, 373),(xc, 402),(xc, 425),(xc, 466),(xc, 505),(xc, 678),(xc, 700)]
    row2 = [(a+130,b) for a,b in row1]
    row3 = [(a+242,b) for a,b in row1]

    for i, row in enumerate(row1):
        d1.text(row, numbers[i][0], fill=COLOR, font=font)
    for i, row in enumerate(row2):
        d1.text(row, numbers[i][1], fill=COLOR, font=font)
    for i, row in enumerate(row3):
        d1.text(row, numbers[i][2], fill=COLOR, font=font)

    runway, length, headwind, crosswind = _find_active_runway(metar, runway)
    data = _get_data(metar, headwind)

    wxxc = 225
    wx = [("wind", (wxxc, 218)), ("visibility", (wxxc, 242)), ("layers", (wxxc, 264)), ("temp_dewpoint", (wxxc,288)), ("altimeter", (wxxc,312)), ("density_altitude", (wxxc,358)), ("pressure_altitude", (wxxc,380))]
    for key, coords in wx:
        d1.text(coords, data[key], fill=COLOR, font=font)

    # Runway, length, headwind, crosswind
    d1.text((wxxc, 335), runway,fill=COLOR, font=font)
    d1.text((wxxc, 405), length, fill=COLOR, font=font)
    d1.text((wxxc, 429), headwind, fill=COLOR, font=font)
    d1.text((wxxc, 451), crosswind, fill=COLOR, font=font)

    
    va = lambda tow: str(round(99*math.sqrt(tow/2450), 1))

    maneuvering_speed = va(input_data[11][1])
    d1.text((198, 657), maneuvering_speed, fill=COLOR, font=font)

    takeoff = data["takeoff_distance"]

    rollto, fiftyfoot = takeoff

    # Amount to multiply distances for headwind
    wind_factor = 1.0 - math.floor(float(headwind)/9)/10
    rollto *= wind_factor
    fiftyfoot *= wind_factor


    d1.text((244, 547), str(round(rollto)), fill=COLOR, font=font)
    d1.text((458, 547), str(round(fiftyfoot)), fill=COLOR, font=font)

    d1.text((193, 607), str(data["rate_of_climb"]), fill=COLOR, font=font)

    landing = data["landing_distance"]
    rolll, fiftyfoot = landing
    
    rolll *= wind_factor
    fiftyfoot *= wind_factor


    d1.text((248, 632), str(round(rolll)), fill=COLOR, font=font)
    d1.text((457, 632), str(round(fiftyfoot)), fill=COLOR, font=font)

    matd = round((rollto + rolll) * 1.3)
    d1.text((222, 568), str(matd), fill=COLOR, font=font)
    
    imname = f"{str(random.randint(0,1000000000))}c.png"
    impath = f"{config.CWD}/static/tmp/" + imname
    webpath = "static/tmp/" + imname
    img.save(impath)

    return webpath
