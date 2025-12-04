# Asset-Based Database Schema Explanation

## Overview

This schema is designed for tracking financial assets. Users can record and manage their portfolio of:
- **Stocks** - Individual stock holdings
- **Mutual Funds** - Mutual fund investments
- **Bank Accounts** - Savings, checking, and current accounts
- **Fixed Deposits** - Fixed deposit investments

## Database Structure

### Single Unified Table: `assets`

Instead of separate tables for each asset type, we use a single `assets` table with type-specific fields. This design:
- ✅ Simplifies queries (one table to query)
- ✅ Makes it easy to get total portfolio value
- ✅ Allows flexible filtering by asset type
- ✅ Reduces database complexity

### Table Structure

```sql
assets
├── Common Fields (all asset types)
│   ├── id (UUID)
│   ├── user_id (UUID) - Links to user
│   ├── name (VARCHAR) - Asset name/description
│   ├── type (VARCHAR) - 'stock', 'mutual_fund', 'bank_account', 'fixed_deposit'
│   ├── current_value (DECIMAL) - Current total value
│   ├── currency (VARCHAR) - Currency code (USD, INR, etc.)
│   ├── notes (TEXT) - User notes
│   ├── is_active (BOOLEAN) - Active/inactive status
│   └── timestamps
│
├── Stock Fields (only for type='stock')
│   ├── stock_symbol - e.g., "AAPL", "GOOGL"
│   ├── stock_exchange - e.g., "NASDAQ", "NYSE"
│   ├── quantity - Number of shares
│   ├── purchase_price - Price per share when bought
│   ├── purchase_date - When shares were purchased
│   └── current_price - Current market price per share
│
├── Mutual Fund Fields (only for type='mutual_fund')
│   ├── mutual_fund_code - Fund identifier
│   ├── fund_house - Fund management company
│   ├── nav - Net Asset Value
│   ├── units - Number of units held
│   └── nav_purchase_date - When units were purchased
│
├── Bank Account Fields (only for type='bank_account')
│   ├── account_number - Account identifier
│   ├── bank_name - Bank name
│   ├── account_type - 'savings', 'checking', 'current'
│   └── interest_rate - Annual interest rate %
│
└── Fixed Deposit Fields (only for type='fixed_deposit')
    ├── fd_number - FD reference number
    ├── principal_amount - Initial deposit
    ├── fd_interest_rate - Annual interest rate %
    ├── maturity_date - When FD matures
    └── start_date - When FD was started
```

## Asset Type Details

### 1. **Stocks** (`type = 'stock'`)

**Required Fields:**
- `name` - e.g., "Apple Inc."
- `stock_symbol` - e.g., "AAPL"
- `quantity` - Number of shares owned
- `purchase_price` - Price per share when purchased
- `purchase_date` - Date of purchase
- `current_value` - Total current value (quantity × current_price)

**Optional Fields:**
- `stock_exchange` - Exchange where stock is listed
- `current_price` - Current market price (can be updated)

**Example:**
```json
{
  "name": "Apple Inc.",
  "type": "stock",
  "stock_symbol": "AAPL",
  "stock_exchange": "NASDAQ",
  "quantity": 10,
  "purchase_price": 150.00,
  "purchase_date": "2024-01-15",
  "current_price": 175.50,
  "current_value": 1755.00,
  "currency": "USD"
}
```

### 2. **Mutual Funds** (`type = 'mutual_fund'`)

**Required Fields:**
- `name` - e.g., "S&P 500 Index Fund"
- `mutual_fund_code` - Fund identifier
- `units` - Number of units held
- `current_value` - Total current value (units × nav)

**Optional Fields:**
- `fund_house` - Fund management company
- `nav` - Current Net Asset Value per unit
- `nav_purchase_date` - When units were purchased

**Example:**
```json
{
  "name": "Vanguard S&P 500 Index Fund",
  "type": "mutual_fund",
  "mutual_fund_code": "VOO",
  "fund_house": "Vanguard",
  "units": 50.5,
  "nav": 420.00,
  "current_value": 21210.00,
  "currency": "USD"
}
```

### 3. **Bank Accounts** (`type = 'bank_account'`)

**Required Fields:**
- `name` - e.g., "Chase Savings Account"
- `bank_name` - Bank name
- `account_type` - 'savings', 'checking', or 'current'
- `current_value` - Current account balance

**Optional Fields:**
- `account_number` - Account identifier (can be masked)
- `interest_rate` - Annual interest rate percentage

**Example:**
```json
{
  "name": "Chase Savings",
  "type": "bank_account",
  "bank_name": "Chase Bank",
  "account_type": "savings",
  "account_number": "****1234",
  "current_value": 5000.00,
  "interest_rate": 2.5,
  "currency": "USD"
}
```

### 4. **Fixed Deposits** (`type = 'fixed_deposit'`)

