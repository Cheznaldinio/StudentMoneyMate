from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import logging
import random
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, text
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

class Users(db.Model):
    userid = db.Column(db.String(255), primary_key=True, nullable=True, server_default=text('NULL::character varying'))
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    password = db.Column(db.String(255))
    admin = db.Column(db.Boolean, default=False)

    def __str__(self):
        return f"User: {self.userid}, {self.username}, {self.email}, {self.password}, {self.admin}"

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/', methods=['GET'])
def index():
    logging.info("Entry Point")
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():

    if request.method == 'POST':
        try:
            # Retrieve form data using request.form
            account_email = request.form['accountEmail']
            account_password = request.form['accountUserPassword']
            logging.info(account_email)
            logging.info(account_password)
            # Query the database for the user with the provided email
            user = Users.query.filter_by(email=account_email).first()

            # Check if the user exists and the password is correct
            if user and user.password == account_password:
      #
      # Redirect to the home page if credentials are correct
                logging.info("Logged in")
                session['user_id'] = user.userid
                return redirect(url_for('home'))

            # Return an error message if credentials are incorrect
            error_message = {"error": "Invalid email or password"}
            return jsonify(error_message), 401

        except Exception as e:
            error_message = {"error": str(e)}
            return jsonify(error_message), 400  # Respond with an error message if there's an issue

    # Add an additional response if the request method is not 'POST'
    return jsonify({"error": "Invalid request method"}), 405


@app.route('/home', methods=['GET'])
def home():
    logging.info("Home Page")
    return render_template('home.html')

@app.route('/individual', methods=['GET'])
def individual():
    logging.info("Individual Page")
    return render_template('individual.html')

@app.route('/account', methods=['GET'])
def account():
    logging.info("Account Page")
    return render_template('account.html')

@app.route('/header', methods=['GET'])
def header():
    logging.info("Header Page")
    return render_template('header.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

print("hello_world")
