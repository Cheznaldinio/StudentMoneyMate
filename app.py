from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import logging
import random

from datetime import datetime, timedelta
from sqlalchemy import or_, and_
import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
                              'postgresql://postgres:postgres@localhost/StudentMoneyMate'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'your_secret_key'
db.init_app(app)

@app.route('/', methods=['GET'])
def index():
    logging.info("Entry Point")
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)

print("hello_world")
