"""
Chat/LLM API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import time
import random
import uuid
import asyncio
from auth import get_current_user, security
from services.llm_service import llm_service
from services.asset_llm_service import asset_llm_service
from database.supabase_client import supabase, supabase_service, get_supabase_client_with_token
from models import AssetCreate, AssetUpdate

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
                
                if len(assets) > 0:
                
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
        
        # Get current message order (max message_order + 1 for this user and context)
        try:
            max_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).eq("context", context).order("message_order", desc=True).limit(1).execute()
            if max_order_response.data and len(max_order_response.data) > 0:
                current_order = max_order_response.data[0].get("message_order", -1) + 1
            else:
                current_order = 0
        except Exception as e:
            import traceback
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
                            # Update asset
                            if not asset_id:
                                llm_response = "❌ Could not find the asset to update. Please specify the asset name or ID more clearly."
                            else:
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

