"""
Pydantic models for FinanceApp - Asset Tracking
"""

from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import Optional, Union
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class AssetType(str, Enum):
    STOCK = "stock"
    MUTUAL_FUND = "mutual_fund"
    BANK_ACCOUNT = "bank_account"
    FIXED_DEPOSIT = "fixed_deposit"


class BankAccountType(str, Enum):
    SAVINGS = "savings"
    CHECKING = "checking"
    CURRENT = "current"


# Base Asset Model
class AssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: AssetType
    current_value: Union[Decimal, str, float] = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="USD", max_length=3)
    notes: Optional[str] = None
    is_active: bool = Field(default=True)
    
    @field_validator('current_value', mode='before')
    @classmethod
    def convert_current_value(cls, v):
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(str(v))
        return v


# Stock-specific fields
class StockFields(BaseModel):
    stock_symbol: str = Field(..., min_length=1, max_length=20)
    stock_exchange: Optional[str] = Field(None, max_length=50)
    quantity: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    purchase_date: date
    current_price: Optional[Decimal] = Field(None, gt=0)


# Mutual Fund-specific fields
class MutualFundFields(BaseModel):
    mutual_fund_code: str = Field(..., min_length=1, max_length=50)
    fund_house: Optional[str] = Field(None, max_length=255)
    nav: Optional[Decimal] = Field(None, gt=0)  # Net Asset Value
    units: Decimal = Field(..., gt=0)
    nav_purchase_date: Optional[date] = None


# Bank Account-specific fields
class BankAccountFields(BaseModel):
    account_number: Optional[str] = Field(None, max_length=100)
    bank_name: str = Field(..., min_length=1, max_length=255)
    account_type: BankAccountType
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)


# Fixed Deposit-specific fields
class FixedDepositFields(BaseModel):
    fd_number: Optional[str] = Field(None, max_length=100)
    principal_amount: Decimal = Field(..., gt=0)
    fd_interest_rate: Decimal = Field(..., ge=0, le=100)
    maturity_date: date
    start_date: date


# Asset Create Models (with type-specific validation)
class AssetCreate(AssetBase):
    class Config:
        json_encoders = {
            Decimal: str
        }
        # Allow string input for Decimal fields
        json_schema_extra = {
            "example": {
                "name": "Example Asset",
                "type": "stock",
                "current_value": "1000.00",
                "currency": "USD"
            }
        }
    # Stock fields
    stock_symbol: Optional[str] = Field(None, max_length=20)
    stock_exchange: Optional[str] = Field(None, max_length=50)
    quantity: Optional[Decimal] = Field(None, gt=0)
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    purchase_date: Optional[date] = None
    current_price: Optional[Decimal] = Field(None, gt=0)
    
    # Mutual Fund fields
    mutual_fund_code: Optional[str] = Field(None, max_length=50)
    fund_house: Optional[str] = Field(None, max_length=255)
    nav: Optional[Decimal] = Field(None, gt=0)
    units: Optional[Decimal] = Field(None, gt=0)
    nav_purchase_date: Optional[date] = None
    
    # Bank Account fields
    account_number: Optional[str] = Field(None, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=255)
    account_type: Optional[BankAccountType] = None
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    
    # Fixed Deposit fields
    fd_number: Optional[str] = Field(None, max_length=100)
    principal_amount: Optional[Decimal] = Field(None, gt=0)
    fd_interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    maturity_date: Optional[date] = None
    start_date: Optional[date] = None

    @field_validator('type')
    @classmethod
    def validate_asset_type(cls, v, values):
        """Validate that required fields are present based on asset type"""
        # Note: This validation is done at the API level in the router
        # Pydantic field_validator runs before all fields are set, so we do basic validation here
        return v
    
    # Validators to convert strings to Decimal for all Decimal fields
    @field_validator('quantity', 'purchase_price', 'current_price', 'nav', 'units', 
                     'interest_rate', 'principal_amount', 'fd_interest_rate', mode='before')
    @classmethod
    def convert_decimal_fields(cls, v):
        """Convert string or float to Decimal"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return Decimal(v)
            except:
                return None
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, int):
            return Decimal(str(v))
        return v
    
    # Validator to convert string dates to date objects
    @field_validator('purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date', mode='before')
    @classmethod
    def convert_date_fields(cls, v):
        """Convert string dates to date objects"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                from datetime import datetime
                # Try parsing ISO format (YYYY-MM-DD)
                return datetime.strptime(v, '%Y-%m-%d').date()
            except:
                return None
        return v
    
    def model_validate_asset_fields(self):
        """Custom validation after all fields are set"""
        if self.type == AssetType.STOCK:
            if not self.stock_symbol or not self.quantity or not self.purchase_price or not self.purchase_date:
                raise ValueError("stock_symbol, quantity, purchase_price, and purchase_date are required for stock assets")
        
        elif self.type == AssetType.MUTUAL_FUND:
            if not self.mutual_fund_code or not self.units:
                raise ValueError("mutual_fund_code and units are required for mutual fund assets")
        
        elif self.type == AssetType.BANK_ACCOUNT:
            if not self.bank_name or not self.account_type:
                raise ValueError("bank_name and account_type are required for bank account assets")
        
        elif self.type == AssetType.FIXED_DEPOSIT:
            if not self.principal_amount or not self.fd_interest_rate or not self.maturity_date or not self.start_date:
                raise ValueError("principal_amount, fd_interest_rate, maturity_date, and start_date are required for fixed deposit assets")


