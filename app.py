import random
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, make_response, g
from databases import db, Users, Groups, Ledger, Bills, Config, GroupMembers, Notifications, BankDetails
import datetime
from datetime import datetime, timedelta
from services.group_services import GroupService
import os
from werkzeug.utils import secure_filename
from PIL import Image

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'your_secret_key'
db.init_app(app)
UPLOAD_FOLDER = os.path.join(basedir, 'static/profile_pictures')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
with app.app_context():
    db.create_all()

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    if user_id:
        user = Users.query.get(user_id)
        return {'user': user}
    return {}

def get_unread_notifications_count(user_id):
    return Notifications.query.filter_by(user_id=user_id, read=False).count()

@app.before_request
def load_user_data():
    g.user = None
    g.unread_notifications_count = 0

    if 'user_id' in session:
        user_id = session['user_id']
        g.user = Users.query.get(user_id)
        g.unread_notifications_count = get_unread_notifications_count(user_id)

def checkimg(filename):
    parts = filename.rsplit('.', 1)
    if len(parts) == 2:
        extension = parts[1].lower()
        if extension in {'png', 'jpg', 'jpeg'}:
            return True
    else:
        return False

def checklogin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

def MakeHex(prefix):
    return f"{prefix}{''.join(random.choices('0123456789ABCDEF', k=6))}"

@app.route('/', methods=['GET'])
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    remember_me = request.cookies.get('rememberMe')
    if remember_me and remember_me == 'true' and 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    account_email = request.form['accountEmail']
    account_password = request.form['accountUserPassword']
    remember_me = request.form.get('rememberMe')
    user = Users.query.filter_by(email=account_email).first()
    if user and user.password == account_password:
        session['user_id'] = user.user_id
        session['user_name'] = user.user_name
        session['user_email'] = user.email
        resp = make_response(redirect(url_for('home')))
        if remember_me:
            resp.set_cookie('rememberMe', 'true', max_age=30 * 24 * 60 * 60)
        else:
            resp.set_cookie('rememberMe', 'false', max_age=30 * 24 * 60 * 60)
        return resp
    flash('email or pasword wrong', 'danger')
    return render_template('login.html')

@app.route('/create', methods=['GET'])
def create():
    return render_template('create_account.html')

@app.route('/create_account', methods=['POST'])
def create_account():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    existing_user = Users.query.filter_by(email=email).first()
    if existing_user:
        flash('Email already has user', 'danger')
        return redirect(url_for('create'))
    new_user_id = MakeHex('user')
    new_user = Users(user_id=new_user_id, user_name=name, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()
    flash('account craeted', 'success')
    return redirect(url_for('confirmation'))

@app.route('/confirmation', methods=['GET'])
def confirmation():
    return render_template('confirmation.html')

@app.route('/home', methods=['GET'])
def home():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = Users.query.get(user_id)
    current_date = datetime.now()
    two_weeks_from_now = current_date + timedelta(weeks=2)
    one_month_from_now = current_date + timedelta(weeks=6)

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

    future_bills = Ledger.query.filter(
        Ledger.user_id == user_id,
        Ledger.due_date > one_month_from_now,
        Ledger.status == 'owe'
    ).order_by(Ledger.due_date.asc()).limit(5).all()

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
    checklogin()
    notification = Notifications.query.get(notif_id)
    ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id, status='confirming').first()
    ledger_entry.status = 'paid'
    ledger_entry.paid_date = datetime.now()
    db.session.commit()
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
    notification.read = True
    db.session.commit()
    flash("payment confirmed", "success")
    return redirect(url_for('notifications'))

@app.route('/deny_payment/<notif_id>/<ledger_id>', methods=['POST'])
def deny_payment(notif_id, ledger_id):
    user_id = session.get('user_id')
    checklogin()
    notification = Notifications.query.get(notif_id)
    ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id, status='confirming').first()
    ledger_entry.status = 'owe'
    db.session.commit()
    notification_message = f"{session['user_name']} has denied your payment for the bill '{ledger_entry.bill_name}'."
    new_notification = Notifications(user_id=ledger_entry.user_id, sender_id=user_id,
                                     bill_id=ledger_entry.bill_id, notif_type="payment_denied",
                                     content=notification_message, read=False)
    db.session.add(new_notification)
    notification.read = True
    db.session.commit()
    flash("payment denied", "success")
    return redirect(url_for('notifications'))

