"""Calculations for TOLD Card"""

def told_card(empty_weight=0, empty_moment=0, pilot_weight=0, backseat_weight=0, baggage1=0, baggage2=0, fuel_quantity="0"):
    if fuel_quantity == "":
        fuel_quantity = 318
    else:
        fuel_quantity = float(fuel_quantity)

    data = {
        "airplane": {
            "weight": 0,
            "arm": 0,
            "moment": 0,
        },

        "pilot": {
            "weight": 0,
            "arm": 37
        },

        "backseat": {
            "weight": 0,
            "arm": 73
        },

        "baggage1": {
            "weight": 0,
            "arm": 95
        },

        "baggage2": {
            "weight": 0,
            "arm": 123
        }
    }

    data["airplane"]["weight"] = empty_weight
    data["airplane"]["moment"] = empty_moment

    if not pilot_weight == "":
        data["pilot"]["weight"] = float(pilot_weight)

    if not backseat_weight == "":
        data["backseat"]["weight"] = float(backseat_weight)

    if not baggage1 == "":
        data["baggage1"]["weight"] = float(baggage1)

    if not baggage2 == "":
        data["baggage2"]["weight"] = float(baggage2)

    # Zero fuel calculations
    weight_count = 0
    moment_count = 0
    for key, nums in data.items():
        weight = nums["weight"]
        weight_count += weight

        moment = nums["weight"] * nums["arm"]
        if key == "airplane":
            moment = nums["moment"]
        moment_count += moment


    fuel_data = {
        "zerofuel": {
            "weight": weight_count,
            "arm": moment_count/weight_count,
            "moment": moment_count
        },

        "fuel": {
            "weight": fuel_quantity,
            "arm": 48
        }
    }


    # Fuel Calculations
    if not fuel_quantity == "":
        data["pilot"]["weight"] = float(pilot_weight)

    # Find ramp weight (zero fuel + fuel weight) 
    fuel_weight_count = 0
    fuel_moment_count = 0
    for key, nums in fuel_data.items():
        fuel_weight = nums["weight"]
        fuel_weight_count += fuel_weight

        fuel_moment = nums["weight"]*nums["arm"]
        fuel_moment_count += fuel_moment

    takeoff_weight = round(fuel_weight_count - 7, 2)
    takeoff_moment = round(fuel_moment_count - 336, 2)
    takeoff_arm = round(takeoff_moment/takeoff_weight, 2)

    line_by_line = [
        (" ","WEIGHT","ARM","MOMENT"),
        ("Basic Empty Weight",round(data["airplane"]["weight"],2),round(data["airplane"]["moment"]/data["airplane"]["weight"],2),round(data["airplane"]["moment"] ,2)),
        ("Pilot and Passenger",round(data["pilot"]["weight"],2),round(data["pilot"]["arm"],2),round(data["pilot"]["weight"]*data["pilot"]["arm"],2)),
        ("Rear Passengers",round(data["backseat"]["weight"],2),round(data["backseat"]["arm"],2),round(data["backseat"]["weight"]*data["backseat"]["arm"],2)),
        ("Baggage Area 1",round(data["baggage1"]["weight"],2),round(data["baggage1"]["arm"],2),round(data["baggage1"]["weight"]*data["baggage1"]["arm"],2)),
        ("Baggage Area 2",round(data["baggage2"]["weight"],2),round(data["baggage2"]["arm"],2),round(data["baggage2"]["weight"]*data["baggage2"]["arm"],2)),
        ("Zero Fuel Weight",round(weight_count, 2),round(moment_count/weight_count, 2),round(moment_count, 2)),
        (" "," "," "," "),
        ("Fuel",round(fuel_data["fuel"]["weight"], 2),round(fuel_data["fuel"]["arm"], 2),round(fuel_data["fuel"]["weight"]*fuel_data["fuel"]["arm"], 2)),
        ("Ramp Weight",round(fuel_data["fuel"]["weight"]+weight_count, 2),round((fuel_data["zerofuel"]["moment"]+fuel_data["fuel"]["weight"]*fuel_data["fuel"]["arm"])/(fuel_data["fuel"]["weight"]+weight_count), 2),round(fuel_data["zerofuel"]["moment"]+fuel_data["fuel"]["weight"]*fuel_data["fuel"]["arm"],2)),
        ("Start/Taxi/Run-up","-7","48","-336"),
        ("Takeoff Weight",takeoff_weight,takeoff_arm,takeoff_moment),
        (" "," "," "," "),
        ("Fuel Loss","-72","48","-3456"),
        ("Landing Weight", round(takeoff_weight-72, 2), round((takeoff_moment-3456)/(takeoff_weight-72),2),takeoff_moment-3456),
    ]

    final = []
    for line in line_by_line:
        final.append("<code><pre>%25s %12s %12s %12s</pre></code>" % line)
        
    return final, takeoff_weight, takeoff_arm, line_by_line

def safe_mode(empty_weight=0, empty_moment=0, pilot_weight=0, backseat_weight=0, baggage1=0, baggage2=0, fuel_quantity="0"):
    output = told_card(empty_weight, empty_moment, pilot_weight, backseat_weight, baggage1, baggage2, fuel_quantity)
    return "<code><pre>Image generation failed</pre></code>" + "".join(output[0])