# Asset Update Model
class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    current_value: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    
    # Stock fields
    stock_symbol: Optional[str] = Field(None, max_length=20)
    stock_exchange: Optional[str] = Field(None, max_length=50)
    quantity: Optional[Decimal] = Field(None, gt=0)
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    purchase_date: Optional[date] = None
    current_price: Optional[Decimal] = Field(None, gt=0)
    
    # Mutual Fund fields
    mutual_fund_code: Optional[str] = Field(None, max_length=50)
    fund_house: Optional[str] = Field(None, max_length=255)
    nav: Optional[Decimal] = Field(None, gt=0)
    units: Optional[Decimal] = Field(None, gt=0)
    nav_purchase_date: Optional[date] = None
    
    # Bank Account fields
    account_number: Optional[str] = Field(None, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=255)
    account_type: Optional[BankAccountType] = None
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    
    # Fixed Deposit fields
    fd_number: Optional[str] = Field(None, max_length=100)
    principal_amount: Optional[Decimal] = Field(None, gt=0)
    fd_interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    maturity_date: Optional[date] = None
    start_date: Optional[date] = None


# Asset Response Model
class Asset(AssetBase):
    id: str
    user_id: str
    
    # Stock fields
    stock_symbol: Optional[str] = None
    stock_exchange: Optional[str] = None
    quantity: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    current_price: Optional[Decimal] = None
    
    # Mutual Fund fields
    mutual_fund_code: Optional[str] = None
    fund_house: Optional[str] = None
    nav: Optional[Decimal] = None
    units: Optional[Decimal] = None
    nav_purchase_date: Optional[date] = None
    
    # Bank Account fields
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    interest_rate: Optional[Decimal] = None
    
    # Fixed Deposit fields
    fd_number: Optional[str] = None
    principal_amount: Optional[Decimal] = None
    fd_interest_rate: Optional[Decimal] = None
    maturity_date: Optional[date] = None
    start_date: Optional[date] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# User Profile Models
class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Expense Models
class ExpenseBase(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    amount: Union[Decimal, str, float] = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    category: Optional[str] = Field(None, max_length=100)
    expense_date: date
    notes: Optional[str] = None
    
    @field_validator('amount', mode='before')
    @classmethod
    def convert_amount(cls, v):
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(str(v))
        return v
    
    @field_validator('expense_date', mode='before')
    @classmethod
    def convert_date_field(cls, v):
        """Convert string dates to date objects"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                from datetime import datetime
                return datetime.strptime(v, '%Y-%m-%d').date()
            except:
                return None
        return v


class ExpenseCreate(ExpenseBase):
    class Config:
        json_encoders = {
            Decimal: str
        }
        json_schema_extra = {
            "example": {
                "description": "Lunch at restaurant",
                "amount": "25.50",
                "currency": "USD",
                "category": "Food",
                "expense_date": "2024-01-15",
                "notes": "Business lunch"
            }
        }


class ExpenseUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[Union[Decimal, str, float]] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    category: Optional[str] = Field(None, max_length=100)
    expense_date: Optional[date] = None
    notes: Optional[str] = None
    
    @field_validator('amount', mode='before')
    @classmethod
    def convert_amount(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(str(v))
        return v
    
    @field_validator('expense_date', mode='before')
    @classmethod
    def convert_date_field(cls, v):
        """Convert string dates to date objects"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                from datetime import datetime
                return datetime.strptime(v, '%Y-%m-%d').date()
            except:
                return None
        return v


class Expense(ExpenseBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
