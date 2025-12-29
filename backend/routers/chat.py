"""
Chat/LLM API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import time
import random
import uuid
import asyncio
import csv
import io
from auth import get_current_user, security
from services.llm_service import llm_service
from services.asset_llm_service import asset_llm_service
from database.supabase_client import supabase, supabase_service, get_supabase_client_with_token
from models import AssetCreate, AssetUpdate
# File upload helper functions will be defined below

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None
    context: Optional[str] = "assets"  # "assets" or "expenses" to determine which system prompt to use


class ChatResponse(BaseModel):
    response: str
    message_id: str


class ChatHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Handle chat messages and return LLM response
    """
    try:
        # Extract user_id safely (matching pattern from assets router)
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Get context from request (default to "assets")
        # Handle both None and empty string cases
        context_value = request.context
        if not context_value or context_value == "":
            context = "assets"
        else:
            context = str(context_value).lower().strip()  # Normalize to lowercase and strip whitespace
        
        
        # Fetch user's portfolio from database (only if context is "assets")
        portfolio_data = {}
        if context == "assets":
            try:
                
                # Fetch family members first
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members = {str(member["id"]): member for member in (family_members_response.data if family_members_response.data else [])}
                
                # Use service role client (bypasses RLS, user already validated via get_current_user)
                # This avoids JWT expiration issues
                supabase_client = supabase_service
                
                # Fetch all assets (similar to assets endpoint - fetch all and filter in Python)
                # This handles NULL is_active values for backward compatibility
                response = supabase_client.table("assets").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
                all_assets = response.data if response.data else []
                
                # Filter by is_active - include assets where is_active is True or NULL (NULL treated as active)
                assets = [a for a in all_assets if a.get("is_active") is True or a.get("is_active") is None]
                
                # Organize assets by market (currency) and then by type
                # Also organize by family member for better context
                portfolio_data = {
                    "india": {
                        "currency": "INR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}  # Will be populated after processing all assets
                    },
                    "europe": {
                        "currency": "EUR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}  # Will be populated after processing all assets
                    }
                }
                
                for asset in assets:
                    currency = asset.get("currency", "USD")
                    # Determine market based on currency
                    market = "india" if currency == "INR" else "europe" if currency == "EUR" else "other"
                    
                    # Skip assets with other currencies (or add to a separate section if needed)
                    if market == "other":
                        continue
                    
                    # Get family member information
                    family_member_id = asset.get("family_member_id")
                    family_member_info = None
                    if family_member_id:
                        member = family_members.get(str(family_member_id))
                        if member:
                            family_member_info = {
                                "id": member.get("id"),
                                "name": member.get("name"),
                                "relationship": member.get("relationship")
                            }
                    
                    asset_info = {
                        "id": asset.get("id"),
                        "name": asset.get("name"),
                        "currency": currency,
                        "current_value": float(asset.get("current_value", 0)) if asset.get("current_value") else 0,
                        "created_at": asset.get("created_at"),
                        "updated_at": asset.get("updated_at"),
                        "family_member": family_member_info if family_member_info else {"name": "Self", "relationship": "Self"}
                    }
                    
                    asset_type = asset.get("type")
                    if asset_type == "stock":
                        asset_info.update({
                            "symbol": asset.get("stock_symbol"),
                            "quantity": float(asset.get("quantity", 0)) if asset.get("quantity") else 0,
                            "purchase_price": float(asset.get("purchase_price", 0)) if asset.get("purchase_price") else 0,
                            "current_price": float(asset.get("current_price", 0)) if asset.get("current_price") else 0,
                            "purchase_date": asset.get("purchase_date")
                        })
                        portfolio_data[market]["stocks"].append(asset_info)
                    elif asset_type == "mutual_fund":
                        asset_info.update({
                            "mutual_fund_code": asset.get("mutual_fund_code"),
                            "fund_house": asset.get("fund_house"),
                            "nav": float(asset.get("nav", 0)) if asset.get("nav") else 0,
                            "units": float(asset.get("units", 0)) if asset.get("units") else 0,
                            "nav_purchase_date": asset.get("nav_purchase_date")
                        })
                        portfolio_data[market]["mutual_funds"].append(asset_info)
                    elif asset_type == "bank_account":
                        asset_info.update({
                            "bank_name": asset.get("bank_name"),
                            "account_number": asset.get("account_number"),
                            "account_type": asset.get("account_type"),
                            "balance": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                        })
                        portfolio_data[market]["bank_accounts"].append(asset_info)
                    elif asset_type == "fixed_deposit":
                        asset_info.update({
                            "bank_name": asset.get("name"),
                            "principal_amount": float(asset.get("principal_amount", 0)) if asset.get("principal_amount") else 0,
                            "interest_rate": float(asset.get("fd_interest_rate", 0)) if asset.get("fd_interest_rate") else 0,
                            "start_date": asset.get("start_date"),
                            "maturity_date": asset.get("maturity_date"),
                            "maturity_amount": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                        })
                        portfolio_data[market]["fixed_deposits"].append(asset_info)
                    elif asset_type == "insurance_policy":
                        asset_info.update({
                            "insurance_name": asset.get("name"),
                            "policy_number": asset.get("policy_number"),
                            "amount_insured": float(asset.get("amount_insured", 0)) if asset.get("amount_insured") else 0,
                            "issue_date": asset.get("issue_date"),
                            "date_of_maturity": asset.get("date_of_maturity"),
                            "premium": float(asset.get("premium", 0)) if asset.get("premium") else 0,
                            "nominee": asset.get("nominee"),
                            "premium_payment_date": asset.get("premium_payment_date")
                        })
                        portfolio_data[market]["insurance_policies"].append(asset_info)
                    elif asset_type == "commodity":
                        asset_info.update({
                            "commodity_name": asset.get("commodity_name"),
                            "form": asset.get("form"),
                            "quantity": float(asset.get("commodity_quantity", 0)) if asset.get("commodity_quantity") else 0,
                            "units": asset.get("commodity_units"),
                            "purchase_date": asset.get("commodity_purchase_date"),
                            "purchase_price": float(asset.get("commodity_purchase_price", 0)) if asset.get("commodity_purchase_price") else 0,
                            "current_value": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                        })
                        portfolio_data[market]["commodities"].append(asset_info)
                
                # Organize assets by family member for better LLM context
                for market in ["india", "europe"]:
                    family_member_assets = {}
                    for asset_type in ["stocks", "mutual_funds", "bank_accounts", "fixed_deposits", "insurance_policies", "commodities"]:
                        for asset in portfolio_data[market][asset_type]:
                            family_member_name = asset.get("family_member", {}).get("name", "Self")
                            if family_member_name not in family_member_assets:
                                family_member_assets[family_member_name] = {
                                    "stocks": [],
                                    "mutual_funds": [],
                                    "bank_accounts": [],
                                    "fixed_deposits": [],
                                    "insurance_policies": [],
                                    "commodities": []
                                }
                            family_member_assets[family_member_name][asset_type].append(asset)
                    portfolio_data[market]["by_family_member"] = family_member_assets
                    
                    # Print summary by family member
                    for member_name, assets_by_type in family_member_assets.items():
                        total_assets = sum(len(assets_by_type[at]) for at in ["stocks", "mutual_funds", "bank_accounts", "fixed_deposits", "insurance_policies", "commodities"])
                
                # Add family members list to portfolio_data for system prompt
                portfolio_data["family_members"] = [
                    {"id": str(fm.get("id")), "name": fm.get("name"), "relationship": fm.get("relationship")}
                    for fm in family_members.values()
                ]
            except Exception as portfolio_error:
                # If portfolio fetch fails, continue without portfolio data
                import traceback
                portfolio_data = {
                    "india": {
                        "currency": "INR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}
                    },
                    "europe": {
                        "currency": "EUR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}
                    },
                    "family_members": []
                }
        
        # Fetch user's expenses from database (only if context is "expenses")
        expenses_data = []
        if context == "expenses":
            try:
                # Fetch family members first
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members = {str(member["id"]): member for member in (family_members_response.data if family_members_response.data else [])}
                
                # Use service role client (bypasses RLS, user already validated via get_current_user)
                # This avoids JWT expiration issues
                expenses_response = supabase_service.table("expenses").select("*").eq("user_id", user_id).order("expense_date", desc=True).execute()
                expenses = expenses_response.data if expenses_response.data else []
                
                
                # Limit expenses to most recent 500 to avoid prompt size issues
                # This prevents rate limiting from very large prompts
                max_expenses = 500
                if len(expenses) > max_expenses:
                    expenses = expenses[:max_expenses]
                
                # Format expenses for LLM context
                for expense in expenses:
                    # Get family member information
                    family_member_id = expense.get("family_member_id")
                    family_member_info = None
                    if family_member_id:
                        member = family_members.get(str(family_member_id))
                        if member:
                            family_member_info = {
                                "id": member.get("id"),
                                "name": member.get("name"),
                                "relationship": member.get("relationship")
                            }
                    
                    expense_info = {
                        "id": expense.get("id"),
                        "description": expense.get("description"),
                        "amount": float(expense.get("amount", 0)) if expense.get("amount") else 0,
                        "currency": expense.get("currency", "USD"),
                        "category": expense.get("category"),
                        "expense_date": expense.get("expense_date"),
                        "notes": expense.get("notes"),
                        "created_at": expense.get("created_at"),
                        "family_member": family_member_info if family_member_info else {"name": "Self", "relationship": "Self"}
                    }
                    expenses_data.append(expense_info)
                
                # Group expenses by currency and family member for easier analysis
                expenses_by_currency = {}
                expenses_by_family_member = {}
                for expense in expenses_data:
                    currency = expense.get("currency", "USD")
                    if currency not in expenses_by_currency:
                        expenses_by_currency[currency] = []
                    expenses_by_currency[currency].append(expense)
                    
                    # Group by family member
                    family_member_name = expense.get("family_member", {}).get("name", "Self")
                    if family_member_name not in expenses_by_family_member:
                        expenses_by_family_member[family_member_name] = []
                    expenses_by_family_member[family_member_name].append(expense)
                
                for currency, exp_list in expenses_by_currency.items():
                    total = sum(e.get("amount", 0) for e in exp_list)
                
                for member_name, exp_list in expenses_by_family_member.items():
                    total = sum(e.get("amount", 0) for e in exp_list)
                    
            except Exception as expenses_error:
                # If expenses fetch fails, continue without expense data
                import traceback
                expenses_data = []
        
        # Convert portfolio to JSON string (only if context is "assets")
        portfolio_json = ""
        if context == "assets":
            portfolio_json = json.dumps(portfolio_data, indent=2, default=str)
        
        # Convert expenses to JSON string (only if context is "expenses")
        expenses_json = ""
        if context == "expenses":
            # Organize expenses by family member for better LLM context
            expenses_by_family_member = {}
            for expense in expenses_data:
                family_member_name = expense.get("family_member", {}).get("name", "Self")
                if family_member_name not in expenses_by_family_member:
                    expenses_by_family_member[family_member_name] = []
                expenses_by_family_member[family_member_name].append(expense)
            
            expenses_data_with_grouping = {
                "all_expenses": expenses_data,
                "by_family_member": expenses_by_family_member
            }
            
            expenses_json = json.dumps(expenses_data_with_grouping, indent=2, default=str)
            # If expenses JSON is very large (>50KB), log a warning
            if len(expenses_json) > 50000:
                print(f"WARNING: Expenses JSON is very large ({len(expenses_json)} bytes). Consider pagination.")
        
        # Get current message order (max message_order + 1 for this user and context)
        try:
            max_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).eq("context", context).order("message_order", desc=True).limit(1).execute()
            if max_order_response.data and len(max_order_response.data) > 0:
                max_order = max_order_response.data[0].get("message_order", -1)
                # Safety check: if max_order is too large (timestamp-based), reset to 0
                # PostgreSQL INTEGER max is 2,147,483,647, but timestamps are ~1.7 trillion
                if max_order and max_order > 1000000000:  # If it's a timestamp (milliseconds), reset
                    print(f"WARNING: Found timestamp-based message_order ({max_order}), resetting to 0")
                    current_order = 0
                else:
                    current_order = (max_order if max_order is not None else -1) + 1
            else:
                current_order = 0
        except Exception as e:
            import traceback
            print(f"Error getting message order: {e}")
            traceback.print_exc()
            current_order = 0
        
        # Save user message to database
        try:
            user_message_data = {
                "user_id": user_id,
                "role": "user",
                "content": request.message,
                "message_order": current_order,
                "context": context  # Store context with message
            }
            insert_response = supabase_service.table("chat_messages").insert(user_message_data).execute()
            current_order += 1
        except Exception as e:
            import traceback
            # Continue even if save fails - don't break the chat flow
        
        # Convert conversation history to dict format for LLM service
        history = None
        if request.conversation_history:
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
        
        # Create system prompt based on context
        
        if context == "assets":
            # System prompt for Financial Assets tab
            
            # Build family members info string for the prompt
            family_members_info = ""
            if portfolio_data and "family_members" in portfolio_data:
                family_members_list = portfolio_data["family_members"]
                if family_members_list:
                    family_members_info = "AVAILABLE FAMILY MEMBERS:\n"
                    for member in family_members_list:
                        name = member.get("name", "")
                        relationship = member.get("relationship", "")
                        if relationship:
                            family_members_info += f"- {name} ({relationship})\n"
                        else:
                            family_members_info += f"- {name}\n"
                    family_members_info += "- Self (for your own assets)\n"
                else:
                    family_members_info = "AVAILABLE FAMILY MEMBERS:\n- Self (for your own assets)\n"
            else:
                family_members_info = "AVAILABLE FAMILY MEMBERS:\n- Self (for your own assets)\n"
            
            system_prompt = f"""<Role>
You are FinAI, an intelligent financial advisor. Your purpose is to help users manage their finances, understand markets, and make informed investment decisions. You must always communicate clearly, accurately, and professionally while providing factual, data-based insights.
</Role>

<Purpose>
1. Explain financial and investment concepts in simple, clear language.
2. Provide market updates, trend analysis, and data on instruments such as stocks, ETFs, bonds, and mutual funds.
3. Offer tailored investment advice using the user's portfolio and the latest financial data.
4. Deliver actionable insights with transparent explanations of risks and assumptions.
</Purpose>

<Data_Fetching_Rules>
1. Always fetch the most recent and reputable financial or market data available.
2. When displaying time-sensitive data (e.g., stock prices, yield rates), include both the source and timestamp.
3. If real-time data is temporarily unavailable, explicitly state that and provide the latest verified information.
</Data_Fetching_Rules>

<Portfolio_Access>
1. You have secure access to the user's investment portfolio at all times.
2. Use this portfolio data to generate personalized insights, including:
   1. Asset allocation summaries
   2. Portfolio risk and volatility assessments
   3. Diversification and sector exposure analysis
   4. Growth, yield, or loss projections
3. Maintain complete confidentiality and privacy for all portfolio data.
</Portfolio_Access>

<Advice_Rules>
1. When providing investment advice, always consider the user's portfolio composition, financial goals, and risk profile.
2. Support every recommendation with analytical reasoning (e.g., expected return, volatility, benchmark comparison).
3. After every piece of investment advice, include the cautionary statement from the <Caution_Note_Template>.
4. Never guarantee profits or make exaggerated or speculative statements.
</Advice_Rules>

<Caution_Note_Template>
Caution: Financial markets carry inherent risks. This recommendation is provided for informational purposes only and should not be taken as professional financial advice. Market conditions change rapidly. Always evaluate your risk tolerance and consult a certified financial advisor before making investment decisions.
</Caution_Note_Template>

<Behavior>
1. Maintain a neutral, objective, and professional tone at all times.
2. Avoid persuasive or emotionally driven language.
3. Use numerical lists, tables, or charts to summarize information effectively.
4. Clearly state data limitations or uncertain conditions when applicable.
5. Uphold user trust and confidentiality in all interactions.
6. Introduce yourself only once in the beginning of the conversation. Do not repeat yourself.
7. **ASSET MANAGEMENT CAPABILITIES**: You have the ability to add, update, and delete assets in the portfolio when explicitly requested by the user. However:
   - For normal questions, portfolio analysis, and investment advice, respond conversationally as usual
   - ONLY perform asset operations (add/update/delete) when the user explicitly asks you to do so (e.g., "add a stock", "update my portfolio", "delete this asset")
   - When performing asset operations, provide clear confirmation of what was done
   - For questions and analysis, continue to provide insights and recommendations without performing operations
</Behavior>

<Example_Introduction>
Hello, I'm FinAI — your personal finance assistant. I provide real-time financial insights, portfolio analysis, and data-driven investment guidance based on current market conditions. How can I assist you today?
</Example_Introduction>

<Current_Portfolio>
The user's current portfolio data is provided below in JSON format. Use this data to provide personalized insights and recommendations:

```json
{portfolio_json}
```

The portfolio is organized by market (India/Europe) and then by asset type. Each market has its own currency (INR for India, EUR for Europe).

IMPORTANT: The portfolio includes assets belonging to different family members. Each asset has a "family_member" field that indicates:
- If "family_member.name" is "Self", the asset belongs to the user themselves
- Otherwise, it shows the family member's name and relationship (e.g., "John (Father)", "Sarah (Daughter)")

The portfolio data also includes a "by_family_member" section for each market that organizes all assets by family member. Use this information to:
1. Provide insights specific to each family member's portfolio
2. Answer questions about which family member owns which assets
3. Calculate net worth or asset allocation for individual family members when requested
4. Understand the complete family financial picture when providing overall portfolio analysis

When analyzing the portfolio:
1. Consider the asset allocation across different types (stocks, mutual funds, bank accounts, fixed deposits, insurance policies, commodities) within each market
2. Analyze the distribution across different markets/currencies (INR for India, EUR for Europe)
3. Calculate total portfolio value and breakdown by asset type for each market separately
4. When asked about specific family members, use the "by_family_member" data to provide family member-specific insights
5. Provide insights on diversification, risk exposure, and potential improvements for each market
6. Reference specific assets by name, market, and family member when making recommendations
7. Note that India and Europe markets are separate - assets in one market do not affect the other
8. When calculating net worth or asset allocation, you can provide both overall family net worth and individual family member net worth
</Current_Portfolio>

<Asset_Management>
You have the capability to add, update, and delete assets in the portfolio when the user explicitly requests it.

{family_members_info}

AVAILABLE MARKETS:
- "india" (currency: INR, ₹, rupees) - for Indian stocks and assets
- "europe" (currency: EUR, €, euros) - for European stocks and assets

**IMPORTANT BEHAVIOR RULES:**
1. For normal questions, portfolio analysis, and investment advice, respond conversationally as usual. Do NOT perform any operations.
2. ONLY perform asset operations (add/update/delete) when the user explicitly asks you to do so with clear intent (e.g., "add a stock", "add Reliance stock", "update my portfolio", "delete this asset", "remove Mahindra stock").
3. When the user explicitly asks to ADD a stock, you must collect ALL required information:
   - Stock Name (e.g., "Reliance", "TCS", "Mahindra")
   - Stock Price (purchase price per share)
   - Quantity (number of shares)
   - Purchase Date (in YYYY-MM-DD format)
   - Stock Owner (family member name from the list above, or "self"/"me"/"myself" for the user)
   - Market (India or Europe)
   
   If ANY required information is missing, ask the user for it clearly. Do NOT assume or guess values. Extract information from the entire conversation history if available.

   When the user explicitly asks to ADD a bank account, you must collect ALL required information:
   - Account Name (e.g., "HDFC Savings", "SBI Current Account")
   - Bank Name (e.g., "HDFC", "SBI", "ICICI")
   - Account Number
   - Account Type (savings, checking, or current)
   - Current Balance (bank balance)
   - Account Owner (family member name from the list above, or "self"/"me"/"myself" for the user)
   - Market (India or Europe)
   
   If ANY required information is missing, ask the user for it clearly. Do NOT assume or guess values. Extract information from the entire conversation history if available.

4. When the user explicitly asks to UPDATE an asset, identify the asset from the portfolio and update only the fields they specify.

5. When the user explicitly asks to DELETE an asset, identify the asset from the portfolio and confirm the deletion.

6. After successfully performing an operation, provide a clear confirmation message (e.g., "Successfully added Reliance stock to your portfolio" or "Successfully updated the Mahindra stock").

Remember: Your primary role is to provide financial insights and analysis. Asset management operations are a secondary capability that should only be used when explicitly requested.
</Asset_Management>"""
        
        elif context == "expenses":
            # System prompt for Expense Tracker tab
            
            system_prompt = f"""<Role>
You are FinAI, an intelligent expense tracking and budgeting assistant. Your purpose is to help users track their expenses, analyze spending patterns, and make informed budgeting decisions. You must always communicate clearly, accurately, and professionally while providing factual, data-based insights.
</Role>

<Purpose>
1. Help users understand their spending patterns and trends over time.
2. Analyze expenses by category, month, year, or currency.
3. Provide budgeting recommendations and identify areas for cost optimization.
4. Calculate expense totals, averages, and comparisons as requested.
5. Deliver actionable insights with clear explanations.
</Purpose>

<Behavior>
1. Maintain a neutral, objective, and professional tone at all times.
2. Avoid judgmental language about spending habits.
3. Use numerical lists, tables, or charts to summarize expense information effectively.
4. Clearly state data limitations or uncertain conditions when applicable.
5. Uphold user trust and confidentiality in all interactions.
</Behavior>

<Example_Introduction>
Hello, I'm FinAI — your expense tracking assistant. I can help you analyze your spending patterns, track expenses by category, and provide budgeting insights. How can I assist you with your expenses today?
</Example_Introduction>

<Current_Expenses>
The user's expense data is provided below in JSON format. Use this data to answer questions about spending patterns, budgeting, and expense analysis:

```json
{expenses_json}
```

The expense data is organized in two ways:
1. "all_expenses": A flat list of all expenses
2. "by_family_member": Expenses grouped by family member name

Each expense contains:
- description: What the expense was for
- amount: The expense amount
- currency: The currency (EUR or INR)
- category: Expense category (Food, Transport, Shopping, Bills, Entertainment, Healthcare, Education, Travel, Other, or null)
- expense_date: Date when the expense was made (YYYY-MM-DD format)
- notes: Additional notes about the expense
- family_member: Information about who the expense belongs to:
  - If "family_member.name" is "Self", the expense belongs to the user themselves
  - Otherwise, it shows the family member's name and relationship (e.g., "John (Father)", "Sarah (Daughter)")

IMPORTANT - Family Member Information:
- Expenses can belong to different family members or to the user themselves (Self)
- Use the "by_family_member" data to provide family member-specific expense analysis when requested
- When calculating totals or analyzing spending patterns, you can provide both overall family expenses and individual family member expenses

When analyzing expenses:
1. Calculate total expenses by currency, category, month, year, or family member as requested
2. When asked about specific family members, use the "by_family_member" data to provide family member-specific insights
3. Identify spending patterns and trends over time for the entire family or individual members
4. Provide insights on budgeting and expense management
5. Compare spending across different categories or family members
6. Help identify areas where spending can be optimized
7. Note that expenses are in different currencies (EUR and INR) - analyze them separately or convert if needed
8. Group expenses by month/year when providing monthly or yearly summaries
9. When asked about specific time periods, filter expenses by the expense_date field
10. Provide clear breakdowns with totals, averages, and percentages when relevant
11. Suggest practical budgeting tips based on the user's spending patterns
12. When calculating expense totals or budgets, you can provide both overall family expenses and individual family member expenses
</Current_Expenses>"""
        
        else:
            # Default/fallback prompt
            system_prompt = "You are FinAI, a helpful financial assistant. How can I help you today?"
        
        # Check if this is an asset management command (only for assets context)
        if context == "assets":
            try:
                # Prepare conversation history for asset command processing
                asset_conversation_history = None
                if request.conversation_history:
                    asset_conversation_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in request.conversation_history
                    ]
                else:
                    # If conversation history not provided, fetch from database
                    try:
                        chat_history_response = supabase_service.table("chat_messages").select("*").eq("user_id", user_id).eq("context", context).order("message_order", desc=False).limit(10).execute()
                        if chat_history_response.data:
                            asset_conversation_history = [
                                {"role": msg.get("role"), "content": msg.get("content", "")}
                                for msg in chat_history_response.data
                            ]
                    except Exception as history_error:
                        print(f"Error fetching chat history: {history_error}")
                        asset_conversation_history = []
                
                # Add family members to portfolio_data for LLM context
                if portfolio_data and "family_members" not in portfolio_data:
                    try:
                        family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                        family_members_list = family_members_response.data if family_members_response.data else []
                        # Add family members info to portfolio_data
                        portfolio_data["family_members"] = [
                            {"id": str(fm.get("id")), "name": fm.get("name"), "relationship": fm.get("relationship")}
                            for fm in family_members_list
                        ]
                    except Exception as e:
                        portfolio_data["family_members"] = []
                
                asset_command_result = await asset_llm_service.process_asset_command(
                    user_message=request.message,
                    user_id=user_id,
                    portfolio_data=portfolio_data,
                    conversation_history=asset_conversation_history
                )
                
                
                # Check if this is a request asking for missing information
                # If so, return the response and don't continue to normal chat
                if asset_command_result.get("action") == "none":
                    response_msg = asset_command_result.get("response", "")
                    # Check if the response is asking for missing information
                    if response_msg and any(keyword in response_msg.lower() for keyword in ["need", "missing", "provide", "specify", "information"]):
                        # This is asking for missing info - return it and stop
                        try:
                            # Get current message order
                            current_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).eq("context", context).order("message_order", desc=True).limit(1).execute()
                            current_order = 1
                            if current_order_response.data and len(current_order_response.data) > 0:
                                current_order = (current_order_response.data[0].get("message_order", 0) or 0) + 1
                            
                            assistant_message_data = {
                                "user_id": user_id,
                                "role": "assistant",
                                "content": response_msg,
                                "message_order": current_order,
                                "context": context
                            }
                            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
                            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
                        except Exception as e:
                            print(f"Error saving assistant message: {e}")
                            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
                        
                        return ChatResponse(
                            response=response_msg,
                            message_id=message_id
                        )
                    else:
                        # Not asking for missing info, continue to normal chat
                        pass
                
                if asset_command_result.get("action") != "none":
                    # This is an asset management command - execute it
                    action = asset_command_result.get("action")
                    asset_data = asset_command_result.get("asset_data", {})
                    asset_id = asset_command_result.get("asset_id")
                    
                    
                    try:
                        if action == "add":
                            # Create new asset
                            from routers.assets import create_asset
                            
                            # Build AssetCreate object
                            # Get currency from market (market should already be converted to currency in asset_llm_service)
                            currency = asset_data.get("currency")
                            asset_type = asset_data.get("asset_type")
                            
                            # Validate required fields are present - don't assume anything
                            missing_fields = []
                            
                            if not currency:
                                # Check if market was provided instead
                                market = asset_data.get("market")
                                if market:
                                    market_lower = market.lower()
                                    if market_lower == 'india':
                                        currency = 'INR'
                                    elif market_lower == 'europe':
                                        currency = 'EUR'
                                    else:
                                        missing_fields.append("market (must be 'India' or 'Europe')")
                                else:
                                    missing_fields.append("market (India or Europe)")
                            
                            if asset_type == "stock":
                                if not asset_data.get("asset_name"):
                                    missing_fields.append("asset name")
                                if not asset_data.get("stock_symbol"):
                                    missing_fields.append("stock symbol")
                                if not asset_data.get("quantity"):
                                    missing_fields.append("quantity (number of shares)")
                                if not asset_data.get("purchase_price"):
                                    missing_fields.append("purchase price")
                                if not asset_data.get("purchase_date"):
                                    missing_fields.append("purchase date")
                                if not asset_data.get("family_member_name"):
                                    missing_fields.append("stock owner (family member name or 'self')")
                            elif asset_type == "bank_account":
                                if not asset_data.get("asset_name"):
                                    missing_fields.append("account name")
                                if not asset_data.get("bank_name"):
                                    missing_fields.append("bank name")
                                if not asset_data.get("account_number"):
                                    missing_fields.append("account number")
                                if not asset_data.get("account_type"):
                                    missing_fields.append("account type (savings, checking, or current)")
                                if not asset_data.get("current_value"):
                                    missing_fields.append("current balance (bank balance)")
                                if not asset_data.get("family_member_name"):
                                    missing_fields.append("account owner (family member name or 'self')")
                            
                            if missing_fields:
                                error_msg = f"I need more information to add this {asset_type} asset. Please provide: {', '.join(missing_fields)}."
                                llm_response = f"❌ {error_msg}"
                                
                                # Save error response to database
                                try:
                                    assistant_message_data = {
                                        "user_id": user_id,
                                        "role": "assistant",
                                        "content": llm_response,
                                        "message_order": current_order,
                                        "context": context
                                    }
                                    insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
                                    message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
                                except:
                                    message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
                                
                                return ChatResponse(
                                    response=llm_response,
                                    message_id=message_id
                                )
                            
                            # Handle family member matching for stocks and bank accounts
                            family_member_id = None
                            family_member_name_provided = asset_data.get("family_member_name", "").strip().lower()
                            family_member_not_found_message = ""
                            
                            if asset_type in ["stock", "bank_account"]:
                                if family_member_name_provided:
                                    # Normalize: "self", "me", "myself" -> None (user themselves)
                                    if family_member_name_provided in ["self", "me", "myself", ""]:
                                        family_member_id = None
                                    else:
                                        # Fetch family members and match by name
                                        try:
                                            family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                                            family_members_list = family_members_response.data if family_members_response.data else []
                                            
                                            # Try to find matching family member (prioritize exact match, then partial match)
                                            matched_member = None
                                            # First, try exact match (case-insensitive)
                                            for member in family_members_list:
                                                member_name = member.get("name", "").lower()
                                                if member_name == family_member_name_provided:
                                                    matched_member = member
                                                    break
                                            
                                            # If no exact match, try partial match (but be more strict)
                                            if not matched_member:
                                                for member in family_members_list:
                                                    member_name = member.get("name", "").lower()
                                                    # Only match if the provided name is a complete word/phrase in the member name
                                                    # e.g., "krishnan" should match "krishnan" but not "bharadwaj krishnan" unless it's the last name
                                                    # Check if provided name matches the last word of the member name
                                                    member_name_parts = member_name.split()
                                                    if len(member_name_parts) > 1 and family_member_name_provided == member_name_parts[-1]:
                                                        # Last name match (e.g., "krishnan" matches "bharadwaj krishnan")
                                                        matched_member = member
                                                        break
                                                    elif family_member_name_provided in member_name and len(family_member_name_provided) >= 4:
                                                        # Partial match only if the provided name is at least 4 characters (to avoid false matches)
                                                        matched_member = member
                                                        break
                                            
                                            if matched_member:
                                                family_member_id = matched_member.get("id")
                                            else:
                                                # Family member not found - default to self but note it
                                                family_member_id = None
                                                asset_type_name = "stock" if asset_type == "stock" else "bank account"
                                                family_member_not_found_message = f" Note: The family member '{asset_data.get('family_member_name')}' is not yet added in your Profile. The {asset_type_name} has been assigned to you (Self). Please add this family member in the Profile section if you want to assign assets to them in the future."
                                        except Exception as e:
                                            family_member_id = None
                                else:
                                    # No family member name provided - default to self
                                    family_member_id = None
                            
                            # For bank accounts, if asset_name is not provided, use bank_name as asset_name
                            asset_name = asset_data.get("asset_name")
                            if asset_type == "bank_account" and not asset_name and asset_data.get("bank_name"):
                                asset_name = asset_data.get("bank_name")
                            
                            asset_create_data = {
                                "name": asset_name or "New Asset",
                                "type": asset_type,
                                "currency": currency,
                                "current_value": asset_data.get("current_value", 0),
                                "notes": asset_data.get("notes"),
                                "family_member_id": family_member_id,
                            }
                            
                            # asset_type already set above
                            if asset_type == "stock":
                                asset_create_data.update({
                                    "stock_symbol": asset_data.get("stock_symbol"),
                                    "stock_exchange": asset_data.get("stock_exchange"),
                                    "quantity": asset_data.get("quantity"),
                                    "purchase_price": asset_data.get("purchase_price"),
                                    "purchase_date": asset_data.get("purchase_date"),
                                    "current_price": asset_data.get("current_price"),
                                })
                                # Calculate current_value if not provided
                                if not asset_create_data.get("current_value") and asset_data.get("quantity") and asset_data.get("purchase_price"):
                                    asset_create_data["current_value"] = float(asset_data.get("quantity", 0)) * float(asset_data.get("purchase_price", 0))
                            elif asset_type == "mutual_fund":
                                asset_create_data.update({
                                    "mutual_fund_code": asset_data.get("mutual_fund_code"),
                                    "fund_house": asset_data.get("fund_house"),
                                    "nav": asset_data.get("nav"),
                                    "units": asset_data.get("units"),
                                    "nav_purchase_date": asset_data.get("nav_purchase_date"),
                                })
                                # Calculate current_value if not provided
                                if not asset_create_data.get("current_value") and asset_data.get("units") and asset_data.get("nav"):
                                    asset_create_data["current_value"] = float(asset_data.get("units", 0)) * float(asset_data.get("nav", 0))
                            elif asset_type == "bank_account":
                                asset_create_data.update({
                                    "bank_name": asset_data.get("bank_name"),
                                    "account_type": asset_data.get("account_type"),
                                    "account_number": asset_data.get("account_number"),
                                    "interest_rate": asset_data.get("interest_rate"),
                                })
                                if asset_data.get("current_value"):
                                    asset_create_data["current_value"] = asset_data.get("current_value")
                            elif asset_type == "fixed_deposit":
                                asset_create_data.update({
                                    "fd_number": asset_data.get("fd_number"),
                                    "principal_amount": asset_data.get("principal_amount"),
                                    "fd_interest_rate": asset_data.get("fd_interest_rate"),
                                    "start_date": asset_data.get("start_date"),
                                    "maturity_date": asset_data.get("maturity_date"),
                                })
                                if asset_data.get("principal_amount"):
                                    asset_create_data["current_value"] = asset_data.get("principal_amount")
                            elif asset_type == "insurance_policy":
                                asset_create_data.update({
                                    "policy_number": asset_data.get("policy_number"),
                                    "amount_insured": asset_data.get("amount_insured"),
                                    "issue_date": asset_data.get("issue_date"),
                                    "date_of_maturity": asset_data.get("date_of_maturity"),
                                    "premium": asset_data.get("premium"),
                                    "nominee": asset_data.get("nominee"),
                                    "premium_payment_date": asset_data.get("premium_payment_date"),
                                })
                                if asset_data.get("amount_insured"):
                                    asset_create_data["current_value"] = asset_data.get("amount_insured")
                            elif asset_type == "commodity":
                                asset_create_data.update({
                                    "commodity_name": asset_data.get("commodity_name"),
                                    "form": asset_data.get("form"),
                                    "commodity_quantity": asset_data.get("quantity") or asset_data.get("commodity_quantity"),
                                    "commodity_units": asset_data.get("commodity_units"),
                                    "commodity_purchase_date": asset_data.get("commodity_purchase_date") or asset_data.get("purchase_date"),
                                    "commodity_purchase_price": asset_data.get("commodity_purchase_price") or asset_data.get("purchase_price"),
                                })
                                # Calculate current_value if not provided
                                if not asset_create_data.get("current_value") and asset_data.get("quantity") and asset_data.get("commodity_purchase_price"):
                                    asset_create_data["current_value"] = float(asset_data.get("quantity", 0)) * float(asset_data.get("commodity_purchase_price", 0))
                            
                            # Create asset using the assets router logic
                            
                            # Ensure is_active is set
                            if "is_active" not in asset_create_data:
                                asset_create_data["is_active"] = True
                            
                            # Remove None values to avoid issues, but keep empty strings and 0 values
                            # Only remove actual None values, not empty strings or zeros which might be valid
                            asset_create_data = {k: v for k, v in asset_create_data.items() if v is not None or k == "notes"}
                            
                            try:
                                asset_create = AssetCreate(**asset_create_data)
                            except Exception as validation_error:
                                print(f"Error creating AssetCreate object: {str(validation_error)}")
                                import traceback
                                raise ValueError(f"Invalid asset data: {str(validation_error)}")
                            
                            try:
                                asset_create.model_validate_asset_fields()  # Validate required fields
                            except Exception as validation_error:
                                print(f"Error validating asset fields: {str(validation_error)}")
                                import traceback
                                raise ValueError(f"Asset validation failed: {str(validation_error)}")
                            
                            # Use supabase_service to create asset directly
                            try:
                                asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
                            except AttributeError:
                                # Fallback for older Pydantic versions
                                asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
                            
                            asset_dict["user_id"] = user_id
                            
                            # Ensure is_active is set
                            if "is_active" not in asset_dict:
                                asset_dict["is_active"] = True
                            
                            
                            # Convert dates and decimals
                            date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date', 
                                         'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
                            for field in date_fields:
                                if field in asset_dict and asset_dict[field]:
                                    if isinstance(asset_dict[field], str):
                                        pass  # Already string
                                    else:
                                        asset_dict[field] = asset_dict[field].isoformat() if hasattr(asset_dict[field], 'isoformat') else asset_dict[field]
                            
                            decimal_fields = ['current_value', 'quantity', 'purchase_price', 'current_price',
                                             'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
                                             'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price']
                            for field in decimal_fields:
                                if field in asset_dict and asset_dict[field] is not None:
                                    asset_dict[field] = str(asset_dict[field])
                            
                            
                            # Insert into database
                            try:
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                
                                # Check response structure
                                response_data = None
                                if hasattr(response, 'data'):
                                    response_data = response.data
                                elif hasattr(response, '__dict__'):
                                    # Fallback: try to get data from __dict__
                                    response_data = response.__dict__.get('data')
                                
                                # Also check for errors
                                response_error = None
                                if hasattr(response, 'error'):
                                    response_error = response.error
                                
                                if response_error:
                                    error_msg = f"Supabase error: {response_error}"
                                    print(f"ERROR: {error_msg}")
                                    llm_response = f"❌ Failed to create asset: {error_msg}. Please check the provided information and try again."
                                elif response_data and isinstance(response_data, list) and len(response_data) > 0:
                                    created_asset = response_data[0]
                                    asset_id = created_asset.get('id')
                                    
                                    # Verify the asset was actually created by querying it back
                                    verify_response = supabase_service.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
                                    if verify_response.data and len(verify_response.data) > 0:
                                        # Build success message without asset ID
                                        asset_name = asset_create_data.get('name', 'asset')
                                        owner_info = ""
                                        if family_member_id:
                                            # Get family member name
                                            try:
                                                fm_response = supabase_service.table("family_members").select("name").eq("id", family_member_id).execute()
                                                if fm_response.data:
                                                    owner_info = f" for {fm_response.data[0].get('name')}"
                                            except:
                                                pass
                                        else:
                                            owner_info = " for you (Self)"
                                        
                                        if asset_type == "stock":
                                            llm_response = f"✅ Successfully added {asset_name} stock{owner_info} to your portfolio.{family_member_not_found_message}"
                                        elif asset_type == "bank_account":
                                            llm_response = f"✅ Successfully added {asset_name} bank account{owner_info} to your portfolio.{family_member_not_found_message}"
                                        else:
                                            llm_response = f"✅ Successfully added {asset_type} asset: {asset_name} to your portfolio.{family_member_not_found_message}"
                                    else:
                                        error_msg = "Asset was inserted but could not be verified"
                                        print(f"ERROR: {error_msg}")
                                        llm_response = f"❌ {error_msg}. Please check the database."
                                elif response_data is None or (isinstance(response_data, list) and len(response_data) == 0):
                                    error_msg = "No data returned from Supabase insert - asset may not have been created"
                                    print(f"ERROR: {error_msg}")
                                    llm_response = f"❌ Failed to create asset: {error_msg}. Please check the provided information and try again."
                                else:
                                    error_msg = f"Unexpected response format: {type(response_data)}"
                                    print(f"ERROR: {error_msg}")
                                    llm_response = f"❌ Failed to create asset: {error_msg}. Please check the logs for details."
                                    
                            except Exception as insert_error:
                                error_msg = str(insert_error)
                                print(f"ERROR inserting asset into database: {error_msg}")
                                import traceback
                                
                                # Check for RLS errors
                                if "row-level security" in error_msg.lower() or "42501" in error_msg:
                                    llm_response = "❌ Failed to create asset: Database permission error. Please check your Supabase configuration."
                                elif "foreign key" in error_msg.lower() or "constraint" in error_msg.lower():
                                    llm_response = f"❌ Failed to create asset: Data validation error. {error_msg}"
                                else:
                                    llm_response = f"❌ Failed to create asset: {error_msg}. Please check the provided information and try again."
                                error_msg = str(insert_error)
                                print(f"ERROR inserting asset into database: {error_msg}")
                                import traceback
                                
                                # Check for RLS errors
                                if "row-level security" in error_msg.lower() or "42501" in error_msg:
                                    llm_response = "❌ Failed to create asset: Database permission error. Please check your Supabase configuration."
                                elif "foreign key" in error_msg.lower() or "constraint" in error_msg.lower():
                                    llm_response = f"❌ Failed to create asset: Data validation error. {error_msg}"
                                else:
                                    llm_response = f"❌ Failed to create asset: {error_msg}. Please check the provided information and try again."
                        
                        elif action == "delete":
                            # Delete asset
                            if not asset_id:
                                llm_response = "❌ Could not find the asset to delete. Please specify the asset name or ID more clearly."
                            else:
                                # Verify asset belongs to user
                                asset_response = supabase_service.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
                                if not asset_response.data:
                                    llm_response = f"❌ Asset with ID {asset_id} not found or you don't have permission to delete it."
                                else:
                                    asset_name = asset_response.data[0].get("name", "Unknown")
                                    delete_response = supabase_service.table("assets").delete().eq("id", asset_id).eq("user_id", user_id).execute()
                                    if delete_response.data:
                                        llm_response = f"✅ Successfully deleted asset: {asset_name}"
                                    else:
                                        llm_response = f"❌ Failed to delete asset: {asset_name}"
                        
                        elif action == "update":
                            # Check if user wants to update all stocks/assets
                            # Check both current message and conversation history
                            user_message_lower = request.message.lower()
                            conversation_text = user_message_lower
                            if request.conversation_history:
                                for msg in request.conversation_history:
                                    if msg.get("role") == "user":
                                        conversation_text += " " + msg.get("content", "").lower()
                            
                            # More flexible detection - check for patterns that indicate "all stocks"
                            update_all_stocks = any(phrase in conversation_text for phrase in [
                                "all stocks", "all the stocks", "every stock", "all my stocks", 
                                "update all stocks", "update all the stocks", "change all stocks",
                                "change all the stocks", "update all stock", "for all stocks",
                                "for all the stocks", "the stocks", "all stock"
                            ])
                            update_all_assets = any(phrase in conversation_text for phrase in [
                                "all assets", "all the assets", "every asset", "all my assets", 
                                "update all assets", "update all the assets", "change all assets",
                                "change all the assets", "for all assets", "for all the assets",
                                "do for all assets", "do for all the assets", "the assets"
                            ])
                            
                            # Extract purchase_date from user message if not in asset_data
                            import re
                            from datetime import datetime
                            if not asset_data.get("purchase_date"):
                                # Try to extract date from user message (format: DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY)
                                date_patterns = [
                                    r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 01/01/2024
                                    r'(\d{1,2})-(\d{1,2})-(\d{4})',  # 01-01-2024
                                    r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # 01.01.2024
                                ]
                                for pattern in date_patterns:
                                    date_match = re.search(pattern, conversation_text)
                                    if date_match:
                                        day, month, year = date_match.groups()
                                        try:
                                            # Format as YYYY-MM-DD
                                            asset_data["purchase_date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                                            break
                                        except:
                                            pass
                            
                            print(f"DEBUG UPDATE: update_all_stocks={update_all_stocks}, update_all_assets={update_all_assets}")
                            print(f"DEBUG UPDATE: asset_data keys={list(asset_data.keys())}")
                            print(f"DEBUG UPDATE: purchase_date in asset_data={asset_data.get('purchase_date')}")
                            print(f"DEBUG UPDATE: conversation_text={conversation_text[:200]}")
                            
                            assets_to_update = []
                            if update_all_stocks or update_all_assets:
                                # Fetch all relevant assets
                                query = supabase_service.table("assets").select("*").eq("user_id", user_id).eq("is_active", True)
                                if update_all_stocks:
                                    query = query.eq("type", "stock")
                                assets_response = query.execute()
                                assets_to_update = assets_response.data if assets_response.data else []
                                
                                if not assets_to_update:
                                    llm_response = f"❌ No {'stocks' if update_all_stocks else 'assets'} found to update."
                                else:
                                    # Update each asset
                                    updated_count = 0
                                    failed_count = 0
                                    asset_type = "stock" if update_all_stocks else None
                                    
                                    for asset in assets_to_update:
                                        if not asset_type:
                                            asset_type = asset.get("type")
                                        
                                        try:
                                            # Build update data (same logic as single update)
                                            update_data = {}
                                            if asset_data.get("asset_name"):
                                                update_data["name"] = asset_data.get("asset_name")
                                            if asset_data.get("current_value") is not None:
                                                update_data["current_value"] = str(asset_data.get("current_value"))
                                            if asset_data.get("currency"):
                                                update_data["currency"] = asset_data.get("currency")
                                            if asset_data.get("notes") is not None:
                                                update_data["notes"] = asset_data.get("notes")
                                            
                                            # Handle family member matching if provided
                                            family_member_id = None
                                            if asset_data.get("family_member_name") and asset_type in ["stock", "bank_account"]:
                                                family_member_name_provided = asset_data.get("family_member_name", "").strip().lower()
                                                if family_member_name_provided in ["self", "me", "myself", ""]:
                                                    family_member_id = None
                                                else:
                                                    try:
                                                        family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                                                        family_members_list = family_members_response.data if family_members_response.data else []
                                                        matched_member = None
                                                        for member in family_members_list:
                                                            member_name = member.get("name", "").lower()
                                                            if member_name == family_member_name_provided:
                                                                matched_member = member
                                                                break
                                                        if matched_member:
                                                            family_member_id = matched_member.get("id")
                                                    except:
                                                        family_member_id = None
                                                if family_member_id is not None:
                                                    update_data["family_member_id"] = family_member_id
                                            
                                            # Add type-specific update fields
                                            if asset_type == "stock":
                                                if asset_data.get("quantity") is not None:
                                                    update_data["quantity"] = str(asset_data.get("quantity"))
                                                if asset_data.get("purchase_price") is not None:
                                                    update_data["purchase_price"] = str(asset_data.get("purchase_price"))
                                                if asset_data.get("current_price") is not None:
                                                    update_data["current_price"] = str(asset_data.get("current_price"))
                                                if asset_data.get("purchase_date"):
                                                    update_data["purchase_date"] = asset_data.get("purchase_date")
                                            
                                            # Convert dates
                                            date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date',
                                                         'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
                                            for field in date_fields:
                                                if field in update_data and update_data[field]:
                                                    if isinstance(update_data[field], str):
                                                        pass
                                                    else:
                                                        update_data[field] = update_data[field].isoformat() if hasattr(update_data[field], 'isoformat') else update_data[field]
                                            
                                            # Convert decimals
                                            decimal_fields = ['current_value', 'quantity', 'purchase_price', 'current_price',
                                                             'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
                                                             'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price']
                                            for field in decimal_fields:
                                                if field in update_data and update_data[field] is not None:
                                                    update_data[field] = str(update_data[field])
                                            
                                            # Perform update
                                            if update_data:
                                                update_response = supabase_service.table("assets").update(update_data).eq("id", asset["id"]).eq("user_id", user_id).execute()
                                                if update_response.data:
                                                    updated_count += 1
                                                else:
                                                    failed_count += 1
                                            else:
                                                failed_count += 1
                                        except Exception as e:
                                            print(f"Error updating asset {asset.get('id')}: {e}")
                                            failed_count += 1
                                    
                                    if updated_count > 0:
                                        llm_response = f"✅ Successfully updated {updated_count} {'stock' if update_all_stocks else 'asset'}{'s' if updated_count > 1 else ''}."
                                        if failed_count > 0:
                                            llm_response += f" {failed_count} failed to update."
                                    else:
                                        llm_response = f"❌ Failed to update any {'stocks' if update_all_stocks else 'assets'}."
                            
                            elif not asset_id:
                                llm_response = "❌ Could not find the asset to update. Please specify the asset name or ID more clearly."
                            else:
                                # Single asset update (existing logic)
                                # Verify asset belongs to user
                                asset_response = supabase_service.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
                                if not asset_response.data:
                                    llm_response = f"❌ Asset with ID {asset_id} not found or you don't have permission to update it."
                                else:
                                    # Get asset type first
                                    asset_type = asset_response.data[0].get("type")
                                    
                                    # Handle family member matching for updates (stocks and bank accounts)
                                    family_member_id = None
                                    if asset_data.get("family_member_name") and asset_type in ["stock", "bank_account"]:
                                        family_member_name_provided = asset_data.get("family_member_name", "").strip().lower()
                                        
                                        # Normalize: "self", "me", "myself" -> None (user themselves)
                                        if family_member_name_provided in ["self", "me", "myself", ""]:
                                            family_member_id = None
                                        else:
                                            # Fetch family members and match by name
                                            try:
                                                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                                                family_members_list = family_members_response.data if family_members_response.data else []
                                                
                                                # Try to find matching family member (prioritize exact match, then partial match)
                                                matched_member = None
                                                # First, try exact match (case-insensitive)
                                                for member in family_members_list:
                                                    member_name = member.get("name", "").lower()
                                                    if member_name == family_member_name_provided:
                                                        matched_member = member
                                                        break
                                                
                                                # If no exact match, try partial match (but be more strict)
                                                if not matched_member:
                                                    for member in family_members_list:
                                                        member_name = member.get("name", "").lower()
                                                        # Only match if the provided name is a complete word/phrase in the member name
                                                        # Check if provided name matches the last word of the member name
                                                        member_name_parts = member_name.split()
                                                        if len(member_name_parts) > 1 and family_member_name_provided == member_name_parts[-1]:
                                                            # Last name match (e.g., "krishnan" matches "bharadwaj krishnan")
                                                            matched_member = member
                                                            break
                                                        elif family_member_name_provided in member_name and len(family_member_name_provided) >= 4:
                                                            # Partial match only if the provided name is at least 4 characters (to avoid false matches)
                                                            matched_member = member
                                                            break
                                                
                                                if matched_member:
                                                    family_member_id = matched_member.get("id")
                                                else:
                                                    # Family member not found - default to self but note it
                                                    family_member_id = None
                                            except Exception as e:
                                                family_member_id = None
                                    
                                    # Build update data
                                    update_data = {}
                                    if asset_data.get("asset_name"):
                                        update_data["name"] = asset_data.get("asset_name")
                                    if asset_data.get("current_value") is not None:
                                        update_data["current_value"] = str(asset_data.get("current_value"))
                                    if asset_data.get("currency"):
                                        update_data["currency"] = asset_data.get("currency")
                                    if asset_data.get("notes") is not None:
                                        update_data["notes"] = asset_data.get("notes")
                                    
                                    # Add family_member_id if it was provided/calculated (for stocks and bank accounts)
                                    if asset_data.get("family_member_name") and asset_type in ["stock", "bank_account"]:
                                        update_data["family_member_id"] = family_member_id
                                    
                                    # Add type-specific update fields
                                    if asset_type == "stock":
                                        if asset_data.get("quantity") is not None:
                                            update_data["quantity"] = str(asset_data.get("quantity"))
                                        if asset_data.get("purchase_price") is not None:
                                            update_data["purchase_price"] = str(asset_data.get("purchase_price"))
                                        if asset_data.get("current_price") is not None:
                                            update_data["current_price"] = str(asset_data.get("current_price"))
                                        if asset_data.get("purchase_date"):
                                            update_data["purchase_date"] = asset_data.get("purchase_date")
                                    elif asset_type == "mutual_fund":
                                        if asset_data.get("units") is not None:
                                            update_data["units"] = str(asset_data.get("units"))
                                        if asset_data.get("nav") is not None:
                                            update_data["nav"] = str(asset_data.get("nav"))
                                    elif asset_type == "bank_account":
                                        if asset_data.get("bank_name"):
                                            update_data["bank_name"] = asset_data.get("bank_name")
                                        if asset_data.get("account_type"):
                                            update_data["account_type"] = asset_data.get("account_type")
                                        if asset_data.get("current_value") is not None:
                                            update_data["current_value"] = str(asset_data.get("current_value"))
                                    
                                    # Convert dates and decimals
                                    date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date',
                                                 'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
                                    for field in date_fields:
                                        if field in update_data and update_data[field]:
                                            if isinstance(update_data[field], str):
                                                pass
                                            else:
                                                update_data[field] = update_data[field].isoformat() if hasattr(update_data[field], 'isoformat') else update_data[field]
                                    
                                    decimal_fields = ['current_value', 'quantity', 'purchase_price', 'current_price',
                                                     'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
                                                     'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price']
                                    for field in decimal_fields:
                                        if field in update_data and update_data[field] is not None:
                                            update_data[field] = str(update_data[field])
                                    
                                    update_response = supabase_service.table("assets").update(update_data).eq("id", asset_id).eq("user_id", user_id).execute()
                                    if update_response.data:
                                        asset_name = update_response.data[0].get("name", "Unknown")
                                        llm_response = f"✅ Successfully updated asset: {asset_name}"
                                    else:
                                        llm_response = "❌ Failed to update asset. Please check the provided information."
                        
                        # Save assistant response to database
                        try:
                            assistant_message_data = {
                                "user_id": user_id,
                                "role": "assistant",
                                "content": llm_response,
                                "message_order": current_order,
                                "context": context
                            }
                            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
                            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
                        except Exception as e:
                            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
                        
                        return ChatResponse(
                            response=llm_response,
                            message_id=message_id
                        )
                    
                    except Exception as exec_error:
                        import traceback
                        error_details = traceback.format_exc()
                        print(f"Error executing asset command: {str(exec_error)}")
                        error_response = f"❌ Error executing asset operation: {str(exec_error)}. Please check the information and try again."
                        
                        # Save error response
                        try:
                            assistant_message_data = {
                                "user_id": user_id,
                                "role": "assistant",
                                "content": error_response,
                                "message_order": current_order,
                                "context": context
                            }
                            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
                            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
                        except:
                            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
                        
                        return ChatResponse(
                            response=error_response,
                            message_id=message_id
                        )
                else:
                    # If action is "none", continue with normal LLM chat flow
                    pass
                
            except Exception as asset_llm_error:
                # If asset LLM service fails, continue with normal chat flow
                import traceback
        
        # Get LLM response
        # Log prompt size for debugging
        system_prompt_length = len(system_prompt) if system_prompt else 0
        history_length = len(history) if history else 0
        message_length = len(request.message) if request.message else 0
        total_prompt_size = system_prompt_length + message_length + (history_length * 200)  # Rough estimate
        
        # Retry logic for rate limit errors
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        llm_response = None
        
        for attempt in range(max_retries):
            try:
                llm_response = await llm_service.chat(
                    message=request.message,
                    conversation_history=history,
                    system_prompt=system_prompt
                )
                
                # Check if the response is an error message (LLM service returns error strings)
                if llm_response and isinstance(llm_response, str):
                    error_lower = llm_response.lower()
                    is_rate_limit = "rate-limited" in error_lower or "rate limit" in error_lower
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    elif is_rate_limit and attempt == max_retries - 1:
                        # Max retries reached, return the error message
                        break
                
                # Success or non-rate-limit error, exit retry loop
                break
                
            except Exception as llm_error:
                import traceback
                error_trace = traceback.format_exc()
                error_msg = str(llm_error)
                error_lower = error_msg.lower()
                
                # Check if it's a rate limit error
                is_rate_limit = "quota" in error_lower or "rate limit" in error_lower or "429" in error_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Not a rate limit error, or max retries reached
                    # Re-raise to let the LLM service handle it
                    raise
        
        if llm_response is None:
            raise HTTPException(status_code=500, detail="Failed to get LLM response after retries")
        
        # Save assistant response to database
        try:
            assistant_message_data = {
                "user_id": user_id,
                "role": "assistant",
                "content": llm_response,
                "message_order": current_order,
                "context": context  # Store context with message
            }
            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
        except Exception as e:
            import traceback
            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
        
        return ChatResponse(
            response=llm_response,
            message_id=message_id
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    context: Optional[str] = Query("assets", description="Context filter: 'assets' or 'expenses'"),
    current_user=Depends(get_current_user)
):
    """
    Fetch chat history for the current user, filtered by context
    """
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Normalize context
        if not context or context == "":
            context = "assets"
        else:
            context = str(context).lower().strip()
        
        
        # Fetch chat messages from database, filtered by context and ordered by message_order
        try:
            response = supabase_service.table("chat_messages").select("*").eq("user_id", user_id).eq("context", context).order("message_order", desc=False).execute()
            messages = response.data if response.data else []
            
            # Format messages for frontend
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "id": msg.get("id"),
                    "role": msg.get("role"),
                    "content": msg.get("content"),
                    "timestamp": msg.get("created_at")
                })
            
            return ChatHistoryResponse(messages=formatted_messages)
        except Exception as e:
            import traceback
            raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")


