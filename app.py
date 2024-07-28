from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import logging
import os
from databases import db, Users, Groups, Accounts, Ledger, Bills, Config, GroupMembers

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get the base directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Initialize the Flask application
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'your_secret_key'
db.init_app(app)

# Ensure the database tables are created
with app.app_context():
    db.create_all()

@app.route('/', methods=['GET'])
def index():
    logging.info("Entry Point")
    all_group_members = GroupMembers.query.all()
    if not all_group_members:
        logging.info("No members found")
    else:
        for member in all_group_members:
            logging.info(member)
    all_users = Users.query.all()
    if not all_users:
        logging.info("No users found")
    else:
        for user in all_users:
            logging.info(user)
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
                # Redirect to the home page if credentials are correct
                logging.info("Logged in")
                session['user_id'] = user.user_id
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
    user_id = session.get('user_id')
    logging.info(f"Session User ID: {user_id}")
    if not user_id:
        return redirect(url_for('index'))

    # Check if the user exists
    user = Users.query.get(user_id)
    logging.info(f"User: {user}")

    # Query group memberships
    group_memberships = GroupMembers.query.filter_by(user_id=user_id).all()
    logging.info(f"Group Memberships: {group_memberships}")

    group_ids = [membership.group_id for membership in group_memberships]
    logging.info(f"Group IDs: {group_ids}")

    groups = Groups.query.filter(Groups.group_id.in_(group_ids)).all()
    logging.info(f"Groups: {groups}")

    group_names = [group.group_name for group in groups]
    logging.info(f"Group Names: {group_names}")

    if not group_names:
        group_message = "You are not a member of any groups."
    else:
        group_message = None

    return render_template('home.html', user=user, group_names=group_names, group_message=group_message)


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
    app.run(debug=True)

print("hello_world")

