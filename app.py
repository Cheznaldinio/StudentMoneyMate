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
from services.group_services import GroupService
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
                session['user_name'] = user.user_name
                session['user_email'] = user.email

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
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = Users.query.get(user_id)

    # Get the current date
    current_date = datetime.now()

    # Calculate date ranges
    two_weeks_from_now = current_date + timedelta(weeks=2)
    one_month_from_now = current_date + timedelta(weeks=6)

    # Fetch the ledger entries for the logged-in user
    current_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.due_date <= two_weeks_from_now,
        Ledger.status == 'owe'
    ).all()

    upcoming_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.due_date > two_weeks_from_now,
        Ledger.due_date <= one_month_from_now,
        Ledger.status == 'owe'
    ).all()

    paid_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.status == 'paid'
    ).order_by(Ledger.due_date.desc()).all()

    # Fetch future bills (more than one month away) and limit to 5 initially
    future_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.due_date > one_month_from_now,
        Ledger.status == 'owe'
    ).order_by(Ledger.due_date.asc()).limit(5).all()

    # Fetch all future bills for the "Show All" functionality
    all_future_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.due_date > one_month_from_now,
        Ledger.status == 'owe'
    ).order_by(Ledger.due_date.asc()).all()

    return render_template('home.html',
                           user=user,
                           current_bills=current_bills,
                           upcoming_bills=upcoming_bills,
                           paid_bills=paid_bills,
                           future_bills=future_bills,
                           all_future_bills=all_future_bills)

@app.route('/confirm_payment/<notif_id>/<ledger_id>', methods=['POST'])
def confirm_payment(notif_id, ledger_id):
    user_id = session.get('user_id')
    if not user_id:
        logging.error("User not logged in")
        return redirect(url_for('login'))

    # Log the received IDs
    logging.info(f"Confirm Payment called with notif_id: {notif_id}, ledger_id: {ledger_id}")

    # Fetch the notification using the notif_id
    notification = Notifications.query.get(notif_id)
    if not notification:
        logging.error(f"Notification not found for notif_id: {notif_id}")
        flash("Invalid operation.", "danger")
        return redirect(url_for('notifications'))

    # Fetch the ledger entry for the corresponding bill_id that is in confirming status
    ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id, status='confirming').first()

    # Log the existence of ledger entry
    if not ledger_entry:
        logging.error(f"Ledger entry not found with status 'confirming' for bill_id: {notification.bill_id}")
        flash("Invalid operation.", "danger")
        return redirect(url_for('notifications'))

    try:
        # Log before updating the ledger entry
        logging.info(f"Marking ledger_id: {ledger_entry.ledger_id} as paid")

        # Mark the bill as paid
        ledger_entry.status = 'paid'
        ledger_entry.paid_date = datetime.now()
        db.session.commit()

        # Notify the payer that the payment was confirmed
        payer = Users.query.get(ledger_entry.user_id)
        logging.info(f"Sending confirmation notification to user_id: {ledger_entry.user_id} for bill '{ledger_entry.bill_name}'")

        notification_message = f"{session['user_name']} has confirmed your payment for the bill '{ledger_entry.bill_name}'."
        new_notification = Notifications(
            user_id=ledger_entry.user_id,  # Notify the original payer
            sender_id=user_id,  # Bill creator
            bill_id=ledger_entry.bill_id,
            notif_type="payment_confirmation",
            content=notification_message,
            read=False
        )
        db.session.add(new_notification)

        # Mark the original notification as read
        notification.read = True
        db.session.commit()

        logging.info(f"Payment confirmation completed for ledger_id: {ledger_entry.ledger_id}")

        flash("Payment confirmed successfully.", "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred while confirming the payment: {str(e)}")
        flash(f"An error occurred while confirming the payment: {str(e)}", "danger")

    return redirect(url_for('notifications'))