@router.delete("/history", status_code=204)
async def clear_chat_history(
    context: Optional[str] = Query("assets", description="Context filter: 'assets' or 'expenses'"),
    current_user=Depends(get_current_user)
):
    """
    Clear chat messages for the current user, filtered by context
    """
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Normalize context
        if not context or context == "":
            context = "assets"
        else:
            context = str(context).lower().strip()
        
        
        # Delete chat messages for this user and context
        try:
            delete_response = supabase_service.table("chat_messages").delete().eq("user_id", user_id).eq("context", context).execute()
        except Exception as e:
            import traceback
            raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")


async def create_asset_from_llm_data(
    asset_data: Dict[str, Any],
    user_id: str,
    context: str = "assets"
) -> str:
    """
    Helper function to create an asset from LLM-extracted data.
    Returns the response message.
    This function is reused by both the chat endpoint and the upload endpoint.
    """
    try:
        # Get currency from market (market should already be converted to currency in asset_llm_service)
        currency = asset_data.get("currency")
        asset_type = asset_data.get("asset_type")
        
        # Validate required fields are present
        missing_fields = []
        
        if not currency:
            # Check if market was provided instead
            market = asset_data.get("market")
            if market:
                market_lower = market.lower()
                if market_lower == 'india':
                    currency = 'INR'
                elif market_lower == 'europe':
                    currency = 'EUR'
                else:
                    missing_fields.append("market (must be 'India' or 'Europe')")
            else:
                missing_fields.append("market (India or Europe)")
        
        if asset_type == "stock":
            if not asset_data.get("asset_name"):
                missing_fields.append("asset name")
            if not asset_data.get("stock_symbol"):
                missing_fields.append("stock symbol")
            if not asset_data.get("quantity"):
                missing_fields.append("quantity (number of shares)")
            if not asset_data.get("purchase_price"):
                missing_fields.append("purchase price")
            if not asset_data.get("purchase_date"):
                missing_fields.append("purchase date")
            if not asset_data.get("family_member_name"):
                missing_fields.append("stock owner (family member name or 'self')")
        elif asset_type == "bank_account":
            if not asset_data.get("bank_name"):
                missing_fields.append("bank name")
            if not asset_data.get("account_number"):
                missing_fields.append("account number")
            if not asset_data.get("account_type"):
                missing_fields.append("account type (savings, checking, or current)")
            if not asset_data.get("current_value"):
                missing_fields.append("current balance (bank balance)")
            if not asset_data.get("family_member_name"):
                missing_fields.append("account owner (family member name or 'self')")
        
        if missing_fields:
            error_msg = f"I need more information to add this {asset_type} asset. Please provide: {', '.join(missing_fields)}."
            return f"❌ {error_msg}"
        
        # Handle family member matching
        family_member_id = None
        family_member_name_provided = asset_data.get("family_member_name", "").strip().lower()
        family_member_not_found_message = ""
        
        if asset_type in ["stock", "bank_account"]:
            if family_member_name_provided:
                if family_member_name_provided in ["self", "me", "myself", ""]:
                    family_member_id = None
                else:
                    try:
                        family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                        family_members_list = family_members_response.data if family_members_response.data else []
                        
                        matched_member = None
                        # Exact match first
                        for member in family_members_list:
                            member_name = member.get("name", "").lower()
                            if member_name == family_member_name_provided:
                                matched_member = member
                                break
                        
                        # Partial match if no exact match
                        if not matched_member:
                            for member in family_members_list:
                                member_name = member.get("name", "").lower()
                                member_name_parts = member_name.split()
                                if len(member_name_parts) > 1 and family_member_name_provided == member_name_parts[-1]:
                                    matched_member = member
                                    break
                                elif family_member_name_provided in member_name and len(family_member_name_provided) >= 4:
                                    matched_member = member
                                    break
                        
                        if matched_member:
                            family_member_id = matched_member.get("id")
                        else:
                            family_member_id = None
                            asset_type_name = "stock" if asset_type == "stock" else "bank account"
                            family_member_not_found_message = f" Note: The family member '{asset_data.get('family_member_name')}' is not yet added in your Profile. The {asset_type_name} has been assigned to you (Self)."
                    except Exception as e:
                        family_member_id = None
            else:
                family_member_id = None
        
        # For bank accounts, if asset_name is not provided, use bank_name as asset_name
        asset_name = asset_data.get("asset_name")
        if asset_type == "bank_account" and not asset_name and asset_data.get("bank_name"):
            asset_name = asset_data.get("bank_name")
        
        asset_create_data = {
            "name": asset_name or "New Asset",
            "type": asset_type,
            "currency": currency,
            "current_value": asset_data.get("current_value", 0),
            "notes": asset_data.get("notes"),
            "family_member_id": family_member_id,
        }
        
        # Add type-specific fields
        if asset_type == "stock":
            asset_create_data.update({
                "stock_symbol": asset_data.get("stock_symbol"),
                "stock_exchange": asset_data.get("stock_exchange"),
                "quantity": asset_data.get("quantity"),
                "purchase_price": asset_data.get("purchase_price"),
                "purchase_date": asset_data.get("purchase_date"),
                "current_price": asset_data.get("current_price"),
            })
            if not asset_create_data.get("current_value") and asset_data.get("quantity") and asset_data.get("purchase_price"):
                asset_create_data["current_value"] = float(asset_data.get("quantity", 0)) * float(asset_data.get("purchase_price", 0))
        elif asset_type == "bank_account":
            # Normalize account_type - extract base type from variations like "SAVINGS - NRO", "NRO SB - EBROKING", etc.
            account_type_raw = asset_data.get("account_type", "").strip()
            account_type_normalized = None
            
            if account_type_raw:
                account_type_lower = account_type_raw.lower()
                # Check for savings variations
                if "savings" in account_type_lower or "sb" in account_type_lower:
                    account_type_normalized = "savings"
                # Check for checking variations
                elif "checking" in account_type_lower:
                    account_type_normalized = "checking"
                # Check for current variations
                elif "current" in account_type_lower:
                    account_type_normalized = "current"
                # If no match found, default to savings (most common in India)
                else:
                    print(f"WARNING: Could not normalize account_type '{account_type_raw}', defaulting to 'savings'")
                    account_type_normalized = "savings"
            
            asset_create_data.update({
                "bank_name": asset_data.get("bank_name"),
                "account_type": account_type_normalized,
                "account_number": asset_data.get("account_number"),
                "interest_rate": asset_data.get("interest_rate"),
            })
            if asset_data.get("current_value"):
                asset_create_data["current_value"] = asset_data.get("current_value")
        
        # Create AssetCreate object
        asset_create_data = {k: v for k, v in asset_create_data.items() if v is not None or k == "notes"}
        asset_create = AssetCreate(**asset_create_data)
        asset_create.model_validate_asset_fields()
        
        # Convert to dict for database insertion
        try:
            asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        except AttributeError:
            asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
        
        asset_dict["user_id"] = user_id
        asset_dict["is_active"] = True
        
        # Convert dates and decimals
        date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date', 
                     'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
        for field in date_fields:
            if field in asset_dict and asset_dict[field]:
                if not isinstance(asset_dict[field], str):
                    asset_dict[field] = asset_dict[field].isoformat() if hasattr(asset_dict[field], 'isoformat') else asset_dict[field]
        
        decimal_fields = ['current_value', 'quantity', 'purchase_price', 'current_price',
                         'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
                         'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price']
        for field in decimal_fields:
            if field in asset_dict and asset_dict[field] is not None:
                asset_dict[field] = str(asset_dict[field])
        
        # Insert into database
        response = supabase_service.table("assets").insert(asset_dict).execute()
        
        response_data = response.data if hasattr(response, 'data') else None
        response_error = response.error if hasattr(response, 'error') else None
        
        if response_error:
            return f"❌ Failed to create asset: {response_error}"
        elif response_data and isinstance(response_data, list) and len(response_data) > 0:
            created_asset = response_data[0]
            asset_id = created_asset.get('id')
            
            # Verify creation
            verify_response = supabase_service.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
            if verify_response.data and len(verify_response.data) > 0:
                owner_info = ""
                if family_member_id:
                    try:
                        fm_response = supabase_service.table("family_members").select("name").eq("id", family_member_id).execute()
                        if fm_response.data:
                            owner_info = f" for {fm_response.data[0].get('name')}"
                    except:
                        pass
                else:
                    owner_info = " for you (Self)"
                
                if asset_type == "stock":
                    return f"✅ Successfully added {asset_name} stock{owner_info} to your portfolio.{family_member_not_found_message}"
                elif asset_type == "bank_account":
                    return f"✅ Successfully added {asset_name} bank account{owner_info} to your portfolio.{family_member_not_found_message}"
                else:
                    return f"✅ Successfully added {asset_type} asset: {asset_name} to your portfolio.{family_member_not_found_message}"
            else:
                return "❌ Asset was inserted but could not be verified"
        else:
            return "❌ Failed to create asset: No data returned from database"
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in create_asset_from_llm_data: {error_details}")
        return f"❌ Failed to create asset: {str(e)}"


