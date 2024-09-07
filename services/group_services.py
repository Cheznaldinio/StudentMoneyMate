# services/group_service.py

from collections import defaultdict
from datetime import datetime
from databases import Users, Groups, Bills, GroupMembers

class GroupService:
    @staticmethod
    def get_user_groups(user_id):
        groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
            .filter(GroupMembers.user_id == user_id).all()

        return groups

    @staticmethod
    def calculate_flat_bills(flat_groups):
        flat_bills_data = []
        total_flat_owed = 0.0

        if flat_groups:
            grouped_bills = defaultdict(list)
            for group in flat_groups:
                bills = Bills.query.filter_by(group_id=group.group_id).all()
                for bill in bills:
                    grouped_bills[(bill.bill_name, bill.amount, bill.group_id)].append(bill)

            for (bill_name, amount, group_id), bills in grouped_bills.items():
                bills.sort(key=lambda x: x.start_date)
                next_bill = None
                current_date = datetime.now()
                for bill in bills:
                    if bill.start_date and bill.start_date > current_date:
                        next_bill = bill
                        break

                for bill in bills:
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
        return flat_bills_data, total_flat_owed

    @staticmethod
    def calculate_non_flat_bills(non_flat_groups):
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
        return non_flat_bills_data, total_non_flat_owed, individual_owed

    @staticmethod
    def get_managed_groups(user_id):
        managed_flat_groups = Groups.query.filter_by(manager_id=user_id, group_type='flat').all()
        managed_non_flat_groups = Groups.query.filter(Groups.manager_id == user_id, Groups.group_type != 'flat').all()
        return managed_flat_groups, managed_non_flat_groups

    @staticmethod
    def get_group_details(user_id):
        """
        Retrieves details of the groups (both flat and non-flat) that the user is a part of.
        """
        all_groups = Groups.query.join(GroupMembers, Groups.group_id == GroupMembers.group_id) \
            .filter(GroupMembers.user_id == user_id).all()

        group_info = []

        for group in all_groups:
            group_manager = Users.query.get(group.manager_id)
            is_manager = group.manager_id == user_id
            members_count = GroupMembers.query.filter_by(group_id=group.group_id).count()
            bills = Bills.query.filter_by(group_id=group.group_id).all()

            bill_details = [
                {
                    'bill_name': bill.bill_name,
                    'amount': bill.amount,
                    'start_date': bill.start_date.strftime('%Y-%m-%d') if bill.start_date else 'N/A'
                } for bill in bills
            ]

            group_info.append({
                'group_id': group.group_id,
                'group_name': group.group_name,
                'group_type': group.group_type,
                'manager_name': group_manager.user_name if group_manager else 'N/A',
                'is_manager': is_manager,
                'members_count': members_count,
                'bills': bill_details
            })

        return group_info
