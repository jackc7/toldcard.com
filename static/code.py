from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def index():
    now = datetime.now()
    dt = now.strftime("%B %d, %Y")
    return render_template("index.html", dt=dt)

if __name__ == "__main__":
    app.run("0.0.0.0", debug=True)