@app.route('/pay_bill/<ledger_id>', methods=['POST'])
def pay_bill(ledger_id):
    user_id = session.get('user_id')
    checklogin()
    ledger_entry = Ledger.query.filter_by(ledger_id=ledger_id, user_id=user_id).first()
    ledger_entry.status = 'confirming'
    ledger_entry.updated_at = datetime.now()
    bill = Bills.query.get(ledger_entry.bill_id)
    notification_message = f"{session['user_name']} is trying to pay '{bill.bill_name}'. Please confirm or deny it."
    new_notification = Notifications(user_id=bill.created_by, sender_id=user_id,
                                     bill_id=bill.bill_id,
                                     notif_type="payment_confirmation_request",
                                     content=notification_message, read=False)
    db.session.add(new_notification)
    db.session.commit()
    flash("payment claimed, awaiting confirmation", "success")
    return redirect(url_for('home'))

@app.route('/mark_as_read/<notif_id>', methods=['POST'])
def mark_as_read(notif_id):
    user_id = session.get('user_id')
    checklogin()
    notification = Notifications.query.get(notif_id)
    notification.read = True
    db.session.commit()
    flash("notification marked as read", "success")
    return redirect(url_for('notifications'))

@app.route('/create_group', methods=['POST'])
def create_group():
    checklogin()
    user_id = session['user_id']
    group_name = request.form.get('newGroupName')
    split_type = request.form.get('splitType')
    new_group_id = MakeHex('group')
    group = Groups(group_id=new_group_id, group_name=group_name, manager_id=user_id,
                   group_type=split_type)
    db.session.add(group)
    db.session.commit()
    group_member = GroupMembers(group_id=new_group_id, user_id=user_id)
    db.session.add(group_member)
    db.session.commit()
    flash('group created!', 'success')
    return redirect(url_for('home'))

@app.route('/create_bill', methods=['GET', 'POST'])
def save_bill():
    user_id = session.get('user_id')
    checklogin()
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id).filter(GroupMembers.user_id == user_id).all()
    if request.method == 'POST':
        bill_id = MakeHex('bill')
        bill_name = request.form.get('bill_name')
        bill_type = request.form.get('bill_type')
        amount = request.form.get('amount')
        group_id = request.form.get('group_id')
        start_date = request.form.get('start_date') if bill_type == 'recurring' else None
        frequency = request.form.get('frequency') if bill_type == 'recurring' else None
        end_date = request.form.get('end_date') if bill_type == 'recurring' else None
        new_bill = Bills(bill_id=bill_id, bill_name=bill_name, group_id=group_id,
                         bill_type=bill_type, amount=amount, start_date=start_date,
                         frequency=frequency, end_date=end_date, created_by=user_id, status='New')
        db.session.add(new_bill)
        db.session.commit()
        generate_payment_schedule(bill_id)
        flash(f"bill '{bill_name}' created!", "success")
        return redirect(url_for('home'))
    return render_template('create_bill.html', user_groups=user_groups)

@app.route('/my_bills', methods=['GET'])
def my_bills():
    user_id = session.get('user_id')
    checklogin()
    created_bills = db.session.query(Bills, Groups.group_name).join(Groups, Bills.group_id == Groups.group_id).filter(Bills.created_by == user_id).all()
    modified_bills = []
    for bill, group_name in created_bills:
        repetitions = Ledger.query.filter_by(bill_id=bill.bill_id, user_id=user_id).count()
        latest_ledger_entry = Ledger.query.filter_by(bill_id=bill.bill_id, user_id=user_id).order_by(Ledger.due_date.desc()).first()
        if latest_ledger_entry:
            latest_due_date = latest_ledger_entry.due_date
        else:
            latest_due_date = None
        if repetitions <= 1:
            repetitions = 1
            end_date = latest_due_date
        else:
            end_date = bill.end_date if bill.end_date else latest_due_date
        modified_bills.append((bill, group_name, repetitions, end_date))
    return render_template('my_bills.html', created_bills=modified_bills)

