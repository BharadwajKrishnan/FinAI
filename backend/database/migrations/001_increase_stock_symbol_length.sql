-- Migration: Increase stock_symbol column length from VARCHAR(20) to VARCHAR(255)
-- Date: 2025-12-29
-- Description: Remove the 20 character limit on stock_symbol to allow full company names

-- Alter the stock_symbol column to allow longer values
ALTER TABLE assets 
ALTER COLUMN stock_symbol TYPE VARCHAR(255);

-- Note: This migration is safe to run on existing databases
-- Existing data will be preserved, and the column will now accept up to 255 characters

