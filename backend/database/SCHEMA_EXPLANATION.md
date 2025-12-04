# Database Schema Explanation

## Overview

This schema is designed for a personal finance management application. It allows users to track their income, expenses, accounts, and budgets in a secure, multi-user environment.

## Database Tables

### 1. **Categories Table** (`categories`)

**Purpose**: Stores transaction categories that users can assign to their income and expenses.

**Fields**:
- `id` (UUID) - Unique identifier
- `user_id` (UUID) - Links to the user who owns this category
- `name` (VARCHAR) - Category name (e.g., "Groceries", "Salary", "Rent")
- `type` (VARCHAR) - Either "income" or "expense"
- `color` (VARCHAR) - Hex color code for UI display (default: blue)
- `icon` (VARCHAR) - Icon identifier for UI
- `created_at` / `updated_at` - Timestamps

**Example Data**:
```
id: abc-123
user_id: user-456
name: "Groceries"
type: "expense"
color: "#FF5733"
icon: "shopping-cart"
```

**Key Features**:
- Each user can have their own categories
- A user cannot have duplicate category names of the same type
- Categories are separated by type (income vs expense)

---

### 2. **Accounts Table** (`accounts`)

**Purpose**: Represents financial accounts where money is stored or tracked (bank accounts, credit cards, cash, etc.).

**Fields**:
- `id` (UUID) - Unique identifier
- `user_id` (UUID) - Owner of the account
- `name` (VARCHAR) - Account name (e.g., "Chase Checking", "Cash Wallet")
- `type` (VARCHAR) - Account type: "checking", "savings", "credit_card", "cash", "investment", or "other"
- `balance` (DECIMAL) - Current account balance (default: 0.00)
- `currency` (VARCHAR) - Currency code (default: "USD")
- `is_active` (BOOLEAN) - Whether the account is currently active
- `created_at` / `updated_at` - Timestamps

**Example Data**:
```
id: acc-789
user_id: user-456
name: "Chase Checking"
type: "checking"
balance: 2500.00
currency: "USD"
is_active: true
```

**Key Features**:
- Tracks current balance for each account
- Supports multiple account types
- Can mark accounts as inactive without deleting them

---

### 3. **Transactions Table** (`transactions`)

**Purpose**: The core table that stores all financial transactions (income, expenses, transfers).

**Fields**:
- `id` (UUID) - Unique identifier
- `user_id` (UUID) - Owner of the transaction
- `account_id` (UUID) - Which account this transaction belongs to (references accounts table)
- `category_id` (UUID, optional) - Category for this transaction (references categories table)
- `amount` (DECIMAL) - Transaction amount (must be positive)
- `type` (VARCHAR) - "income", "expense", or "transfer"
- `description` (TEXT) - Optional description/notes
- `date` (DATE) - When the transaction occurred
- `created_at` / `updated_at` - Timestamps

**Example Data**:
```
id: txn-111
user_id: user-456
account_id: acc-789
category_id: cat-222
amount: 150.50
type: "expense"
description: "Weekly groceries"
date: 2024-01-15
```