@app.route('/edit_bill/<bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    user_id = session.get('user_id')
    checklogin()
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    if request.method == 'POST':
        bill.bill_name = request.form.get('bill_name')
        bill.group_id = request.form.get('group_id')
        bill.bill_type = request.form.get('bill_type')
        bill.amount = float(request.form.get('amount'))
        if bill.bill_type == 'recurring':
            bill.start_date = request.form.get('start_date')
            bill.frequency = request.form.get('frequency')
            bill.end_date = request.form.get('end_date')
        db.session.commit()
        generate_payment_schedule(bill_id)
        flash(f"bill '{bill.bill_name}' updated", "success")
        return redirect(url_for('my_bills'))
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id).filter(GroupMembers.user_id == user_id).all()
    return render_template('edit_bill.html', bill=bill, user_groups=user_groups)

@app.route('/get_group_members/<group_id>', methods=['GET'])
def get_group_members(group_id):
    group_members = GroupMembers.query.filter_by(group_id=group_id).all()
    members_data = [{"user_name": Users.query.get(member.user_id).user_name, "email": Users.query.get(member.user_id).email} for member in group_members]
    return jsonify(members=members_data)

@app.route('/delete_bill/<bill_id>', methods=['POST'])
def delete_bill(bill_id):
    user_id = session.get('user_id')
    checklogin()
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    Notifications.query.filter_by(bill_id=bill.bill_id).delete()
    Ledger.query.filter_by(bill_id=bill.bill_id).delete()
    db.session.delete(bill)
    db.session.commit()
    flash("bill deleted", "success")
    return redirect(url_for('my_bills'))

@app.route('/generate_payment_schedule/<bill_id>', methods=['POST'])
def generate_payment_schedule(bill_id):
    user_id = session.get('user_id')
    checklogin()
    creditor_id = user_id
    creditor_name = session.get('user_name')
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    group_members = GroupMembers.query.filter_by(group_id=bill.group_id).all()
    num_members = len(group_members)
    individual_amount = bill.amount / num_members
    if bill.bill_type == 'recurring':
        current_date = bill.start_date
        end_date = bill.end_date
        recurrence_frequency = bill.frequency

        def increment_date(date, frequency):
            if frequency == 'monthly':
                return date + timedelta(days=30)
            elif frequency == 'weekly':
                return date + timedelta(weeks=1)
            elif frequency == 'yearly':
                return date + timedelta(days=365)
            else:
                return date

        group = Groups.query.filter_by(group_id=bill.group_id).first()
        while current_date <= end_date:
            for member in group_members:
                ledger_id = MakeHex('post')
                user = Users.query.filter_by(user_id=member.user_id).first()
                new_ledger_entry = Ledger(ledger_id=ledger_id, bill_id=bill.bill_id,
                                          bill_name=bill.bill_name, user_id=member.user_id,
                                          user_name=user.user_name, group_id=group.group_id,
                                          group_name=group.group_name, creditor_id=creditor_id,
                                          creditor_name=creditor_name, amount=individual_amount,
                                          status='owe', due_date=current_date)
                db.session.add(new_ledger_entry)
            current_date = increment_date(current_date, recurrence_frequency)
    else:
        group = Groups.query.filter_by(group_id=bill.group_id).first()
        due_date = datetime.today().date() + timedelta(days=7)
        for member in group_members:
            ledger_id = MakeHex('post')
            user = Users.query.filter_by(user_id=member.user_id).first()
            new_ledger_entry = Ledger(ledger_id=ledger_id, bill_id=bill.bill_id,
                                      bill_name=bill.bill_name, user_id=member.user_id,
                                      user_name=user.user_name, group_id=group.group_id,
                                      group_name=group.group_name, creditor_id=creditor_id,
                                      creditor_name=creditor_name, amount=individual_amount,
                                      status='owe', due_date=due_date)
            db.session.add(new_ledger_entry)
    bill.status = 'Active'
    db.session.commit()
    return redirect(url_for('my_bills'))