**Required Fields:**
- `name` - e.g., "FD - HDFC Bank"
- `principal_amount` - Initial deposit amount
- `fd_interest_rate` - Annual interest rate percentage
- `start_date` - When FD was started
- `maturity_date` - When FD matures
- `current_value` - Current value (principal + accrued interest)

**Optional Fields:**
- `fd_number` - FD reference number

**Example:**
```json
{
  "name": "HDFC Fixed Deposit",
  "type": "fixed_deposit",
  "fd_number": "FD-2024-001",
  "principal_amount": 10000.00,
  "fd_interest_rate": 6.5,
  "start_date": "2024-01-01",
  "maturity_date": "2025-01-01",
  "current_value": 10650.00,
  "currency": "USD"
}
```

## Key Features

### 1. **Flexible Design**
- Single table handles all asset types
- Type-specific fields are NULL for other types
- Easy to add new asset types in the future

### 2. **Portfolio Tracking**
- `current_value` field tracks total value of each asset
- Easy to calculate total portfolio value
- Can filter and group by asset type

### 3. **Security (Row Level Security)**
- Users can only see their own assets
- RLS policies enforce data isolation
- Even direct database access is secure

### 4. **Performance**
- Indexes on `user_id`, `type`, and `user_id + type`
- Fast queries for user-specific assets
- Indexes on `stock_symbol` and `mutual_fund_code` for lookups

## API Endpoints

### Asset Management
- `GET /api/assets` - Get all assets (with optional filters)
- `POST /api/assets` - Create a new asset
- `GET /api/assets/{id}` - Get specific asset
- `PUT /api/assets/{id}` - Update asset
- `DELETE /api/assets/{id}` - Delete asset

### Portfolio Summary
- `GET /api/assets/summary/total` - Get total portfolio value
- `GET /api/assets/summary/by-type` - Get assets grouped by type

## Example Use Cases

### Use Case 1: Add a Stock
```json
POST /api/assets
{
  "name": "Apple Inc.",
  "type": "stock",
  "stock_symbol": "AAPL",
  "stock_exchange": "NASDAQ",
  "quantity": 10,
  "purchase_price": 150.00,
  "purchase_date": "2024-01-15",
  "current_price": 175.50,
  "current_value": 1755.00,
  "currency": "USD"
}
```

### Use Case 2: Add a Bank Account
```json
POST /api/assets
{
  "name": "Chase Savings",
  "type": "bank_account",
  "bank_name": "Chase Bank",
  "account_type": "savings",
  "current_value": 5000.00,
  "interest_rate": 2.5,
  "currency": "USD"
}
```

### Use Case 3: Get Portfolio Summary
```json
GET /api/assets/summary/total
Response:
{
  "total_value": 50000.00,
  "currency": "USD",
  "asset_count": 8
}

GET /api/assets/summary/by-type
Response:
{
  "stock": {"count": 3, "total_value": 15000.00},
  "mutual_fund": {"count": 2, "total_value": 20000.00},
  "bank_account": {"count": 2, "total_value": 10000.00},
  "fixed_deposit": {"count": 1, "total_value": 5000.00}
}
```

## Design Decisions

### Why Single Table Instead of Separate Tables?

**Pros:**
- Simpler queries (one table)
- Easy portfolio aggregation
- Flexible filtering
- Less complex joins

**Cons:**
- Many NULL fields (but that's acceptable)
- Slightly larger table size

**Decision**: Single table is better for this use case because:
- Users typically have few assets of each type
- Portfolio queries need to aggregate across all types
- Simpler API and code

### Field Naming Convention

- Type-specific fields are prefixed with their type (e.g., `stock_symbol`, `fd_interest_rate`)
- This makes it clear which fields belong to which asset type
- Prevents confusion when reading the schema

### Current Value Tracking

- `current_value` is stored directly (not calculated)
- Allows manual updates if needed
- Can be updated via API when market prices change
- Future: Could add automatic price updates via external APIs

## Future Enhancements

Possible additions:
1. **Price History** - Track historical prices for stocks/mutual funds
2. **Transactions** - Record buy/sell transactions
3. **Dividends/Interest** - Track income from assets
4. **Performance Metrics** - Calculate returns, gains/losses
5. **Asset Allocation** - Percentage breakdown by type
6. **Alerts** - Notifications for price changes, maturity dates

## Summary

This schema provides:
✅ **Unified asset tracking** - All assets in one table
✅ **Type flexibility** - Supports 4 asset types with room to grow
✅ **Portfolio management** - Easy aggregation and summary
✅ **Security** - RLS ensures data isolation
✅ **Performance** - Indexed for fast queries
✅ **Extensibility** - Easy to add new asset types or fields

The design prioritizes simplicity and usability while maintaining flexibility for future enhancements.

