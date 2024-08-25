import random
import string
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, make_response
import logging
import os
from databases import db, Users, Groups, Ledger, Bills, Config, GroupMembers, Notifications
from uuid import uuid4
import datetime
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

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

    if 'user_id' in session:
        return redirect(url_for('home'))

    remember_me = request.cookies.get('rememberMe')
    if remember_me and remember_me == 'true' and 'user_id' in session:
        return redirect(url_for('home'))

    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        try:
            account_email = request.form['accountEmail']
            account_password = request.form['accountUserPassword']
            remember_me = request.form.get('rememberMe')

            logging.info(account_email)
            logging.info(account_password)

            user = Users.query.filter_by(email=account_email).first()
            if user and user.password == account_password:
                logging.info("Logged in")
                session['user_id'] = user.user_id

                resp = make_response(redirect(url_for('home')))
                if remember_me:
                    resp.set_cookie('rememberMe', 'true', max_age=30*24*60*60)
                else:
                    resp.set_cookie('rememberMe', 'false', max_age=30*24*60*60)
                return resp

            # If login fails, render the login page with an error message
            flash('Invalid email or password', 'error')
            return render_template('login.html')

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return render_template('login.html')

    return render_template('login.html')

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

    flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
        .filter(GroupMembers.user_id == user_id, Groups.group_type == 'flat').all()
    logging.info(f"Flat Groups: {flat_groups}")

    non_flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
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

        # Group bills by name, amount, and group
        grouped_bills = defaultdict(list)
        for group in flat_groups:
            bills = Bills.query.filter_by(group_id=group.group_id).all()
            group.bills = bills  # Attach bills to the group for template use
            for bill in bills:
                grouped_bills[(bill.bill_name, bill.amount, bill.group_id)].append(bill)

        # Process each group of bills to include only the next upcoming and past bills
        for (bill_name, amount, group_id), bills in grouped_bills.items():
            bills.sort(key=lambda x: x.start_date)
            next_bill = None
            current_date = datetime.now()
            for bill in bills:
                if bill.start_date and bill.start_date > current_date:
                    next_bill = bill
                    break

            for bill in bills:
                if next_bill is None or bill.start_date <= next_bill.start_date:
                    num_members = GroupMembers.query.filter_by(group_id=bill.group_id).count()
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
        group.bills = bills  # Attach bills to the group for template use
        group_manager = Users.query.get(group.manager_id)
        group_manager_name = group_manager.user_name.replace('_',
                                                             ' ').title() if group_manager else "N/A"
        group_members = GroupMembers.query.filter_by(group_id=group.group_id).all()
        member_names = [Users.query.get(member.user_id).user_name.replace('_', ' ').title() for
                        member in group_members]

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

    flat_group_members = Users.query.join(GroupMembers, Users.user_id == GroupMembers.user_id) \
        .filter(GroupMembers.group_id.in_([group.group_id for group in flat_groups])).all()
    logging.info(f"Flat Group Members: {flat_group_members}")

    other_flat_members = [member for member in flat_group_members if member.user_id != user_id]

    # Get groups where the user is the manager
    managed_flat_groups = Groups.query.filter_by(manager_id=user_id, group_type='flat').all()
    managed_non_flat_groups = Groups.query.filter(
        Groups.manager_id == user_id, Groups.group_type != 'flat'
    ).all()

    return render_template('home.html', user=user, flat_groups=flat_groups,
                           non_flat_groups=non_flat_groups,
                           flat_group_members=flat_group_members,
                           other_flat_members=other_flat_members,
                           flat_group_names=flat_group_names,
                           non_flat_group_names=non_flat_group_names,
                           group_message=None, flat_bills=flat_bills_data,
                           total_flat_owed=total_flat_owed,
                           non_flat_bills=non_flat_bills_data,
                           total_non_flat_owed=total_non_flat_owed,
                           individual_owed=individual_owed, manager_name=manager_name,
                           managed_flat_groups=managed_flat_groups,
                           managed_non_flat_groups=managed_non_flat_groups)

