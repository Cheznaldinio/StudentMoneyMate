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
    payment_id = db.Column(String(255), primary_key=True)
    bill_id = db.Column(String(255), ForeignKey('bills.bill_id'))
    user_id = db.Column(String(255), ForeignKey('users.user_id'))
    confirmed = db.Column(Boolean)

    def __str__(self):
        return f"Ledger: {self.payment_id}, {self.bill_id}, {self.user_id}, {self.confirmed}"

class Bills(db.Model):
    bill_id = db.Column(String(255), primary_key=True)
    bill_name = db.Column(String(255))
    group_id = db.Column(String(255), ForeignKey('groups.group_id'))
    amount = db.Column(Float)
    start_date = db.Column(TIMESTAMP)

    def __str__(self):
        return (f"Bills: {self.bill_id}, {self.bill_name}, {self.group_id}, {self.amount}, "
                f"{self.start_date}")

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
