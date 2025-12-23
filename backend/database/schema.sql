-- FinanceApp Database Schema - Asset Tracking
-- Run this SQL in your Supabase SQL Editor to create the tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Financial Assets table - unified table for all asset types
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Asset identification
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('stock', 'mutual_fund', 'bank_account', 'fixed_deposit', 'insurance_policy', 'commodity')),
    
    -- Common fields for all asset types
    current_value DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Stock-specific fields (NULL for other types)
    stock_symbol VARCHAR(20),  -- e.g., "AAPL", "GOOGL"
    stock_exchange VARCHAR(50), -- e.g., "NASDAQ", "NYSE"
    quantity DECIMAL(15, 4),   -- Number of shares
    purchase_price DECIMAL(15, 4), -- Price per share when purchased
    purchase_date DATE,
    current_price DECIMAL(15, 4), -- Current market price per share
    
    -- Mutual Fund specific fields (NULL for other types)
    mutual_fund_code VARCHAR(50), -- Fund code/identifier
    fund_house VARCHAR(255), -- Fund management company
    nav DECIMAL(15, 4), -- Net Asset Value
    units DECIMAL(15, 4), -- Number of units held
    nav_purchase_date DATE, -- Date when units were purchased
    
    -- Bank Account specific fields (NULL for other types)
    account_number VARCHAR(100), -- Masked or partial account number
    bank_name VARCHAR(255),
    account_type VARCHAR(50), -- e.g., "savings", "checking", "current"
    interest_rate DECIMAL(5, 2), -- Annual interest rate percentage
    
    -- Fixed Deposit specific fields (NULL for other types)
    fd_number VARCHAR(100), -- Fixed deposit number/reference
    principal_amount DECIMAL(15, 2), -- Initial deposit amount
    fd_interest_rate DECIMAL(5, 2), -- Annual interest rate percentage
    maturity_date DATE, -- When FD matures
    start_date DATE, -- When FD was started
    
    -- Insurance Policy specific fields (NULL for other types)
    policy_number VARCHAR(100), -- Insurance policy number
    amount_insured DECIMAL(15, 2), -- Sum insured/coverage amount
    issue_date DATE, -- Date when policy was issued
    date_of_maturity DATE, -- Date when policy matures
    premium DECIMAL(15, 2), -- Premium amount
    nominee VARCHAR(255), -- Nominee name
    premium_payment_date DATE, -- Next premium payment date
    
    -- Commodity specific fields (NULL for other types)
    commodity_name VARCHAR(255), -- Name of the commodity (e.g., "Gold", "Silver")
    form VARCHAR(50), -- Form of commodity (e.g., "ETF", "Physical", "Coin")
    commodity_quantity DECIMAL(15, 4), -- Quantity of commodity
    commodity_units VARCHAR(20), -- Units of measurement (e.g., "grams", "karat", "units")
    commodity_purchase_date DATE, -- Date when commodity was purchased
    commodity_purchase_price DECIMAL(15, 4), -- Purchase price per unit
    
    -- Additional metadata
    notes TEXT, -- User notes about the asset
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- User profiles table (extends auth.users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Chat messages table - stores conversation history
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    message_order INTEGER NOT NULL, -- Order of message in conversation (for sorting)
    context VARCHAR(20) DEFAULT 'assets', -- Context: 'assets' or 'expenses' to separate conversations
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Expenses table - stores daily expenses
CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    
    -- Expense details
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) DEFAULT 'USD',
    category VARCHAR(100), -- e.g., "Food", "Transport", "Shopping", "Bills", etc.
    expense_date DATE NOT NULL, -- Date when expense was made
    
    -- Additional metadata
    notes TEXT, -- User notes about the expense
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_user_type ON assets(user_id, type);
CREATE INDEX IF NOT EXISTS idx_assets_stock_symbol ON assets(stock_symbol) WHERE stock_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_assets_mutual_fund_code ON assets(mutual_fund_code) WHERE mutual_fund_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_order ON chat_messages(user_id, message_order);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_context ON chat_messages(user_id, context);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_context_order ON chat_messages(user_id, context, message_order);
CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category) WHERE category IS NOT NULL;

-- Enable Row Level Security (RLS)
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Users can only access their own data

-- Assets policies
CREATE POLICY "Users can view their own assets"
    ON assets FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own assets"
    ON assets FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own assets"
    ON assets FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own assets"
    ON assets FOR DELETE
    USING (auth.uid() = user_id);

-- User profiles policies
CREATE POLICY "Users can view their own profile"
    ON user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
    ON user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Chat messages policies
CREATE POLICY "Users can view their own chat messages"
    ON chat_messages FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own chat messages"
    ON chat_messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own chat messages"
    ON chat_messages FOR DELETE
    USING (auth.uid() = user_id);

-- Expenses policies
CREATE POLICY "Users can view their own expenses"
    ON expenses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own expenses"
    ON expenses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own expenses"
    ON expenses FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own expenses"
    ON expenses FOR DELETE
    USING (auth.uid() = user_id);

-- Function to automatically create user profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, name)
    VALUES (NEW.id, NEW.raw_user_meta_data->>'name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create profile on user creation
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to update updated_at
CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_expenses_updated_at BEFORE UPDATE ON expenses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
