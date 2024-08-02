import random
import string
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import logging
import os
from databases import db, Users, Groups, Accounts, Ledger, Bills, Config, GroupMembers
from uuid import uuid4

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

def generate_hex_id(prefix):
    return f"{prefix}{''.join(random.choices('0123456789ABCDEF', k=6))}"

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
            account_email = request.form['accountEmail']
            account_password = request.form['accountUserPassword']
            logging.info(account_email)
            logging.info(account_password)

            user = Users.query.filter_by(email=account_email).first()
            if user and user.password == account_password:
                logging.info("Logged in")
                session['user_id'] = user.user_id
                return redirect(url_for('home'))

            error_message = {"error": "Invalid email or password"}
            return jsonify(error_message), 401

        except Exception as e:
            error_message = {"error": str(e)}
            return jsonify(error_message), 400

    return jsonify({"error": "Invalid request method"}), 405

@app.route('/create', methods=['GET'])
def create():
    return render_template('create_account.html')

@app.route('/create_account', methods=['POST'])
def create_account():
    try:
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        existing_user = Users.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists', 'error')
            return redirect(url_for('create'))

        # Create new user
        new_user_id = generate_hex_id('user')
        new_user = Users(user_id=new_user_id, user_name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully!', 'success')
        return redirect(url_for('confirmation'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating account: {str(e)}', 'error')
        return redirect(url_for('create'))

@app.route('/confirmation', methods=['GET'])
def confirmation():
    return render_template('confirmation.html')

@app.route('/home', methods=['GET'])
def home():
    logging.info("Home Page")
    user_id = session.get('user_id')
    logging.info(f"Session User ID: {user_id}")
    if not user_id:
        return redirect(url_for('index'))

    user = Users.query.get(user_id)
    logging.info(f"User: {user}")

    flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id)\
                              .filter(GroupMembers.user_id == user_id, Groups.group_type == 'flat').all()
    logging.info(f"Flat Groups: {flat_groups}")

    non_flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id)\
                                  .filter(GroupMembers.user_id == user_id, Groups.group_type != 'flat').all()
    logging.info(f"Non-flat Groups: {non_flat_groups}")

    manager_name = "N/A"
    flat_group_names = []
    flat_bills_data = []
    total_flat_owed = 0.0
    if flat_groups:
        manager = Users.query.get(flat_groups[0].manager_id)
        manager_name = manager.user_name.replace('_', ' ').title() if manager else "N/A"
        logging.info(f"Manager Name: {manager_name}")

        flat_group_names = [group.group_name for group in flat_groups]

        for group in flat_groups:
            bills = Bills.query.filter_by(group_id=group.group_id).all()
            for bill in bills:
                logging.info(f"Bill: {bill}")
                num_members = GroupMembers.query.filter_by(group_id=group.group_id).count()
                personal_cost = bill.amount / num_members if num_members > 0 else bill.amount
                total_flat_owed += personal_cost
                flat_bills_data.append({
                    'bill_name': bill.bill_name,
                    'amount': bill.amount,
                    'due_date': bill.start_date,
                    'group_id': bill.group_id,
                    'personal_cost': personal_cost,
                    'paid': "No"
                })

    non_flat_group_names = [group.group_name for group in non_flat_groups]
    non_flat_bills_data = []
    total_non_flat_owed = 0.0
    individual_owed = {}

    for group in non_flat_groups:
        bills = Bills.query.filter_by(group_id=group.group_id).all()
        group_manager = Users.query.get(group.manager_id)
        group_manager_name = group_manager.user_name.replace('_', ' ').title() if group_manager else "N/A"
        group_members = GroupMembers.query.filter_by(group_id=group.group_id).all()
        member_names = [Users.query.get(member.user_id).user_name.replace('_', ' ').title() for member in group_members]

        for bill in bills:
            logging.info(f"Bill: {bill}")
            num_members = len(group_members)
            personal_cost = bill.amount / num_members if num_members > 0 else bill.amount
            total_non_flat_owed += personal_cost

            if group_manager_name not in individual_owed:
                individual_owed[group_manager_name] = 0.0
            individual_owed[group_manager_name] += personal_cost

            non_flat_bills_data.append({
                'bill_name': bill.bill_name,
                'amount': bill.amount,
                'group_manager': group_manager_name,
                'group_members': ', '.join(member_names),
                'personal_cost': personal_cost,
                'paid': "No"
            })

    flat_group_members = Users.query.join(GroupMembers, Users.user_id == GroupMembers.user_id)\
                                    .filter(GroupMembers.group_id.in_([group.group_id for group in flat_groups])).all()
    logging.info(f"Flat Group Members: {flat_group_members}")

    return render_template('home.html', user=user, flat_groups=flat_groups, non_flat_groups=non_flat_groups, flat_group_members=flat_group_members,
                           flat_group_names=flat_group_names, non_flat_group_names=non_flat_group_names,
                           group_message=None, flat_bills=flat_bills_data, total_flat_owed=total_flat_owed,
                           non_flat_bills=non_flat_bills_data, total_non_flat_owed=total_non_flat_owed,
                           individual_owed=individual_owed, manager_name=manager_name)


@app.route('/add_split', methods=['POST'])
def add_split():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    split_type = request.form.get('splitType')
    group_option = request.form.get('groupOption')
    bill_name = request.form.get('billName')
    bill_amount = float(request.form.get('billAmount'))

    if split_type not in ['subgroup', 'event']:
        return jsonify({"error": "Invalid split type"}), 400

    try:
        if group_option == 'existing':
            group_id = request.form.get('selectedGroup')
            group = Groups.query.get(group_id)
            if not group:
                return jsonify({"error": "Group not found"}), 404
        else:
            new_group_name = request.form.get('newGroupName')
            selected_users = request.form.getlist('selectedUsers')
            new_group_id = generate_hex_id('group')
            group = Groups(group_id=new_group_id, group_name=new_group_name, manager_id=user_id, group_type=split_type)
            db.session.add(group)
            db.session.commit()

            for user_id in selected_users:
                group_member = GroupMembers(group_id=group.group_id, user_id=user_id)
                db.session.add(group_member)
            db.session.commit()

        bill = Bills(bill_id=str(uuid4()), bill_name=bill_name, group_id=group.group_id, amount=bill_amount)
        db.session.add(bill)
        db.session.commit()

        return redirect(url_for('home'))

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/individual', methods=['GET'])
def individual():
    logging.info("Individual Page")
    return render_template('individual.html')

@app.route('/account', methods=['GET'])
def account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    user = Users.query.get(user_id)
    return render_template('account.html', user=user)

@app.route('/update_account', methods=['POST'])
def update_account():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Unauthorized access"}), 401

        user = Users.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        previous_password = request.form['previous_password']
        if user.password != previous_password:
            flash('Incorrect previous password. Changes not saved.', 'error')
            return redirect(url_for('account'))

        user.user_name = request.form['name']
        user.email = request.form['email']
        if request.form['new_password']:
            user.password = request.form['new_password']

        db.session.commit()

        flash('Account updated successfully!', 'success')
        return redirect(url_for('account'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating account: {str(e)}', 'error')
        return redirect(url_for('account'))

@app.route('/header', methods=['GET'])
def header():
    logging.info("Header Page")
    return render_template('base.html')

@app.route('/join_flat', methods=['POST'])
def join_flat():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    flat_group_id = request.form.get('flatGroupId')

    try:
        existing_member = GroupMembers.query.filter_by(group_id=flat_group_id, user_id=user_id).first()
        if existing_member:
            flash('You are already a member of this flat group.', 'error')
        else:
            new_member = GroupMembers(group_id=flat_group_id, user_id=user_id)
            db.session.add(new_member)
            db.session.commit()
            flash('Successfully joined the flat group!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error joining flat group: {str(e)}', 'error')

    return redirect(url_for('home'))

@app.route('/create_flat', methods=['POST'])
def create_flat():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    flat_group_name = request.form.get('flatGroupName')

    try:
        new_group_id = generate_hex_id('group')
        new_flat_group = Groups(group_id=new_group_id, group_name=flat_group_name, manager_id=user_id, group_type='flat')
        db.session.add(new_flat_group)
        db.session.commit()

        new_group_member = GroupMembers(group_id=new_group_id, user_id=user_id)
        db.session.add(new_group_member)
        db.session.commit()

        flash('Successfully created the flat group!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating flat group: {str(e)}', 'error')

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
