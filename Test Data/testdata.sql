-- Create Users table
CREATE TABLE Users (
    user_id VARCHAR(255) PRIMARY KEY,
    user_name VARCHAR(255),
    email VARCHAR(255),
    password VARCHAR(255),
    admin BOOLEAN
);

-- Insert data into Users table
INSERT INTO Users (user_id, user_name, email, password, admin) VALUES
('user1', 'john_doe', 'john.doe@example.com', 'password123', FALSE),
('user2', 'jane_smith', 'jane.smith@example.com', 'password456', FALSE),
('user3', 'michael_brown', 'michael.brown@example.com', 'password789', FALSE),
('user4', 'emily_white', 'emily.white@example.com', 'password101', FALSE);

-- Drop Users table
DROP TABLE Users;

-- Select from Users table
SELECT * FROM Users;

-- Create Groups table
CREATE TABLE Groups (
    group_id VARCHAR(255) PRIMARY KEY,
    group_name VARCHAR(255),
    manager_id VARCHAR(255),
    group_type VARCHAR(255),
    FOREIGN KEY (manager_id) REFERENCES Users(user_id)
);

-- Drop Groups table
DROP TABLE Groups;

-- Select from Groups table
SELECT * FROM Groups;

-- Create Accounts table
CREATE TABLE Accounts (
    account_id VARCHAR(255) PRIMARY KEY,
    account_type VARCHAR(255),
    entity_id VARCHAR(255)
);

-- Drop Accounts table
DROP TABLE Accounts;

-- Select from Accounts table
SELECT * FROM Accounts;

-- Create Ledger table
CREATE TABLE Ledger (
    transaction_id VARCHAR(255) PRIMARY KEY,
    group_id VARCHAR(255),
    account_id VARCHAR(255),
    counterparty_id VARCHAR(255),
    bill_id VARCHAR(255),
    amount REAL,
    type VARCHAR(255),
    due_date TIMESTAMP,
    transaction_date TIMESTAMP,
    confirmed BOOLEAN,
    description VARCHAR(255),
    FOREIGN KEY (group_id) REFERENCES Groups(group_id),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id),
    FOREIGN KEY (counterparty_id) REFERENCES Accounts(account_id),
    FOREIGN KEY (bill_id) REFERENCES Bills(bill_id)
);

-- Drop Ledger table
DROP TABLE Ledger;

-- Select from Ledger table
SELECT * FROM Ledger;

-- Create Bills table
CREATE TABLE Bills (
    bill_id VARCHAR(255) PRIMARY KEY,
	bill_name VARCHAR(255),
    group_id VARCHAR(255),
    amount REAL,
    recurrence BOOLEAN,
    start_date TIMESTAMP,
    frequency VARCHAR(255),
    reoccurrences INTEGER,
    FOREIGN KEY (group_id) REFERENCES Groups(group_id)
);

-- Drop Bills table
DROP TABLE Bills CASCADE;

-- Select from Bills table
SELECT * FROM Bills;

INSERT INTO Bills (bill_id, bill_name, group_id, amount, recurrence, start_date, frequency, reoccurrences)
VALUES ('bill1', 'Rent', 'group1', 100.00, FALSE, CURRENT_TIMESTAMP - INTERVAL '1 DAY', 'monthly', 0);

INSERT INTO Bills (bill_id, bill_name, group_id, amount, recurrence, start_date, frequency, reoccurrences)
VALUES ('bill2', 'Food', 'group2', 30.00, FALSE, CURRENT_TIMESTAMP - INTERVAL '1 DAY', 'monthly', 0);

-- Create GroupMembers table
CREATE TABLE Group_Members (
    group_id VARCHAR(255),
    user_id VARCHAR(255),
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES Groups(group_id),
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- Drop GroupMembers table
DROP TABLE GroupMembers;

-- Select from GroupMembers table
SELECT * FROM GroupMembers;

-- Create a new group with Emily as the manager
INSERT INTO Groups (group_id, group_name, manager_id, group_type) VALUES
('group1', 'Current Users Group', 'user4', 'flat');

-- Insert all current users into the GroupMembers table for the new group
INSERT INTO group_members (group_id, user_id) VALUES
('group1', 'user1'),
('group1', 'user2'),
('group1', 'user3'),
('group1', 'user4');

INSERT INTO Groups (group_id, group_name, manager_id, group_type) VALUES
('group2', 'Minor Group', 'user3', 'subgroup');

-- Insert all current users into the GroupMembers table for the new group
INSERT INTO group_members (group_id, user_id) VALUES
('group2', 'user1'),
('group2', 'user2'),
('group2', 'user3');

SELECT * FROM Groups WHERE group_id = 'group1';

SELECT * FROM Group_Members;


WHERE group_id = 'group1';

SELECT * FROM Users WHERE user_id = 'user4';

SELECT * FROM GroupMembers WHERE user_id = 'user1';
