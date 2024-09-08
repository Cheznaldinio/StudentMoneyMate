import os
from sqlalchemy import text, ForeignKey, Float
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import String, Boolean, TIMESTAMP, Integer

db = SQLAlchemy()

class Config(object):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
                              'postgresql://postgres:postgres@localhost/StudentMoneyMate'
    SQLALCHEMY_TRACK_MODIFICATIONS = True

class Users(db.Model):
    user_id = db.Column(String(255), primary_key=True, nullable=True, server_default=text('NULL::character varying'))
    user_name = db.Column(String(255), nullable=False)
    email = db.Column(String(255))
    password = db.Column(String(255))
    admin = db.Column(Boolean, default=False)

    def __str__(self):
        return f"User: {self.user_id}, {self.user_name}, {self.email}, {self.password}, {self.admin}"

class Groups(db.Model):
    group_id = db.Column(String(255), primary_key=True)
    group_name = db.Column(String(255))
    manager_id = db.Column(String(255), ForeignKey('users.user_id'))
    group_type = db.Column(String(255))

    def __str__(self):
        return f"Group: {self.group_id}, {self.group_name}, {self.manager_id}, {self.group_type}"

class Ledger(db.Model):
    ledger_id = db.Column(String(255), primary_key=True)
    bill_id = db.Column(String(255), ForeignKey('bills.bill_id'))
    bill_name = db.Column(String(255))
    user_id = db.Column(String(255), ForeignKey('users.user_id'))
    user_name = db.Column(String(255))
    creditor_id = db.Column(String(255))
    creditor_name = db.Column(String(255))
    group_id = db.Column(String(255), ForeignKey('groups.group_id'))
    group_name = db.Column(String(255))
    amount = db.Column(Float)
    status = db.Column(String(50))  # 'owe', 'paid', etc.
    due_date = db.Column(TIMESTAMP)
    paid_date = db.Column(TIMESTAMP)
    created_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp())
    updated_at = db.Column(db.TIMESTAMP, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __str__(self):
        return (f"Ledger: {self.ledger_id}, Bill: {self.bill_name}, Bill ID: {self.bill_id}, "
                f"User: {self.user_name} (ID: {self.user_id}), Creditor: {self.creditor_name} (ID: {self.creditor_id}), "
                f"Group: {self.group_name} (ID: {self.group_id}), Amount: {self.amount}, "
                f"Status: {self.status}, Due Date: {self.due_date}, "
                f"Created: {self.created_at}, Updated: {self.updated_at}")



class Bills(db.Model):
    __tablename__ = 'bills'

    bill_id = db.Column(db.String(255), primary_key=True)
    bill_name = db.Column(db.String(255), nullable=False)
    group_id = db.Column(db.String(255), db.ForeignKey('groups.group_id'), nullable=False)
    bill_type = db.Column(db.String(50), nullable=False)  # 'one_off' or 'recurring'
    amount = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.TIMESTAMP, nullable=True)
    frequency = db.Column(db.String(50), nullable=True)  # e.g., 'monthly', 'weekly', etc.
    end_date = db.Column(db.TIMESTAMP, nullable=True)  # End date for recurring bills
    created_by = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    def __str__(self):
        return (f"Bills: {self.bill_id}, {self.bill_name}, {self.group_id}, {self.bill_type}, "
                f"{self.amount}, {self.start_date}, {self.frequency}, {self.end_date}, {self.created_by}, {self.status}")

class GroupMembers(db.Model):
    group_id = db.Column(String(255), ForeignKey('groups.group_id'), primary_key=True)
    user_id = db.Column(String(255), ForeignKey('users.user_id'), primary_key=True)

    def __str__(self):
        return f"GroupMembers: {self.group_id}, {self.user_id}"

class Notifications(db.Model):
    notif_id = db.Column(Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(String(255), ForeignKey('users.user_id'))
    sender_id = db.Column(String(255), ForeignKey('users.user_id'))
    bill_id = db.Column(String(255), ForeignKey('bills.bill_id'))
    notif_type = db.Column(String(255))
    content = db.Column(String(255))
    read = db.Column(Boolean, default=False)

    sender = db.relationship('Users', foreign_keys=[sender_id])
    bill = db.relationship('Bills', foreign_keys=[bill_id])

    def __str__(self):
        return (f"Notification: {self.notif_id}, {self.user_id}, {self.sender_id}, {self.bill_id}, "
                f"{self.notif_type}, {self.content}, {self.read}")