@app.route('/view_payment_schedule/<bill_id>', methods=['GET'])
def view_payment_schedule(bill_id):
    user_id = session.get('user_id')
    checklogin()
    bill = Bills.query.filter_by(bill_id=bill_id, created_by=user_id).first()
    ledger_entries = Ledger.query.filter_by(bill_id=bill_id).all()
    return render_template('view_payment_schedule.html', bill=bill, ledger_entries=ledger_entries)

@app.route('/create_bill', methods=['GET'])
def create_bill():
    user_id = session.get('user_id')
    checklogin()
    user_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id).filter(GroupMembers.user_id == user_id).all()
    return render_template('create_bill.html', user_groups=user_groups)

@app.route('/summary')
def summary():
    user_id = session.get('user_id')
    checklogin()
    user = Users.query.get(user_id)
    ledger_entries = Ledger.query.filter_by(user_id=user_id).all()
    total_spent = sum(entry.amount for entry in ledger_entries if entry.status == 'paid')
    outstanding_balance = sum(entry.amount for entry in ledger_entries if entry.status == 'owe')
    projected_spend = outstanding_balance + total_spent
    months = []
    past_spend = []
    future_spend = []
    now = datetime.now()
    for entry in ledger_entries:
        month_name = entry.due_date.strftime('%B')
        if month_name not in months:
            months.append(month_name)
        if entry.due_date < now:
            past_spend.append(entry.amount)
        else:
            future_spend.append(entry.amount)
    money_owed = Ledger.query.filter_by(user_id=user_id, status='owe').all()
    return render_template('summary.html', user=user, total_spent=total_spent, outstanding_balance=outstanding_balance, projected_spend=projected_spend, ledger_entries=ledger_entries, months=months, past_spend=past_spend, future_spend=future_spend, money_owed=money_owed)

@app.route('/account', methods=['GET'])
def account():
    user_id = session.get('user_id')
    checklogin()
    user = Users.query.get(user_id)
    bank_details = BankDetails.query.filter_by(user_id=user_id).first()
    return render_template('account.html', user=user, bank_details=bank_details)

@app.route('/update_account', methods=['POST'])
def update_account():
    user_id = session.get('user_id')
    checklogin()
    user = Users.query.get(user_id)
    previous_password = request.form['previous_password']
    if user.password != previous_password:
        flash('wrong password', 'danger')
        return redirect(url_for('account'))
    user.user_name = request.form['name']
    user.email = request.form['email']
    if request.form['new_password']:
        user.password = request.form['new_password']
    if 'profile_picture' in request.files:
        file = request.files['profile_picture']
        if file == True and checkimg(file.filename):
            filename = secure_filename(f"{user_id}.png")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_' + filename)
            file.save(temp_file_path)
            with Image.open(temp_file_path) as img:
                width, height = img.size
                new_size = min(width, height)
                left = (width - new_size) / 2
                top = (height - new_size) / 2
                right = (width + new_size) / 2
                bottom = (height + new_size) / 2
                img_cropped = img.crop((left, top, right, bottom))
                img_resized = img_cropped.resize((512, 512))
                img_resized.save(file_path, "PNG", quality=85)
            os.remove(temp_file_path)
    db.session.commit()
    flash('account updated', 'success')
    return redirect(url_for('account'))

@app.route('/header', methods=['GET'])
def header():
    return render_template('base.html')

@app.route('/join_flat', methods=['POST'])
def join_flat():
    checklogin()
    user_id = session['user_id']
    flat_group_id = request.form.get('flatGroupId')
    existing_member = GroupMembers.query.filter_by(group_id=flat_group_id, user_id=user_id).first()
    if existing_member == True:
        flash('already a member of this flat group', 'danger')
    else:
        new_member = GroupMembers(group_id=flat_group_id, user_id=user_id)
        db.session.add(new_member)
        db.session.commit()
        flash('joined the group', 'success')
    return redirect(url_for('home'))