@app.route('/create_group', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    group_name = request.form.get('newGroupName')
    split_type = request.form.get('splitType')
    selected_users = request.form.getlist('selectedUsers')

    try:
        new_group_id = generate_hex_id('group')
        group = Groups(group_id=new_group_id, group_name=group_name, manager_id=user_id, group_type=split_type)
        db.session.add(group)
        db.session.commit()

        for selected_user_id in selected_users:
            group_member = GroupMembers(group_id=new_group_id, user_id=selected_user_id)
            db.session.add(group_member)

        db.session.commit()

        flash('Group created successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating group: {str(e)}', 'error')

    return redirect(url_for('home'))

@app.route('/create_bill', methods=['POST'])
def create_bill():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    group_id = request.form.get('selectedGroup')
    bill_name = request.form.get('billName')
    bill_amount_str = request.form.get('billAmount')
    start_date_str = request.form.get('startDate', None)
    reoccurring = request.form.get('reoccurring') == 'on'
    frequency = request.form.get('frequency', None)
    reoccurrences_str = request.form.get('reoccurrences', '0')
    custom_days_str = request.form.get('customDays', '0')

    try:
        bill_amount = float(bill_amount_str)
    except ValueError:
        flash('Invalid bill amount', 'error')
        return redirect(url_for('home'))

    try:
        reoccurrences = int(reoccurrences_str)
    except ValueError:
        reoccurrences = 0

    try:
        custom_days = int(custom_days_str)
    except ValueError:
        custom_days = 0

    try:
        group = Groups.query.get(group_id)
        if not group:
            flash('Group not found', 'error')
            return redirect(url_for('home'))

        # Convert start_date_str to a datetime object
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid start date format. Use YYYY-MM-DD.', 'error')
                return redirect(url_for('home'))
        else:
            start_date = None

        # Add the initial bill
        bill_id = generate_hex_id('bill')
        bill = Bills(bill_id=bill_id, bill_name=bill_name, group_id=group.group_id, amount=bill_amount, start_date=start_date)
        db.session.add(bill)

        # Handle recurring bills
        if reoccurring:
            for i in range(1, reoccurrences + 1):
                if frequency == 'weekly':
                    next_date = start_date + timedelta(weeks=i)
                elif frequency == 'monthly':
                    month = start_date.month - 1 + i
                    year = start_date.year + month // 12
                    month = month % 12 + 1
                    day = min(start_date.day, calendar.monthrange(year, month)[1])
                    next_date = datetime(year=year, month=month, day=day)
                elif frequency == 'custom':
                    next_date = start_date + timedelta(days=custom_days * i)
                else:
                    continue

                bill_id = generate_hex_id('bill')
                bill = Bills(bill_id=bill_id, bill_name=bill_name, group_id=group.group_id, amount=bill_amount, start_date=next_date)
                db.session.add(bill)

        db.session.commit()

        flash('Bill created successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating bill: {str(e)}', 'error')

    return redirect(url_for('home'))

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
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('rememberMe', 'false', expires=0)
    return resp

@app.route('/notifications', methods=['GET'])
def notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    # Retrieve the user and their notifications
    user = Users.query.get(user_id)
    notifications = Notifications.query.filter_by(user_id=user_id).all()

    # Render the template with the user's data and their notifications
    return render_template('notifications.html', user=user, notifications=notifications)

@app.route('/paid_bill', methods=['POST'])
def paid_bill():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    try:
        user_id = session['user_id']
        bill_id = request.form.get('selectedBill')
        logging.info(f"User ID: {user_id}, Bill ID: {bill_id}")

        # Query the bill using bill_id
        bill = Bills.query.get(bill_id)
        if not bill:
            return jsonify({"error": "Bill not found"}), 404

        # Find the manager of the group this bill belongs to
        group = Groups.query.get(bill.group_id)
        if not group:
            return jsonify({"error": "Group not found"}), 404

        manager_id = group.manager_id

        # Generate a new notification
        notif_id = generate_hex_id('notif')
        new_notification = Notifications(
            notif_id=notif_id,
            user_id=manager_id,
            sender_id=user_id,
            bill_id=bill.bill_id,
            notif_type='confirmation',
            content='',  # Content can be added later
            read=False
        )

        # Add the notification to the database
        db.session.add(new_notification)
        db.session.commit()

        return jsonify({"success": "Notification sent successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/group_details', methods=['GET'])
def group_details():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized access"}), 401

    user_id = session['user_id']
    try:
        flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
            .filter(GroupMembers.user_id == user_id, Groups.group_type == 'flat').all()

        non_flat_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
            .filter(GroupMembers.user_id == user_id, Groups.group_type != 'flat').all()

        all_groups = flat_groups + non_flat_groups

        group_info = []
        for group in all_groups:
            is_manager = group.manager_id == user_id
            members = GroupMembers.query.filter_by(group_id=group.group_id).all()
            members_count = len(members)
            member_emails = [Users.query.get(member.user_id).email for member in members]
            bills_count = Bills.query.filter_by(group_id=group.group_id).count()

            group_info.append({
                'group_id': group.group_id,
                'group_name': group.group_name,
                'members_count': members_count,
                'member_emails': member_emails,
                'is_manager': is_manager,
                'bills_count': bills_count
            })

        return jsonify(group_info)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
