""" api test """
import time
from flask import Flask

app= Flask(__name__)

@app.route("/time")
def get_current_time():
    """dummy api"""
    return {"time": time.time()}