@app.route('/create_flat', methods=['POST'])
def create_flat():
    checklogin()
    user_id = session['user_id']
    flat_group_name = request.form.get('flatGroupName')
    new_group_id = MakeHex('group')
    new_flat_group = Groups(group_id=new_group_id, group_name=flat_group_name, manager_id=user_id,
                            group_type='flat')
    db.session.add(new_flat_group)
    db.session.commit()
    new_group_member = GroupMembers(group_id=new_group_id, user_id=user_id)
    db.session.add(new_group_member)
    db.session.commit()
    flash('flat group created!', 'success')
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
    checklogin()
    user = Users.query.get(user_id)
    notifications = Notifications.query.filter_by(user_id=user_id).order_by(Notifications.read.asc(), Notifications.notif_id.desc()).all()
    notification_data = []
    for notification in notifications:
        ledger_entry = Ledger.query.filter_by(bill_id=notification.bill_id).first()
        notification_data.append({'notification': notification, 'ledger_entry': ledger_entry})
    return render_template('notifications.html', user=user, notification_data=notification_data)

@app.route('/paid_bill', methods=['POST'])
def paid_bill():
    checklogin()
    user_id = session['user_id']
    bill_id = request.form.get('selectedBill')
    bill = Bills.query.get(bill_id)
    group = Groups.query.get(bill.group_id)
    manager_id = group.manager_id
    notif_id = MakeHex('notif')
    new_notification = Notifications(notif_id=notif_id, user_id=manager_id, sender_id=user_id,
                                     bill_id=bill.bill_id, notif_type='confirmation', content='',
                                     read=False)
    db.session.add(new_notification)
    db.session.commit()
    return jsonify({"success": "notification sent"}), 200

@app.route('/show_groups')
def show_groups():
    user_id = session['user_id']
    groups_data = GroupService.get_group_details(user_id)
    return render_template('show_groups.html', groups=groups_data)

@app.route('/creat_new_group')
def create_new_group():
    return render_template('create_group.html')

@app.route('/delete_group/<group_id>', methods=['POST'])
def delete_group(group_id):
    checklogin()
    user_id = session.get('user_id')
    group = Groups.query.filter_by(group_id=group_id).first()
    GroupMembers.query.filter_by(group_id=group_id).delete()
    Bills.query.filter_by(group_id=group_id).delete()
    db.session.delete(group)
    db.session.commit()
    flash("group deleted", "success")
    return redirect(url_for('home'))

@app.route('/edit_group/<group_id>', methods=['GET', 'POST'])
def edit_group(group_id):
    checklogin()
    user_id = session.get('user_id')
    group = Groups.query.filter_by(group_id=group_id).first()
    group_members = Users.query.join(GroupMembers, Users.user_id == GroupMembers.user_id).filter(GroupMembers.group_id == group_id).all()
    pending_invites = Notifications.query.filter_by(group_id=group_id, notif_type='group_invite', read=False).all()
    is_manager = (group.manager_id == user_id)
    return render_template('edit_group.html', group=group, group_members=group_members, pending_invites=pending_invites, is_manager=is_manager)

@app.route('/edit_group_details/<group_id>', methods=['POST'])
def edit_group_details(group_id):
    checklogin()
    user_id = session.get('user_id')
    group = Groups.query.filter_by(group_id=group_id).first()
    new_group_name = request.form.get('group_name')
    new_group_type = request.form.get('group_type')
    group.group_name = new_group_name
    group.group_type = new_group_type
    db.session.commit()
    flash("group updated", "success")
    return redirect(url_for('edit_group', group_id=group_id))

