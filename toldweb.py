"""Calculations for TOLD Card"""

class ToldCard:
    def __init__(self, empty_weight=0, empty_moment=0, pilot_weight=0, backseat_weight=0, baggage1=0, baggage2=0, fuel_quantity="0"):
        # Convert inputs to appropriate types
        self.empty_weight = float(empty_weight)
        self.empty_moment = float(empty_moment)
        pilot_weight = float(pilot_weight) if pilot_weight else 0
        backseat_weight = float(backseat_weight) if backseat_weight else 0
        baggage1 = float(baggage1) if baggage1 else 0
        baggage2 = float(baggage2) if baggage2 else 0
        fuel_quantity = float(fuel_quantity) if fuel_quantity else 318

        # Dictionaries to hold calculated values
        self.basic_empty = {}
        self.pilot_and_passenger = {}
        self.rear_passengers = {}
        self.baggage_area_1 = {}
        self.baggage_area_2 = {}
        self.zero_fuel_weight = {}
        self.fuel = {}
        self.ramp_weight = {}
        self.start_taxi_runup = {}
        self.takeoff_weight = {}
        self.fuel_burn = {}
        self.landing_weight = {}

        # Calculate the values
        self._calculate(pilot_weight, backseat_weight, baggage1, baggage2, fuel_quantity)

    def _calculate(self, pilot_weight, backseat_weight, baggage1, baggage2, fuel_quantity):
        # Initial data setup
        data = {
            "airplane": {"weight": self.empty_weight, "arm": 0, "moment": self.empty_moment},
            "pilot": {"weight": pilot_weight, "arm": 37},
            "backseat": {"weight": backseat_weight, "arm": 73},
            "baggage1": {"weight": baggage1, "arm": 95},
            "baggage2": {"weight": baggage2, "arm": 123}
        }

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
            "zerofuel": {"weight": weight_count, "arm": moment_count / weight_count, "moment": moment_count},
            "fuel": {"weight": fuel_quantity, "arm": 48}
        }

        # Fuel Calculations
        fuel_weight_count = fuel_data["fuel"]["weight"]
        fuel_moment_count = fuel_data["fuel"]["weight"] * fuel_data["fuel"]["arm"]

        takeoff_weight = fuel_weight_count + weight_count
        takeoff_arm = (fuel_data["zerofuel"]["moment"] + fuel_moment_count) / takeoff_weight
        takeoff_moment = fuel_data["zerofuel"]["moment"] + fuel_moment_count

        # Assigning calculated values to class attributes
        self.basic_empty = {"weight": self.empty_weight, "arm": self.empty_moment / self.empty_weight, 
                            "moment": self.empty_moment}
        self.pilot_and_passenger = {"weight": data["pilot"]["weight"], "arm": data["pilot"]["arm"],
                                    "moment": data["pilot"]["weight"] * data["pilot"]["arm"]}
        self.rear_passengers = {"weight": data["backseat"]["weight"], "arm": data["backseat"]["arm"],
                                "moment": data["backseat"]["weight"] * data["backseat"]["arm"]}
        self.baggage_area_1 = {"weight": data["baggage1"]["weight"], "arm": data["baggage1"]["arm"],
                               "moment": data["baggage1"]["weight"] * data["baggage1"]["arm"]}
        self.baggage_area_2 = {"weight": data["baggage2"]["weight"], "arm": data["baggage2"]["arm"],
                               "moment": data["baggage2"]["weight"] * data["baggage2"]["arm"]}
        self.zero_fuel_weight = {"weight": weight_count, "arm": moment_count / weight_count,
                                 "moment": moment_count}
        self.fuel = {"weight": fuel_data["fuel"]["weight"], "arm": fuel_data["fuel"]["arm"],
                     "moment": fuel_data["fuel"]["weight"] * fuel_data["fuel"]["arm"]}
        self.ramp_weight = {"weight": takeoff_weight, "arm": takeoff_arm, 
                            "moment": takeoff_moment}
        self.start_taxi_runup = {"weight": "-7", "arm": "48", 
                                 "moment": "-336"}
        self.takeoff_weight = {"weight": takeoff_weight - 7, "arm": (takeoff_moment - 336) / (takeoff_weight - 7), 
                               "moment": takeoff_moment - 336}
        self.fuel_burn = {"weight": "-72", "arm": "48", 
                          "moment": "-3456"}
        self.landing_weight = {"weight": self.takeoff_weight["weight"] - 72, "arm": (self.takeoff_weight["moment"] - 3456) / (self.takeoff_weight["weight"] - 72),
                               "moment": self.takeoff_weight["moment"] - 3456}

    def sort(self):
        return [
            self.basic_empty,
            self.pilot_and_passenger,
            self.rear_passengers,
            self.baggage_area_1,
            self.baggage_area_2,
            self.zero_fuel_weight,
            self.fuel,
            self.ramp_weight,
            self.start_taxi_runup,
            self.takeoff_weight,
            self.fuel_burn,
            self.landing_weight
        ]