@app.route('/deny_payment/<notif_id>/<ledger_id>', methods=['POST'])
def deny_payment(notif_id, ledger_id):
    user_id = session.get('user_id')
    if not user_id:
        logging.error("User not logged in")
        return redirect(url_for('login'))

    # Log the received IDs
    logging.info(f"Deny Payment called with notif_id: {notif_id}, ledger_id: {ledger_id}")

    # Fetch the notification using the notif_id
    notification = Notifications.query.get(notif_id)
    if not notification:
        logging.error(f"Notification not found for notif_id: {notif_id}")
        flash("Invalid operation.", "danger")
        return redirect(url_for('notifications'))

    # Fetch the ledger entry for the corresponding bill_id that is in confirming status
    ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id, status='confirming').first()

    # Log the existence of ledger entry
    if not ledger_entry:
        logging.error(f"Ledger entry not found with status 'confirming' for bill_id: {notification.bill_id}")
        flash("Invalid operation.", "danger")
        return redirect(url_for('notifications'))

    try:
        # Log before updating the ledger entry
        logging.info(f"Reverting ledger_id: {ledger_entry.ledger_id} status to 'owe'")

        # Revert the bill status to 'owe'
        ledger_entry.status = 'owe'
        db.session.commit()

        # Notify the payer that the payment was denied
        payer = Users.query.get(ledger_entry.user_id)
        logging.info(f"Sending denial notification to user_id: {ledger_entry.user_id} for bill '{ledger_entry.bill_name}'")

        notification_message = f"{session['user_name']} has denied your payment for the bill '{ledger_entry.bill_name}'."
        new_notification = Notifications(
            user_id=ledger_entry.user_id,  # Notify the original payer
            sender_id=user_id,  # Bill creator
            bill_id=ledger_entry.bill_id,
            notif_type="payment_denied",
            content=notification_message,
            read=False
        )
        db.session.add(new_notification)

        # Mark the original notification as read
        notification.read = True
        db.session.commit()

        logging.info(f"Payment denial completed for ledger_id: {ledger_entry.ledger_id}")

        flash("Payment denied successfully.", "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"An error occurred while denying the payment: {str(e)}")
        flash(f"An error occurred while denying the payment: {str(e)}", "danger")

    return redirect(url_for('notifications'))

@app.route('/pay_bill/<ledger_id>', methods=['POST'])
def pay_bill(ledger_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to pay the bill.", "danger")
        return redirect(url_for('login'))

    # Fetch the ledger entry for the bill
    ledger_entry = Ledger.query.filter_by(ledger_id=ledger_id, user_id=user_id).first()
    if not ledger_entry:
        flash("Bill not found or you don't have permission to pay this bill.", "danger")
        return redirect(url_for('home'))

    # Ensure the bill is not already in confirming or paid state
    if ledger_entry.status in ['confirming', 'paid']:
        flash("This bill is already in confirming or paid status.", "warning")
        return redirect(url_for('home'))

    try:
        # Mark the bill status as 'confirming'
        ledger_entry.status = 'confirming'
        ledger_entry.updated_at = datetime.now()

        # Fetch the bill and creator
        bill = Bills.query.get(ledger_entry.bill_id)
        creator = Users.query.get(bill.created_by)

        # Notify the bill creator that the payment is in confirming state
        notification_message = f"{session['user_name']} has claimed to pay the bill '{bill.bill_name}'. Please confirm or deny the payment."
        new_notification = Notifications(
            user_id=bill.created_by,  # Notify the bill creator
            sender_id=user_id,  # User who claimed to pay
            bill_id=bill.bill_id,
            notif_type="payment_confirmation_request",
            content=notification_message,
            read=False
        )
        db.session.add(new_notification)
        db.session.commit()

        flash("Payment claimed, waiting for confirmation from the bill creator.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while claiming the bill: {str(e)}", "danger")

    return redirect(url_for('home'))


@app.route('/mark_as_read/<notif_id>', methods=['POST'])
def mark_as_read(notif_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    notification = Notifications.query.get(notif_id)
    if not notification or notification.user_id != user_id:
        flash("Notification not found or unauthorized action.", "danger")
        return redirect(url_for('notifications'))

    try:
        notification.read = True
        db.session.commit()
        flash("Notification marked as read.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while marking the notification as read: {str(e)}", "danger")

    return redirect(url_for('notifications'))


@app.route('/create_group', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    group_name = request.form.get('newGroupName')
    split_type = request.form.get('splitType')

    try:
        new_group_id = generate_hex_id('group')
        group = Groups(group_id=new_group_id, group_name=group_name, manager_id=user_id, group_type=split_type)
        db.session.add(group)
        db.session.commit()


        group_member = GroupMembers(group_id=new_group_id, user_id=user_id)
        db.session.add(group_member)

        db.session.commit()

        flash('Group created successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating group: {str(e)}', 'error')

    return redirect(url_for('home'))

@app.route('/create_bill', methods=['GET', 'POST'])
def save_bill():
    # Check if the user is logged in
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the groups the user is a member of
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
        .filter(GroupMembers.user_id == user_id).all()

    if request.method == 'POST':
        try:
            bill_id  = generate_hex_id('bill')
            bill_name = request.form.get('bill_name')
            bill_type = request.form.get('bill_type')
            amount = request.form.get('amount')
            group_id = request.form.get('group_id')
            start_date = request.form.get('start_date') if bill_type == 'recurring' else None
            frequency = request.form.get('frequency') if bill_type == 'recurring' else None
            end_date = request.form.get('end_date') if bill_type == 'recurring' else None

            # Create the bill in the database
            new_bill = Bills(
                bill_id=bill_id,
                bill_name=bill_name,
                group_id=group_id,
                bill_type=bill_type,
                amount=amount,
                start_date=start_date,
                frequency=frequency,
                end_date=end_date,
                created_by=user_id,
                status='New',
            )
            db.session.add(new_bill)
            db.session.commit()

            # Generate payment schedule if it's a recurring bill
            if bill_type == 'recurring':
                generate_payment_schedule(bill_id)

            flash(f"Bill '{bill_name}' has been created successfully.", "success")
            return redirect(url_for('home'))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")
            return redirect(url_for('create_bill'))

    # Render the create_bill.html page and pass the groups to the template
    return render_template('create_bill.html', user_groups=user_groups)

@app.route('/my_bills', methods=['GET'])
def my_bills():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the bills created by the user
    created_bills = Bills.query.filter_by(created_by=user_id).all()

    return render_template('my_bills.html', created_bills=created_bills)

@app.route('/edit_bill/<bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the bill and check if the user is the creator
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    if not bill:
        flash("Bill not found or you don't have permission to edit this bill.", "danger")
        return redirect(url_for('my_bills'))

    if request.method == 'POST':
        try:
            # Update the existing bill's details
            bill.bill_name = request.form.get('bill_name')
            bill.group_id = request.form.get('group_id')
            bill.bill_type = request.form.get('bill_type')
            bill.amount = float(request.form.get('amount'))

            # Update recurring details if it's a recurring bill
            if bill.bill_type == 'recurring':
                bill.start_date = request.form.get('start_date')
                bill.frequency = request.form.get('frequency')
                bill.end_date = request.form.get('end_date')

            db.session.commit()

            # Only generate the payment schedule if the bill is recurring
            if bill.bill_type == 'recurring':
                generate_payment_schedule(bill_id)

            flash(f"Bill '{bill.bill_name}' has been updated successfully.", "success")
            return redirect(url_for('my_bills'))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while updating the bill: {str(e)}", "danger")
            return redirect(url_for('edit_bill', bill_id=bill_id))

    # For GET request, render the form with existing bill details
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id).filter(GroupMembers.user_id == user_id).all()
    return render_template('edit_bill.html', bill=bill, user_groups=user_groups)

@app.route('/get_group_members/<group_id>', methods=['GET'])
def get_group_members(group_id):
    group_members = GroupMembers.query.filter_by(group_id=group_id).all()
    members_data = [
        {"user_name": Users.query.get(member.user_id).user_name, "email": Users.query.get(member.user_id).email}
        for member in group_members
    ]
    return jsonify(members=members_data)

@app.route('/delete_bill/<bill_id>', methods=['POST'])
def delete_bill(bill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the bill by its ID and ensure the user is the creator
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()

    if not bill:
        flash("Bill not found or you don't have permission to delete this bill.", "danger")
        return redirect(url_for('my_bills'))

    try:
        # Delete associated ledger entries
        Ledger.query.filter_by(bill_id=bill.bill_id).delete()

        # Delete the bill itself
        db.session.delete(bill)
        db.session.commit()

        flash("Bill deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while deleting the bill: {str(e)}", "danger")

    return redirect(url_for('my_bills'))

@app.route('/generate_payment_schedule/<bill_id>', methods=['POST'])
def generate_payment_schedule(bill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    creditor_id = user_id
    creditor_name = session.get('user_name')

    # Fetch the bill and check if the user is the creator
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    if not bill:
        flash("Bill not found or you don't have permission to generate payment schedule for this bill.", "danger")
        return redirect(url_for('my_bills'))

    if bill.status == 'Active':
        flash("Bill already has a payment schedule.", "danger")
        return redirect(url_for('my_bills'))

    # Fetch the group members
    group_members = GroupMembers.query.filter_by(group_id=bill.group_id).all()

    if not group_members:
        flash("No members found in the group.", "danger")
        return redirect(url_for('my_bills'))

    try:
        # Check if the payment schedule already exists
        ledger_entries = Ledger.query.filter_by(bill_id=bill_id).all()
        if ledger_entries:
            flash("Payment schedule already generated.", "warning")
            return redirect(url_for('my_bills'))

        # Calculate the individual payment amount
        num_members = len(group_members)
        individual_amount = bill.amount / num_members

        if bill.bill_type == 'recurring':

            # Set the recurrence pattern
            current_date = bill.start_date
            end_date = bill.end_date
            recurrence_frequency = bill.frequency  # Can be 'monthly', 'weekly', or 'yearly'

            # Helper function to increment date based on the frequency
            def increment_date(date, frequency):
                if frequency == 'monthly':
                    return date + timedelta(days=30)  # Approximation for monthly
                elif frequency == 'weekly':
                    return date + timedelta(weeks=1)
                elif frequency == 'yearly':
                    return date + timedelta(days=365)
                else:
                    return date  # One-off payment

            group = Groups.query.filter_by(group_id=bill.group_id).first()

            # Generate the ledger entries for each recurrence period
            while current_date <= end_date:
                for member in group_members:
                    ledger_id = generate_hex_id('post')

                    user = Users.query.filter_by(user_id=member.user_id).first()

                    new_ledger_entry = Ledger(
                        ledger_id=ledger_id,
                        bill_id=bill.bill_id,
                        bill_name=bill.bill_name,
                        user_id=member.user_id,
                        user_name=user.user_name,
                        group_id=group.group_id,
                        group_name=group.group_name,
                        creditor_id=creditor_id,
                        creditor_name=creditor_name,
                        amount=individual_amount,
                        status='owe',  # Initial status is 'owe'
                        due_date=current_date  # Set due date for this recurrence
                    )
                    db.session.add(new_ledger_entry)

                # Increment the current date for the next recurrence
                current_date = increment_date(current_date, recurrence_frequency)

        else:

            group = Groups.query.filter_by(group_id=bill.group_id).first()

            due_date = datetime.today().date() + timedelta(days=7)

            for member in group_members:
                ledger_id = generate_hex_id('post')

                user = Users.query.filter_by(user_id=member.user_id).first()

                new_ledger_entry = Ledger(
                    ledger_id=ledger_id,
                    bill_id=bill.bill_id,
                    bill_name=bill.bill_name,
                    user_id=member.user_id,
                    user_name=user.user_name,
                    group_id=group.group_id,
                    group_name=group.group_name,
                    creditor_id=creditor_id,
                    creditor_name=creditor_name,
                    amount=individual_amount,
                    status='owe',  # Initial status is 'owe'
                    due_date=due_date  # SSet this for 7 days in the future
                )
                db.session.add(new_ledger_entry)

        # Mark the bill status as Active
        bill.status = 'Active'

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while generating the payment schedule: {str(e)}", "danger")

    return redirect(url_for('my_bills'))

@app.route('/view_payment_schedule/<bill_id>', methods=['GET'])
def view_payment_schedule(bill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the bill and check if the user is the creator
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    if not bill:
        flash("Bill not found or you don't have permission to view this payment schedule.", "danger")
        return redirect(url_for('my_bills'))

    # Fetch the payment schedule from the ledger
    ledger_entries = Ledger.query.filter_by(bill_id=bill_id).all()

    if not ledger_entries:
        flash("No payment schedule found for this bill.", "danger")
        return redirect(url_for('my_bills'))

    return render_template('view_payment_schedule.html', bill=bill, ledger_entries=ledger_entries)

@app.route('/create_bill', methods=['GET'])
def create_bill():
    # Check if the user is logged in
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the groups the user is a member of
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
        .filter(GroupMembers.user_id == user_id).all()

    # Render the create_bill.html page and pass the groups to the template
    return render_template('create_bill.html', user_groups=user_groups)

@app.route('/summary')
def summary():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = Users.query.get(user_id)

    # Fetch all ledger entries for this user
    ledger_entries = Ledger.query.filter_by(user_id=user_id).all()

    # Calculate total spent and outstanding balance
    total_spent = sum(entry.amount for entry in ledger_entries if entry.status == 'paid')
    outstanding_balance = sum(entry.amount for entry in ledger_entries if entry.status == 'owe')
    projected_spend = outstanding_balance + total_spent  # Could be adjusted for future bills

    # For chart: break down spend by month (past spend and future spend)
    months = []
    past_spend = []
    future_spend = []

    # Group entries by due date and amount
    now = datetime.now()
    for entry in ledger_entries:
        month_name = entry.due_date.strftime('%B')
        if month_name not in months:
            months.append(month_name)
        if entry.due_date < now:
            past_spend.append(entry.amount)
        else:
            future_spend.append(entry.amount)

    # Fetch money owed to creditors (you owe)
    money_owed = Ledger.query.filter_by(user_id=user_id, status='owe').all()

    return render_template('summary.html', user=user,
                           total_spent=total_spent,
                           outstanding_balance=outstanding_balance,
                           projected_spend=projected_spend,
                           ledger_entries=ledger_entries,
                           months=months,
                           past_spend=past_spend,
                           future_spend=future_spend,
                           money_owed=money_owed)

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
        return redirect(url_for('login'))

    # Fetch the current user
    user = Users.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

    # Fetch all notifications for the current user
    notifications = Notifications.query.filter_by(user_id=user_id).order_by(Notifications.read.asc(), Notifications.notif_id.desc()).all()

    # Fetch the corresponding ledger entries for each notification
    notification_data = []
    for notification in notifications:
        # Get the corresponding ledger entry
        ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id).first()
        notification_data.append({
            'notification': notification,
            'ledger_entry': ledger_entry  # Add the ledger entry
        })

    # Pass data to the template
    return render_template('notifications.html', user=user, notification_data=notification_data)



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

@app.route('/show_groups')
def show_groups():

    user_id = session['user_id']

    try:

        groups_data = GroupService.get_group_details(user_id)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return render_template('show_groups.html', groups=groups_data)  # Pass relevant data

@app.route('/creat_new_group')
def create_new_group():
    return render_template('create_group.html')  # Pass relevant data

@app.route('/delete_group/<group_id>', methods=['POST'])
def delete_group(group_id):
    """
    Deletes a group if the current user is the manager.
    """
    user_id = session.get('user_id')

    if not user_id:
        flash("You need to be logged in to delete a group.", "danger")
        return redirect(url_for('home'))

    # Fetch the group by group_id
    group = Groups.query.filter_by(group_id=group_id).first()

    if not group:
        flash("Group not found.", "danger")
        return redirect(url_for('home'))

    # Check if the user is the group manager
    if group.manager_id != user_id:
        flash("You are not authorized to delete this group.", "danger")
        return redirect(url_for('home'))

    try:
        # Delete related data (e.g., group members, bills)
        GroupMembers.query.filter_by(group_id=group_id).delete()
        Bills.query.filter_by(group_id=group_id).delete()

        # Delete the group itself
        db.session.delete(group)
        db.session.commit()

        flash("Group deleted successfully.", "success")
        return redirect(url_for('home'))

    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/edit_group/<group_id>', methods=['GET'])
def edit_group(group_id):
    """
    Edit group details and manage members.
    """
    user_id = session.get('user_id')

    if not user_id:
        flash("You need to be logged in to edit a group.", "danger")
        return redirect(url_for('home'))

    group = Groups.query.filter_by(group_id=group_id).first()

    if not group or group.manager_id != user_id:
        flash("You are not authorized to edit this group.", "danger")
        return redirect(url_for('home'))


        return redirect(url_for('show_groups', group_id=group_id))

    # Fetch group members for the GET request
    group_members = Users.query.join(GroupMembers, Users.user_id == GroupMembers.user_id).filter(GroupMembers.group_id == group_id).all()

    return render_template('edit_group.html', group=group, group_members=group_members)

@app.route('/delete_notification/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    notification = Notifications.query.get_or_404(notif_id)

    if notification.user_id != session['user_id']:
        flash("You are not authorized to delete this notification.", "danger")
        return redirect(url_for('notifications'))

    db.session.delete(notification)
    db.session.commit()

    flash("Notification deleted successfully.", "success")
    return redirect(url_for('notifications'))

@app.route('/invite_members/<group_id>', methods=['POST'])
def invite_members(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    invite_emails = request.form.get('invite_emails')

    # Split the emails by commas and clean up the list
    email_list = [email.strip() for email in invite_emails.split(',') if email.strip()]

    # Get the group from the database
    group = Groups.query.get(group_id)

    for email in email_list:
        # Check if the user exists in the system
        invited_user = Users.query.filter_by(email=email).first()

        if invited_user:
            # Check if the user is already a member of the group
            existing_member = GroupMembers.query.filter_by(user_id=invited_user.user_id, group_id=group_id).first()

            if existing_member:
                flash(f"{email} is already a member of the group.", "warning")
            else:
                # Add the user to the group
                new_member = GroupMembers(user_id=invited_user.user_id, group_id=group_id)
                db.session.add(new_member)

                # Send a notification to the user
                notification_message = f"You have been invited to join the group '{group.group_name}'."
                new_notification = Notifications(
                    user_id=invited_user.user_id,
                    sender_id=session['user_id'],  # Assuming the current user is the sender
                    notif_type='group_invite',
                    content=notification_message,
                    read=False
                )
                db.session.add(new_notification)

                flash(f"Invitation sent to {email}.", "success")

        else:
            # Handle the case where the email does not exist in the system
            flash(f"{email} does not exist in the system. Sending a notification email (stub for now).", "info")
            # Here you can integrate email sending logic later as a stub
            # send_email_stub(email, group.group_name)

    db.session.commit()
    return redirect(url_for('edit_group', group_id=group_id))

@app.route('/remove_member/<group_id>/<member_id>', methods=['POST'])
def remove_member(group_id, member_id):
    """
    Remove a user from a group (only by group manager).
    """
    user_id = session.get('user_id')

    if not user_id:
        flash("You need to be logged in to remove a member.", "danger")
        return redirect(url_for('home'))

    group = Groups.query.filter_by(group_id=group_id).first()

    if not group or group.manager_id != user_id:
        flash("You are not authorized to remove members from this group.", "danger")
        return redirect(url_for('edit_group', group_id=group_id))

    # Remove the member from the group
    GroupMembers.query.filter_by(user_id=member_id, group_id=group_id).delete()
    db.session.commit()

    flash("Member removed successfully.", "success")
    return redirect(url_for('edit_group', group_id=group_id))

if __name__ == '__main__':
    app.run(debug=True)
