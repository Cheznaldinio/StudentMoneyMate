import os
from sqlalchemy import text, ForeignKey
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import String, Boolean, Float, Integer, TIMESTAMP

db = SQLAlchemy()

class Config(object):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
                              'postgresql://postgres:postgres@localhost/StudentMoneyMate'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True
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

class Accounts(db.Model):
    account_id = db.Column(String(255), primary_key=True)
    account_type = db.Column(String(255))
    entity_id = db.Column(String(255))

    def __str__(self):
        return f"Account: {self.account_id}, {self.account_type}, {self.entity_id}"

class Ledger(db.Model):
    transaction_id = db.Column(String(255), primary_key=True)
    group_id = db.Column(String(255), ForeignKey('groups.group_id'))
    account_id = db.Column(String(255), ForeignKey('accounts.account_id'))
    counterparty_id = db.Column(String(255), ForeignKey('accounts.account_id'))
    bill_id = db.Column(String(255), ForeignKey('bills.bill_id'))
    amount = db.Column(Float)
    type = db.Column(String(255))
    due_date = db.Column(TIMESTAMP)
    transaction_date = db.Column(TIMESTAMP)
    confirmed = db.Column(Boolean)
    description = db.Column(String(255))

    def __str__(self):
        return (f"Ledger: {self.transaction_id}, {self.group_id}, {self.account_id}, {self.counterparty_id}, "
                f"{self.bill_id}, {self.amount}, {self.type}, {self.due_date}, {self.transaction_date}, "
                f"{self.confirmed}, {self.description}")

class Bills(db.Model):
    bill_id = db.Column(String(255), primary_key=True)
    group_id = db.Column(String(255), ForeignKey('groups.group_id'))
    amount = db.Column(Float)
    recurrence = db.Column(Boolean)
    start_date = db.Column(TIMESTAMP)
    frequency = db.Column(String(255))
    reoccurrences = db.Column(Integer)

    def __str__(self):
        return (f"Bills: {self.bill_id}, {self.group_id}, {self.amount}, {self.recurrence}, "
                f"{self.start_date}, {self.frequency}, {self.reoccurrences}")

class GroupMembers(db.Model):
    group_id = db.Column(String(255), ForeignKey('groups.group_id'), primary_key=True)
    user_id = db.Column(String(255), ForeignKey('users.user_id'), primary_key=True)

    def __str__(self):
        return f"GroupMembers: {self.group_id}, {self.user_id}"