**Key Features**:
- Links transactions to accounts and categories
- Supports three transaction types
- Category is optional (can be null)
- When a category is deleted, transactions keep the category_id as NULL (doesn't break)

---

### 4. **Budgets Table** (`budgets`)

**Purpose**: Allows users to set spending limits for categories over specific time periods.

**Fields**:
- `id` (UUID) - Unique identifier
- `user_id` (UUID) - Owner of the budget
- `category_id` (UUID) - Which category this budget applies to
- `amount` (DECIMAL) - Budget limit amount
- `period` (VARCHAR) - "weekly", "monthly", or "yearly"
- `start_date` (DATE) - When the budget period starts
- `end_date` (DATE) - When the budget period ends
- `created_at` / `updated_at` - Timestamps

**Example Data**:
```
id: bud-333
user_id: user-456
category_id: cat-222
amount: 500.00
period: "monthly"
start_date: 2024-01-01
end_date: 2024-01-31
```

**Key Features**:
- Budgets are tied to specific categories
- Flexible time periods (weekly, monthly, yearly)
- Can track spending against budget limits

---

### 5. **User Profiles Table** (`user_profiles`)

**Purpose**: Extends Supabase's built-in `auth.users` table with additional user information.

**Fields**:
- `id` (UUID) - References auth.users(id) - same as user ID
- `full_name` (VARCHAR) - User's full name
- `avatar_url` (TEXT) - URL to user's profile picture
- `currency` (VARCHAR) - User's preferred currency (default: "USD")
- `timezone` (VARCHAR) - User's timezone (default: "UTC")
- `created_at` / `updated_at` - Timestamps

**Example Data**:
```
id: user-456
full_name: "John Doe"
avatar_url: "https://example.com/avatar.jpg"
currency: "USD"
timezone: "America/New_York"
```

**Key Features**:
- Automatically created when a user signs up (via trigger)
- Stores user preferences
- One profile per user (1:1 relationship with auth.users)

---

## Relationships Between Tables

```
auth.users (Supabase built-in)
    │
    ├── user_profiles (1:1) - One profile per user
    │
    ├── categories (1:many) - User can have many categories
    │       │
    │       └── transactions (many:1) - Many transactions can use one category
    │       └── budgets (many:1) - Many budgets can use one category
    │
    ├── accounts (1:many) - User can have many accounts
    │       │
    │       └── transactions (many:1) - Many transactions belong to one account
    │
    ├── transactions (1:many) - User can have many transactions
    │
    └── budgets (1:many) - User can have many budgets
```

**Visual Flow**:
```
User signs up
    ↓
Profile automatically created
    ↓
User creates accounts (checking, savings, etc.)
    ↓
User creates categories (groceries, salary, etc.)
    ↓
User records transactions (links to account + category)
    ↓
User sets budgets (links to category)
```

---

## Security Features

### Row Level Security (RLS)

**What it does**: Ensures users can only see and modify their own data, even if they try to access the database directly.

**How it works**:
- Every table has RLS enabled
- Policies check `auth.uid()` (current logged-in user's ID)
- Users can only SELECT, INSERT, UPDATE, DELETE their own rows

**Example**:
- User A tries to access User B's transactions → **Blocked**
- User A tries to access their own transactions → **Allowed**

### Policies Created

For each table, there are 4 policies:
1. **SELECT** - Users can view their own data
2. **INSERT** - Users can create their own data
3. **UPDATE** - Users can modify their own data
4. **DELETE** - Users can delete their own data

---

## Automatic Features (Triggers)

### 1. **Auto-create User Profile**

**Trigger**: `on_auth_user_created`
**When**: After a new user is created in `auth.users`
**What it does**: Automatically creates a corresponding row in `user_profiles`

**Why**: Saves you from manually creating profiles in your application code.

### 2. **Auto-update Timestamps**

**Trigger**: `update_updated_at_column`
**When**: Before any UPDATE operation on a table
**What it does**: Automatically sets `updated_at` to current timestamp

**Why**: Keeps track of when records were last modified without manual updates.

---

## Performance Optimizations

### Indexes Created

Indexes speed up database queries. We've created indexes on:

1. **Transactions table**:
   - `user_id` - Fast lookup of user's transactions
   - `account_id` - Fast filtering by account
   - `category_id` - Fast filtering by category
   - `date` - Fast date range queries

2. **Categories table**:
   - `user_id` - Fast lookup of user's categories

3. **Accounts table**:
   - `user_id` - Fast lookup of user's accounts

4. **Budgets table**:
   - `user_id` - Fast lookup of user's budgets

**Why indexes matter**: Without indexes, querying "get all transactions for user X" would scan the entire table. With indexes, it's much faster.

---

## Data Types Explained

- **UUID**: Universally Unique Identifier - a long random string that's guaranteed to be unique (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- **DECIMAL(15, 2)**: Stores money amounts with 15 total digits, 2 after decimal point (e.g., `1234567890123.45`)
- **VARCHAR(n)**: Variable-length text with max length `n`
- **TEXT**: Unlimited length text
- **DATE**: Date without time (e.g., `2024-01-15`)
- **TIMESTAMP WITH TIME ZONE**: Date and time with timezone info
- **BOOLEAN**: True or false

---

## Example Use Cases

### Scenario 1: User Records a Purchase

1. User has account "Chase Checking" (balance: $1000)
2. User creates transaction:
   - Account: "Chase Checking"
   - Category: "Groceries"
   - Amount: $50
   - Type: "expense"
3. **Backend automatically**: Updates account balance to $950

### Scenario 2: User Sets a Monthly Budget

1. User creates budget:
   - Category: "Groceries"
   - Amount: $500
   - Period: "monthly"
   - Dates: Jan 1 - Jan 31
2. User can later query: "How much did I spend on groceries this month?"
3. Compare spending vs budget to see if over/under

### Scenario 3: User Transfers Money

1. User has "Chase Checking" ($1000) and "Savings" ($5000)
2. User creates transaction:
   - Account: "Chase Checking"
   - Amount: $200
   - Type: "transfer"
   - Description: "Transfer to savings"
3. **Backend automatically**: 
   - Deducts $200 from "Chase Checking" (new balance: $800)
   - Could create second transaction for "Savings" account (adds $200)

---

## Design Decisions

### Why UUID instead of auto-incrementing integers?

- **Security**: Harder to guess other users' IDs
- **Scalability**: Can generate IDs without database round-trip
- **Distributed systems**: Works better across multiple servers

### Why separate categories for income and expense?

- **Clarity**: "Salary" is income, "Rent" is expense - they're fundamentally different
- **Validation**: Prevents assigning wrong type to transaction
- **UI**: Can display income and expense categories separately

### Why ON DELETE CASCADE for accounts?

- If user deletes an account, all its transactions are also deleted
- **Alternative**: ON DELETE SET NULL (keeps transactions but removes account reference)
- **Chosen**: CASCADE because transactions without an account don't make sense

### Why ON DELETE SET NULL for categories?

- If user deletes a category, transactions keep their data but category_id becomes NULL
- **Reason**: Transactions are historical records - we don't want to lose them
- User can later recategorize if needed

---

## Summary

This schema provides:
✅ **Multi-user support** with complete data isolation
✅ **Flexible account management** (multiple account types)
✅ **Categorization system** for better organization
✅ **Transaction tracking** with relationships to accounts and categories
✅ **Budget management** for spending control
✅ **Automatic features** (profiles, timestamps)
✅ **Security** (RLS policies)
✅ **Performance** (indexes on key fields)

The schema is designed to be:
- **Scalable**: Can handle many users and transactions
- **Secure**: Users can't access each other's data
- **Flexible**: Easy to add new features
- **Maintainable**: Clear relationships and constraints

