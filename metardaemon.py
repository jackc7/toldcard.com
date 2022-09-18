import requests 
import json
import time
import config 

def get_metar():
    r = requests.get(f"https://avwx.rest/api/metar/KEWB?token={config.AVWX_TOKEN}", timeout=5)
    metar = r.json()

    with open("metar.json", "w") as f:
        json.dump(metar, f, indent=4)
	
if __name__ == "__main__":
    while True:
        try:    
            get_metar()
            time.sleep(120)
        except:
            time.sleep(120)