@app.route('/delete_notification/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    checklogin()
    notification = Notifications.query.get_or_404(notif_id)
    db.session.delete(notification)
    db.session.commit()
    flash("notification deleted", "success")
    return redirect(url_for('notifications'))

@app.route('/leave_group/<group_id>', methods=['POST'])
def leave_group(group_id):
    checklogin()
    user_id = session.get('user_id')
    group = Groups.query.filter_by(group_id=group_id).first()
    if group.manager_id == user_id:
        next_member = GroupMembers.query.filter(GroupMembers.group_id == group_id, GroupMembers.user_id != user_id).first()
        group.manager_id = next_member.user_id
        flash(f"gave {next_member.user_name} manger", "success")
    GroupMembers.query.filter_by(group_id=group_id, user_id=user_id).delete()
    db.session.commit()
    flash("left group", "success")
    return redirect(url_for('home'))

@app.route('/invite_members/<group_id>', methods=['POST'])
def invite_members(group_id):
    checklogin()
    invite_emails = request.form.get('invite_emails')
    email_list = [email.strip() for email in invite_emails.split(',') if email.strip()]
    group = Groups.query.get(group_id)
    for email in email_list:
        invited_user = Users.query.filter_by(email=email).first()
        if invited_user:
            existing_member = GroupMembers.query.filter_by(user_id=invited_user.user_id, group_id=group_id).first()
            if existing_member:
                flash(f'{email} is already in the group', 'warning')
            else:
                new_notification = Notifications(user_id=invited_user.user_id, sender_id=session['user_id'], notif_type='group_invite', content=f"you have been invited to join the group '{group.group_name}'", invitee_email=email, group_id=group_id, read=False)
                db.session.add(new_notification)
                flash(f"invite sent to {email}", 'success')
        else:
            new_notification = Notifications(sender_id=session['user_id'], notif_type='group_invite', content=f"you have been invited to join the group '{group.group_name}'", invitee_email=email, group_id=group_id, read=False)
            db.session.add(new_notification)
            flash(f"invite sent to {email}", 'success')
    db.session.commit()
    return redirect(url_for('edit_group', group_id=group_id))

@app.route('/remove_member/<group_id>/<member_id>', methods=['POST'])
def remove_member(group_id, member_id):
    checklogin()
    GroupMembers.query.filter_by(group_id=group_id, user_id=member_id).delete()
    db.session.commit()
    flash("member removed", "success")
    return redirect(url_for('edit_group', group_id=group_id))

@app.route('/accept_invite/<notif_id>', methods=['POST'])
def accept_invite(notif_id):
    user_id = session.get('user_id')
    checklogin()
    notification = Notifications.query.get(notif_id)
    group = Groups.query.get(notification.group_id)
    new_member = GroupMembers(group_id=group.group_id, user_id=user_id)
    db.session.add(new_member)
    inviter_id = notification.sender_id
    notification_message = f"{session['user_name']} accepted your invite to join '{group.group_name}'"
    new_notification = Notifications(user_id=inviter_id, sender_id=user_id,
                                     notif_type="invite_accepted", content=notification_message,
                                     read=False)
    db.session.add(new_notification)
    notification.read = True
    db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/deny_invite/<notif_id>', methods=['POST'])
def deny_invite(notif_id):
    user_id = session.get('user_id')
    checklogin()
    notification = Notifications.query.get(notif_id)
    group = Groups.query.get(notification.group_id)
    inviter_id = notification.sender_id
    notification_message = f"{session['user_name']} denied your invite to join '{group.group_name}'"
    new_notification = Notifications(user_id=inviter_id, sender_id=user_id,
                                     notif_type="invite_denied", content=notification_message,
                                     read=False)
    db.session.add(new_notification)
    notification.read = True
    db.session.commit()
    flash("invite denied", "success")
    return redirect(url_for('notifications'))

@app.route('/delete_invite/<int:invite_id>', methods=['POST'])
def delete_invite(invite_id):
    checklogin()
    user_id = session.get('user_id')
    invite = Notifications.query.filter_by(notif_id=invite_id, notif_type='group_invite').first()
    db.session.delete(invite)
    db.session.commit()
    flash("invite deleted", "success")
    return redirect(url_for('edit_group', group_id=invite.group_id))

@app.route('/update_bank_details', methods=['POST'])
def update_bank_details():
    checklogin()
    user_id = session.get('user_id')
    full_name = request.form['full_name']
    sort_code = request.form['sort_code']
    account_number = request.form['account_number']
    bank_details = BankDetails.query.filter_by(user_id=user_id).first()
    if bank_details:
        bank_details.full_name = full_name
        bank_details.sort_code = sort_code
        bank_details.account_number = account_number
    else:
        new_bank_details = BankDetails(user_id=user_id, full_name=full_name, sort_code=sort_code, account_number=account_number)
        db.session.add(new_bank_details)
    db.session.commit()
    flash("bank details updated", "success")
    return redirect(url_for('account'))

if __name__ == '__main__':
    app.run(debug=True)