def parse_csv_file(file_content: bytes) -> Optional[Dict[str, Any]]:
    """Parse CSV file and extract asset information"""
    try:
        # Decode bytes to string
        content = file_content.decode('utf-8')
        print(f"DEBUG: CSV file content length: {len(content)}")
        print(f"DEBUG: First 200 chars of CSV content:\n{content[:200]}")
        
        csv_reader = csv.DictReader(io.StringIO(content))
        
        # Extract rows
        rows = list(csv_reader)
        print(f"DEBUG: Parsed {len(rows)} rows from CSV")
        
        if not rows:
            print("DEBUG: No rows found in CSV file")
            return None
        
        # Get columns
        columns = list(rows[0].keys()) if rows else []
        print(f"DEBUG: CSV columns found: {columns}")
        print(f"DEBUG: Sample row data: {rows[0] if rows else 'No rows'}")
        
        # Return structured data
        result = {
            "type": "csv",
            "rows": rows,
            "columns": columns
        }
        print(f"DEBUG: Returning CSV data with {len(rows)} rows and {len(columns)} columns")
        return result
    except Exception as e:
        import traceback
        print(f"ERROR parsing CSV: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None


def parse_pdf_file(file_content: bytes, password: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Parse PDF file and extract text. Supports password-protected PDFs."""
    try:
        # Try pdfplumber first (better text extraction)
        try:
            import pdfplumber
            pdf_stream = io.BytesIO(file_content)
            
            # pdfplumber doesn't directly support password, so we need to decrypt with PyPDF2 first if password is provided
            if password:
                # Decrypt with PyPDF2 first, then use pdfplumber
                try:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(pdf_stream)
                    if pdf_reader.is_encrypted:
                        if not pdf_reader.decrypt(password):
                            raise HTTPException(
                                status_code=400,
                                detail="Incorrect password for PDF file. Please check the password and try again."
                            )
                        # Create a new stream with decrypted content
                        from PyPDF2 import PdfWriter
                        writer = PdfWriter()
                        for page in pdf_reader.pages:
                            writer.add_page(page)
                        decrypted_stream = io.BytesIO()
                        writer.write(decrypted_stream)
                        decrypted_stream.seek(0)
                        pdf_stream = decrypted_stream
                except ImportError:
                    pass
                except Exception as e:
                    if "Incorrect password" in str(e) or isinstance(e, HTTPException):
                        raise
                    print(f"Error decrypting PDF with PyPDF2: {e}")
            
            with pdfplumber.open(pdf_stream) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if text.strip():
                    return {
                        "type": "pdf",
                        "text": text
                    }
        except ImportError:
            pass
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error with pdfplumber: {e}")
        
        # Fallback to PyPDF2
        try:
            import PyPDF2
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Handle password-protected PDFs
            if pdf_reader.is_encrypted:
                if not password:
                    raise HTTPException(
                        status_code=400,
                        detail="PDF file is password-protected. Please provide the password."
                    )
                if not pdf_reader.decrypt(password):
                    raise HTTPException(
                        status_code=400,
                        detail="Incorrect password for PDF file. Please check the password and try again."
                    )
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            if text.strip():
                return {
                    "type": "pdf",
                    "text": text
                }
        except ImportError:
            # Neither library is installed
            raise HTTPException(
                status_code=500, 
                detail="PDF parsing library not installed. Please install PyPDF2 or pdfplumber by running: pip install PyPDF2 pdfplumber"
            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error with PyPDF2: {e}")
        
        # If we get here, no text was extracted
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from PDF file. The file may be corrupted, password-protected, or contain only images."
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None


def format_extracted_data(extracted_data: Dict[str, Any]) -> str:
    """Format extracted data into a message for LLM processing"""
    if extracted_data["type"] == "csv":
        # Format CSV data
        rows = extracted_data.get("rows", [])
        if not rows:
            return "I have uploaded a CSV file but it appears to be empty."
        
        # Get column names
        columns = extracted_data.get("columns", [])
        
        # Create a comprehensive message with ALL CSV data
        formatted = "I have uploaded a CSV file containing stock/asset information. The file contains ALL the data below. Please extract asset information from EVERY row and add ALL assets to my portfolio.\n\n"
        
        # Show column headers
        if columns:
            formatted += f"CSV Columns ({len(columns)} columns): {', '.join(columns)}\n"
            formatted += f"Total Rows: {len(rows)}\n\n"
            formatted += "=" * 80 + "\n"
            formatted += "COMPLETE CSV DATA (ALL ROWS):\n"
            formatted += "=" * 80 + "\n\n"
        
        # Include ALL rows in a clear format
        for i, row in enumerate(rows, 1):
            formatted += f"--- Row {i} of {len(rows)} ---\n"
            for key, value in row.items():
                # Handle None values and empty strings
                if value is None:
                    display_value = ""
                elif value == "":
                    display_value = "(empty)"
                else:
                    display_value = str(value).strip()
                formatted += f"  {key}: {display_value}\n"
            formatted += "\n"
        
        formatted += "=" * 80 + "\n"
        formatted += "\nCOLUMN MAPPINGS (for CSV files):\n"
        formatted += "- SYMBOL or STOCK SYMBOL → stock_symbol\n"
        formatted += "- QTY or QUANTITY → quantity (number of shares)\n"
        formatted += "- AVG PRICE or AVERAGE PRICE or PURCHASE PRICE → purchase_price\n"
        formatted += "- LTP or CURRENT PRICE or LATEST PRICE → current_price (optional)\n"
        formatted += "- CUR. VALUE or CURRENT VALUE → current_value (optional, can be calculated)\n"
        formatted += "- PURCHASE DATE or BUY DATE or DATE → purchase_date (format: YYYY-MM-DD)\n"
        formatted += "- If purchase_date is missing, use today's date (YYYY-MM-DD format)\n"
        formatted += "- Market should be determined from the stock symbol/name (Indian stocks → India/INR, others → Europe/EUR)\n"
        formatted += "- Stock owner defaults to 'self' if not specified\n"
        formatted += "\nIMPORTANT INSTRUCTIONS:\n"
        formatted += "1. Process EVERY row in the CSV file above\n"
        formatted += "2. Extract asset information from each row using the column mappings above\n"
        formatted += "3. For stocks: use AVG PRICE as purchase_price, QTY as quantity, SYMBOL as stock_symbol\n"
        formatted += "4. IMPORTANT: Add assets with whatever information is available. Use defaults for missing optional fields:\n"
        formatted += "   - If purchase_date is missing, use today's date (YYYY-MM-DD format)\n"
        formatted += "   - If family_member_name is missing, use 'self'\n"
        formatted += "   - If asset_name is missing, use the stock_symbol as the asset_name\n"
        formatted += "5. Add ALL assets to my portfolio immediately with available data\n"
        formatted += "6. Only ask for information if CRITICAL fields are missing (stock_symbol, quantity, purchase_price)\n"
        formatted += "7. Do not skip any rows - process all of them\n"
        formatted += "\nPlease extract and add all assets from the CSV data above to my portfolio. Add them with available information and use defaults for missing optional fields."
        
        return formatted
    
    elif extracted_data["type"] == "pdf":
        # Format PDF text
        text = extracted_data.get("text", "")
        if not text.strip():
            return "I have uploaded a PDF file but could not extract any text from it."
        
        # Limit text length to avoid token limits (increased from 8000 to allow more content)
        if len(text) > 15000:
            text = text[:15000] + "... (truncated)"
        
        formatted = "I have uploaded a PDF file containing financial/asset information. The file contains ALL the data below. Please extract asset information from the ENTIRE content and add ALL assets to my portfolio.\n\n"
        formatted += "=" * 80 + "\n"
        formatted += "COMPLETE PDF CONTENT:\n"
        formatted += "=" * 80 + "\n\n"
        formatted += text
        formatted += "\n\n"
        formatted += "=" * 80 + "\n"
        formatted += "\nIMPORTANT INSTRUCTIONS FOR PDF FILES:\n"
        formatted += "1. The PDF content above may contain MULTIPLE assets (e.g., multiple bank accounts, multiple stocks, multiple mutual funds, etc.)\n"
        formatted += "2. You MUST identify and extract EVERY asset mentioned in the PDF content\n"
        formatted += "3. Each bank account, stock, mutual fund, fixed deposit, insurance policy, or commodity mentioned is a SEPARATE asset\n"
        formatted += "4. CRITICAL: If multiple assets are present (e.g., multiple bank accounts), you MUST return an array of assets in the 'assets' field\n"
        formatted += "5. Extract asset information for EACH asset individually\n"
        formatted += "6. IMPORTANT: Add assets with whatever information is available. Use defaults for missing optional fields:\n"
        formatted += "   - If purchase_date is missing, use today's date (YYYY-MM-DD format)\n"
        formatted += "   - If family_member_name is missing, use 'self'\n"
        formatted += "   - If asset_name is missing, use appropriate defaults (e.g., bank name for bank accounts)\n"
        formatted += "7. Do not skip any assets - process ALL of them\n"
        formatted += "8. If an asset is missing critical required information, skip that specific asset but process all other assets\n"
        formatted += "\nPlease extract and add ALL assets from the PDF content above to my portfolio. Add them with available information and use defaults for missing optional fields."
        return formatted
    
    return "I have uploaded a file. Please extract asset information from it."


@router.post("/upload", response_model=ChatResponse)
async def upload_file(
    file: UploadFile = File(...),
    context: str = Form("assets"),
    conversation_history: Optional[str] = Form(None),
    pdf_password: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Handle file uploads (PDF or CSV) and extract asset information
    """
    print(f"DEBUG UPLOAD: File upload endpoint called")
    print(f"DEBUG UPLOAD: File name: {file.filename}")
    print(f"DEBUG UPLOAD: Context: {context}")
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Validate file type
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        if file_extension not in ['pdf', 'csv']:
            raise HTTPException(status_code=400, detail="Only PDF and CSV files are supported")
        
        # Read file content
        print(f"DEBUG UPLOAD: About to read file content")
        file_content = await file.read()
        print(f"DEBUG UPLOAD: File content read. Size: {len(file_content)} bytes")
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        # Parse file based on type
        extracted_data = None
        if file_extension == 'csv':
            print(f"DEBUG UPLOAD: Parsing CSV file...")
            extracted_data = parse_csv_file(file_content)
            print(f"DEBUG UPLOAD: CSV file parsed. Rows: {len(extracted_data.get('rows', [])) if extracted_data else 0}")
            if extracted_data:
                print(f"DEBUG UPLOAD: CSV columns: {extracted_data.get('columns', [])}")
                print(f"DEBUG UPLOAD: First row sample: {extracted_data.get('rows', [])[0] if extracted_data.get('rows') else 'No rows'}")
            else:
                print(f"DEBUG UPLOAD: CSV parsing returned None - file might be empty or invalid")
        elif file_extension == 'pdf':
            print(f"DEBUG UPLOAD: Parsing PDF file...")
            extracted_data = parse_pdf_file(file_content, password=pdf_password)
            print(f"DEBUG UPLOAD: PDF file parsed. Text length: {len(extracted_data.get('text', '')) if extracted_data else 0}")
        
        if not extracted_data:
            if file_extension == 'pdf':
                raise HTTPException(
                    status_code=400, 
                    detail="Could not extract data from PDF file. Please ensure the PDF contains readable text and is not password-protected."
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="Could not extract data from CSV file. Please ensure the file is a valid CSV format."
                )
        
        # Parse conversation history if provided
        parsed_history = []
        if conversation_history:
            try:
                parsed_history = json.loads(conversation_history)
            except:
                parsed_history = []
        
        # Format extracted data into a message
        print(f"DEBUG UPLOAD: About to format extracted data")
        extracted_text = format_extracted_data(extracted_data)
        print(f"DEBUG UPLOAD: Formatted extracted text length: {len(extracted_text)}")
        print(f"DEBUG UPLOAD: First 1000 chars of extracted text:\n{extracted_text[:1000]}")
        if len(extracted_text) > 1000:
            print(f"DEBUG UPLOAD: ... (truncated, total length: {len(extracted_text)})")
        
        # Get portfolio data (reuse logic from chat endpoint)
        portfolio_data = {}
        if context == "assets":
            try:
                # Fetch assets
                assets_response = supabase_service.table("assets").select("*").eq("user_id", user_id).eq("is_active", True).execute()
                assets = assets_response.data if assets_response.data else []
                
                # Fetch family members
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members_list = family_members_response.data if family_members_response.data else []
                
                # Build portfolio data structure (simplified version)
                portfolio_data = {
                    "india": {"stocks": [], "bank_accounts": [], "mutual_funds": [], "fixed_deposits": [], "insurance_policies": [], "commodities": []},
                    "europe": {"stocks": [], "bank_accounts": [], "mutual_funds": [], "fixed_deposits": [], "insurance_policies": [], "commodities": []},
                    "family_members": [
                        {"id": str(fm.get("id")), "name": fm.get("name"), "relationship": fm.get("relationship")}
                        for fm in family_members_list
                    ]
                }
                
                # Organize assets by market
                for asset in assets:
                    currency = asset.get("currency", "USD")
                    market = "india" if currency == "INR" else "europe" if currency == "EUR" else None
                    if not market:
                        continue
                    
                    asset_type = asset.get("type")
                    if asset_type == "stock":
                        portfolio_data[market]["stocks"].append(asset)
                    elif asset_type == "bank_account":
                        portfolio_data[market]["bank_accounts"].append(asset)
                    elif asset_type == "mutual_fund":
                        portfolio_data[market]["mutual_funds"].append(asset)
                    elif asset_type == "fixed_deposit":
                        portfolio_data[market]["fixed_deposits"].append(asset)
                    elif asset_type == "insurance_policy":
                        portfolio_data[market]["insurance_policies"].append(asset)
                    elif asset_type == "commodity":
                        portfolio_data[market]["commodities"].append(asset)
            except Exception as e:
                print(f"Error fetching portfolio data: {e}")
                portfolio_data = {}
        
        # Process with asset LLM service
        print(f"DEBUG: About to call asset_llm_service.process_asset_command")
        print(f"DEBUG: user_message (extracted_text) length: {len(extracted_text)}")
        print(f"DEBUG: First 1000 chars of user_message:\n{extracted_text[:1000]}")
        print(f"DEBUG: conversation_history length: {len(parsed_history)}")
        
        asset_result = await asset_llm_service.process_asset_command(
            user_message=extracted_text,
            user_id=user_id,
            portfolio_data=portfolio_data,
            conversation_history=parsed_history
        )
        
        print(f"DEBUG: asset_result action: {asset_result.get('action')}")
        print(f"DEBUG: asset_result asset_data keys: {list(asset_result.get('asset_data', {}).keys())}")
        print(f"DEBUG: asset_result has assets array: {'assets' in asset_result}")
        if 'assets' in asset_result:
            print(f"DEBUG: asset_result assets array length: {len(asset_result.get('assets', []))}")
        print(f"DEBUG: asset_result response: {asset_result.get('response', '')[:200]}")
        
        # Handle the result
        action = asset_result.get("action", "none")
        asset_data = asset_result.get("asset_data", {})
        
        llm_response = ""
        
        # Get current message order (max message_order + 1 for this user and context)
        try:
            max_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).eq("context", context).order("message_order", desc=True).limit(1).execute()
            if max_order_response.data and len(max_order_response.data) > 0:
                max_order = max_order_response.data[0].get("message_order", -1)
                # Safety check: if max_order is too large (timestamp-based), reset to 0
                # PostgreSQL INTEGER max is 2,147,483,647, but timestamps are ~1.7 trillion
                # Timestamps in milliseconds are typically > 1 billion (1,000,000,000)
                if max_order and max_order > 1000000000:  # If it's a timestamp (milliseconds), reset
                    print(f"WARNING: Found timestamp-based message_order ({max_order}), resetting to 0")
                    current_order = 0
                elif max_order and max_order > 2147483640:  # Close to INTEGER max, reset to avoid overflow
                    print(f"WARNING: message_order ({max_order}) too close to INTEGER max, resetting to 0")
                    current_order = 0
                else:
                    current_order = (max_order if max_order is not None else -1) + 1
            else:
                current_order = 0
        except Exception as e:
            import traceback
            print(f"Error getting message order: {e}")
            current_order = 0
        
        # Save user message (file upload)
        user_message_data = {
            "user_id": user_id,
            "role": "user",
            "content": f"Uploaded {file.filename} file",
            "message_order": current_order,
            "context": context
        }
        user_insert_response = supabase_service.table("chat_messages").insert(user_message_data).execute()
        user_message_id = user_insert_response.data[0]["id"] if user_insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
        current_order += 1
        
        # Handle the result - for CSV files, process each row individually
        if file_extension == 'csv' and extracted_data and extracted_data.get('rows'):
            # Process each CSV row individually
            csv_rows = extracted_data.get('rows', [])
            created_count = 0
            failed_count = 0
            failed_symbols = []
            
            for row in csv_rows:
                try:
                    # Extract data from CSV row
                    symbol_key = None
                    for key in row.keys():
                        if 'symbol' in key.lower():
                            symbol_key = key
                            break
                    
                    if not symbol_key or not row.get(symbol_key):
                        continue  # Skip rows without symbol
                    
                    # Build asset_data from CSV row
                    symbol = str(row[symbol_key]).strip().strip('"')
                    qty_str = None
                    price_str = None
                    
                    # Find quantity column
                    for key in row.keys():
                        if 'qty' in key.lower() or 'quantity' in key.lower():
                            qty_str = row.get(key)
                            break
                    
                    # Find price column
                    for key in row.keys():
                        if 'avg price' in key.lower() or 'average price' in key.lower() or 'purchase price' in key.lower():
                            price_str = row.get(key)
                            break
                    
                    if not qty_str or not price_str:
                        failed_count += 1
                        failed_symbols.append(symbol)
                        continue
                    
                    try:
                        quantity = float(qty_str)
                        purchase_price = float(price_str)
                    except (ValueError, TypeError):
                        failed_count += 1
                        failed_symbols.append(symbol)
                        continue
                    
                    # Determine market (Indian stocks default to India)
                    market = "india"  # Default for Indian stock names
                    currency = "INR"
                    
                    # Build asset data
                    from datetime import date
                    csv_asset_data = {
                        "asset_type": "stock",
                        "stock_symbol": symbol,
                        "asset_name": symbol,
                        "quantity": quantity,
                        "purchase_price": purchase_price,
                        "purchase_date": date.today().strftime('%Y-%m-%d'),  # Default to today
                        "market": market,
                        "currency": currency,
                        "family_member_name": "self"  # Default to self
                    }
                    
                    # Create asset
                    result_msg = await create_asset_from_llm_data(csv_asset_data, user_id, context)
                    if result_msg.startswith("✅"):
                        created_count += 1
                    else:
                        failed_count += 1
                        failed_symbols.append(symbol)
                except Exception as e:
                    print(f"Error processing CSV row: {e}")
                    failed_count += 1
                    if symbol_key and row.get(symbol_key):
                        failed_symbols.append(str(row[symbol_key]))
            
            # Build response message
            if created_count > 0:
                llm_response = f"✅ Successfully added {created_count} stock{'s' if created_count > 1 else ''} from your CSV file to your portfolio."
                if failed_count > 0:
                    llm_response += f" {failed_count} row{'s' if failed_count > 1 else ''} could not be processed."
            else:
                llm_response = f"❌ Could not add any stocks from the CSV file. Please check the file format."
        elif action == "none":
            # Missing information - return the message asking for it
            llm_response = asset_result.get("response", "I need more information to add the assets from your file.")
        elif action == "add":
            # Check if LLM returned multiple assets in an array (for PDF files with multiple assets)
            assets_array = asset_result.get("assets", [])
            
            if assets_array and isinstance(assets_array, list) and len(assets_array) > 0:
                # Process multiple assets (for PDF files with multiple bank accounts, stocks, etc.)
                created_count = 0
                failed_count = 0
                failed_assets = []
                
                for asset_item in assets_array:
                    try:
                        result_msg = await create_asset_from_llm_data(asset_item, user_id, context)
                        if result_msg.startswith("✅"):
                            created_count += 1
                        else:
                            failed_count += 1
                            asset_name = asset_item.get("asset_name") or asset_item.get("stock_symbol") or asset_item.get("bank_name") or "asset"
                            failed_assets.append(asset_name)
                    except Exception as e:
                        print(f"Error processing asset from PDF: {e}")
                        failed_count += 1
                        asset_name = asset_item.get("asset_name") or asset_item.get("stock_symbol") or asset_item.get("bank_name") or "asset"
                        failed_assets.append(asset_name)
                
                # Build response message
                if created_count > 0:
                    asset_type_name = "asset" if file_extension == 'pdf' else "stock"
                    llm_response = f"✅ Successfully added {created_count} {asset_type_name}{'s' if created_count > 1 else ''} from your {file_extension.upper()} file to your portfolio."
                    if failed_count > 0:
                        llm_response += f" {failed_count} asset{'s' if failed_count > 1 else ''} could not be processed."
                else:
                    llm_response = f"❌ Could not add any assets from your {file_extension.upper()} file. Please check the file content."
            elif asset_data:
                # Single asset (backward compatibility)
                llm_response = await create_asset_from_llm_data(asset_data, user_id, context)
                if not llm_response.startswith("✅"):
                    # If creation failed, prepend file info
                    llm_response = f"I've extracted information from your {file_extension.upper()} file. {llm_response}"
            else:
                llm_response = f"❌ Could not extract asset information from your {file_extension.upper()} file. Please ensure the file contains valid asset data."
        else:
            llm_response = asset_result.get("response", f"Processed your {file_extension.upper()} file.")
        
        # Save assistant response
        assistant_message_data = {
            "user_id": user_id,
            "role": "assistant",
            "content": llm_response,
            "message_order": current_order + 1,
            "context": context
        }
        assistant_insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
        assistant_message_id = assistant_insert_response.data[0]["id"] if assistant_insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
        
        return ChatResponse(
            response=llm_response,
            message_id=assistant_message_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in upload_file: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")
