"""
Asset LLM Service - Handles natural language asset management operations
"""

import os
import json
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()


class AssetLLMService:
    """Service for handling asset operations via natural language"""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    def _extract_info_from_message(self, user_message: str, args: Dict, conversation_history: Optional[List[Dict]] = None, portfolio_data: Optional[Dict] = None) -> Dict:
        """Post-process to extract information that LLM might have missed"""
        import re
        from datetime import datetime, date
        
        user_lower = user_message.lower()
        
        # Build combined text from conversation history for better extraction
        combined_text = user_message
        if conversation_history:
            # Get all user messages from history
            for msg in conversation_history:
                if msg.get("role") == "user":
                    combined_text += " " + msg.get("content", "")
        combined_text_lower = combined_text.lower()
        
        # Extract quantity if missing
        if not args.get('quantity'):
            # Try explicit numbers with shares/stocks
            quantity_match = re.search(r'(\d+)\s*(?:shares?|stocks?|units?)', user_lower)
            if quantity_match:
                args['quantity'] = int(quantity_match.group(1))
            else:
                # Check for "a [name] stock" or "a stock" or "a share" (implies quantity = 1)
                # Pattern: "a" followed by optional words, then "stock" or "share"
                if re.search(r'\ba\s+[\w\s]*?(?:stock|share)', user_lower):
                    args['quantity'] = 1
                # Check for standalone numbers that might be quantity (e.g., "100 Reliance")
                elif re.search(r'\b(\d+)\s+(?:reliance|tcs|infosys|hdfc|icici|sbi|wipro|apple|aapl|google|googl)', user_lower):
                    quantity_match = re.search(r'\b(\d+)\s+(?:reliance|tcs|infosys|hdfc|icici|sbi|wipro|apple|aapl|google|googl)', user_lower)
                    if quantity_match:
                        args['quantity'] = int(quantity_match.group(1))
                # Check for number at the start (e.g., "100 Reliance stock")
                elif re.search(r'^(\d+)\s+', user_message):
                    quantity_match = re.search(r'^(\d+)\s+', user_message)
                    if quantity_match:
                        args['quantity'] = int(quantity_match.group(1))
        
        # Extract price if missing
        if not args.get('purchase_price'):
            price_match = re.search(r'(?:at|for|costs?|@)\s*(\d+(?:\.\d+)?)', user_lower)
            if price_match:
                args['purchase_price'] = float(price_match.group(1))
        
        # Extract date if missing
        if not args.get('purchase_date'):
            # Try DD.MM.YYYY format
            date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', user_message)
            if date_match:
                day, month, year = date_match.groups()
                try:
                    args['purchase_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    pass
            else:
                # Try DD-MM-YYYY format
                date_match = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', user_message)
                if date_match:
                    day, month, year = date_match.groups()
                    try:
                        args['purchase_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    except:
                        pass
        
        # Extract stock symbol from stock name if missing
        if not args.get('stock_symbol') and args.get('asset_type') == 'stock':
            # Common Indian stocks
            indian_stocks = {
                'reliance': 'RELIANCE',
                'tcs': 'TCS',
                'infosys': 'INFY',
                'hdfc': 'HDFC',
                'icici': 'ICICIBANK',
                'sbi': 'SBIN',
                'wipro': 'WIPRO',
                'bharti': 'BHARTIARTL',
                'itc': 'ITC',
                'lt': 'LT'
            }
            for stock_name, symbol in indian_stocks.items():
                if stock_name in user_lower:
                    args['stock_symbol'] = symbol
                    if not args.get('asset_name'):
                        args['asset_name'] = stock_name.title() + ' Industries' if stock_name != 'tcs' else 'TCS'
                    if not args.get('market'):
                        args['market'] = 'india'
                    break
        
        # Extract market from currency mentions if missing - check combined text
        if not args.get('market'):
            # Check for explicit market mentions in combined text
            if 'indian market' in combined_text_lower or 'india market' in combined_text_lower:
                args['market'] = 'india'
            elif 'european market' in combined_text_lower or 'europe market' in combined_text_lower:
                args['market'] = 'europe'
            elif 'rupee' in combined_text_lower or '₹' in combined_text or 'inr' in combined_text_lower:
                args['market'] = 'india'
            elif 'euro' in combined_text_lower or '€' in combined_text or 'eur' in combined_text_lower:
                args['market'] = 'europe'
        
        # Extract bank account information if missing - check conversation history too
        if args.get('asset_type') == 'bank_account':
            # Extract bank name - check conversation history
            if not args.get('bank_name'):
                # Common Indian banks
                indian_banks = ['hdfc', 'sbi', 'icici', 'axis', 'pnb', 'bob', 'canara', 'union', 'indian bank', 'indianbank', 'kotak', 'yes bank', 'yesbank']
                for bank in indian_banks:
                    if bank in combined_text_lower:
                        args['bank_name'] = bank.title() + ' Bank' if not bank.endswith('bank') else bank.title()
                        if not args.get('market'):
                            args['market'] = 'india'
                        break
            
            # If account name is not provided but bank name is, use bank name as account name
            if not args.get('asset_name') and args.get('bank_name'):
                args['asset_name'] = args.get('bank_name')
            
            # Extract account number - check current message, conversation history, and notes field
            if not args.get('account_number'):
                # First, check if LLM put it in notes field (e.g., "Account number reconfirmed as 12831283")
                notes = args.get('notes', '')
                if notes:
                    # Look for account number patterns in notes - try multiple patterns
                    notes_lower = notes.lower()
                    # Pattern 1: "account number reconfirmed as 12831283" or "account number is 12831283"
                    acc_match_notes = re.search(r'(?:account\s*(?:number|no|#)?|acc\s*(?:number|no|#)?)\s*(?:is|:)?\s*(?:reconfirmed\s+as\s+)?(\d+)', notes_lower)
                    if acc_match_notes:
                        args['account_number'] = acc_match_notes.group(1)
                    else:
                        # Pattern 2: "reconfirmed as 12831283" or "is 12831283"
                        simple_match_notes = re.search(r'(?:reconfirmed\s+as|is|:)\s+(\d{6,})', notes_lower)
                        if simple_match_notes:
                            args['account_number'] = simple_match_notes.group(1)
                
                # If not found in notes, check current message and conversation history (combined_text)
                if not args.get('account_number'):
                    # Patterns: "account number 123456", "acc no 1234", "account 1234567890", "is 12831283"
                    acc_match = re.search(r'(?:account\s*(?:number|no|#)?|acc\s*(?:number|no|#)?)\s*(?:is|:)?\s*(\d+)', combined_text_lower)
                    if acc_match:
                        args['account_number'] = acc_match.group(1)
                    else:
                        # Try simpler pattern: "is 12831283" or "reconfirmed as 12831283" (for follow-up messages)
                        simple_match = re.search(r'(?:is|as|:)\s+(\d{6,})', combined_text_lower)
                        if simple_match:
                            args['account_number'] = simple_match.group(1)
                        else:
                            # Try even simpler: just a long number (6+ digits) that might be account number
                            # But only if we're in a bank account context
                            number_match = re.search(r'\b(\d{8,})\b', combined_text_lower)
                            if number_match:
                                args['account_number'] = number_match.group(1)
            
            # Extract account type - check conversation history too
            if not args.get('account_type'):
                if 'savings' in combined_text_lower:
                    args['account_type'] = 'savings'
                elif 'checking' in combined_text_lower:
                    args['account_type'] = 'checking'
                elif 'current' in combined_text_lower and 'account' in combined_text_lower:
                    args['account_type'] = 'current'
            
            # Extract current balance - check conversation history too, handle comma-separated numbers
            if not args.get('current_value'):
                # Patterns: "balance of 50000", "has 10000", "with 5000 rupees", "50000 in account", "50,000 rupees"
                balance_patterns = [
                    r'balance\s+(?:of|is|:)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',
                    r'balance\s+(?:of|is|:)?\s*(\d+(?:\.\d+)?)',
                    r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:rupees?|₹|inr|euros?|€|eur)',
                    r'(\d+(?:\.\d+)?)\s*(?:rupees?|₹|inr|euros?|€|eur)',
                    r'has\s+(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',
                    r'has\s+(\d+(?:\.\d+)?)',
                    r'with\s+(\d{1,3}(?:,\d{3})*(?:\.\d+)?)',
                    r'with\s+(\d+(?:\.\d+)?)',
                ]
                for pattern in balance_patterns:
                    balance_match = re.search(pattern, combined_text_lower)
                    if balance_match:
                        # Remove commas from the number
                        balance_str = balance_match.group(1).replace(',', '')
                        args['current_value'] = float(balance_str)
                        break
        
        # Extract family_member_name if missing - check notes, other fields, and conversation
        if not args.get('family_member_name') and args.get('asset_type') in ['stock', 'bank_account']:
            # Check if LLM put it in notes or other fields
            notes = args.get('notes', '').lower()
            bank_name = args.get('bank_name', '').lower()  # Sometimes LLM puts it here incorrectly
            
            family_member_found = False
            
            # Check for "self", "me", "myself", "I" patterns in combined text
            # Use regex to match whole words/phrases to avoid false positives
            self_patterns = [
                r'\bowner\s+is\s+(?:self|me|myself)\b',
                r'\b(?:stock|account)\s+owner\s+is\s+(?:self|me|myself)\b',
                r'\bfor\s+(?:self|me|myself)\b',
                r'\bby\s+(?:self|me|myself)\b',
                r'\bpurchased\s+by\s+(?:self|me|myself)\b',
                r'\bbought\s+by\s+(?:self|me|myself)\b',
                r'\bi\s+purchased\b',
                r'\bi\s+bought\b',
                r'\bi\s+own\b',
                r'\bmy\s+(?:stock|account|bank\s+account|asset)\b',
                r'\bbelongs\s+to\s+(?:me|self|myself)\b',
                r'\bis\s+(?:mine|my)\b',
            ]
            
            for pattern in self_patterns:
                if re.search(pattern, combined_text_lower):
                    args['family_member_name'] = 'self'
                    family_member_found = True
                    break
            
            # Also check for standalone "I" at the start of sentences (e.g., "I purchased", "I bought", "I have an account")
            # and simple ownership indicators
            if not family_member_found:
                # Check if message starts with "I" followed by action words
                if re.search(r'^\s*i\s+(?:purchased|bought|own|have)', user_lower):
                    args['family_member_name'] = 'self'
                    family_member_found = True
                # Check for "my account", "my bank account" patterns
                elif re.search(r'\bmy\s+(?:bank\s+)?account\b', user_lower):
                    args['family_member_name'] = 'self'
                    family_member_found = True
            
            # Check for family member names in combined text (case-insensitive)
            if not family_member_found:
                # Get available family members from portfolio_data
                family_members_list = []
                if portfolio_data and "family_members" in portfolio_data:
                    family_members_list = portfolio_data.get("family_members", [])
                
                # Check for each family member name in the conversation
                for fm in family_members_list:
                    fm_name = fm.get("name", "").lower()
                    if fm_name and fm_name in combined_text_lower:
                        args['family_member_name'] = fm.get("name")  # Use original case
                        family_member_found = True
                        break
            
            # If not found in conversation, check notes for family member mentions
            if not family_member_found and 'natesh' in notes:
                args['family_member_name'] = 'Natesh'
                family_member_found = True
            
            # Check if bank_name was incorrectly used (LLM sometimes puts family member name there)
            if not family_member_found and bank_name and bank_name not in ['savings', 'checking', 'current'] and len(bank_name) > 2:
                # Might be a family member name
                args['family_member_name'] = args.get('bank_name')
                # Remove it from bank_name
                if args.get('asset_type') == 'stock':
                    args.pop('bank_name', None)
        
        return args
    
    async def process_asset_command(
        self,
        user_message: str,
        user_id: str,
        portfolio_data: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language command for asset management
        
        Args:
            user_message: The current user message
            user_id: User ID
            portfolio_data: Current portfolio data
            conversation_history: List of previous messages in format [{"role": "user"/"assistant", "content": "..."}]
        
        Returns:
            Dict with:
            - action: "add", "delete", "update", or "none"
            - asset_data: Dict with asset information (for add/update)
            - asset_id: str (for delete/update)
            - response: str (natural language response)
            - needs_confirmation: bool
        """
        if self.provider == "gemini":
            return await self._process_with_gemini(user_message, user_id, portfolio_data, conversation_history)
        else:
            # Fallback for other providers
            return {
                "action": "none",
                "response": "Asset management via LLM is currently only supported with Gemini. Please use the asset management UI or set GEMINI_API_KEY in your environment."
            }
    
    def _extract_incomplete_request_from_history(self, conversation_history: Optional[List[Dict]]) -> Optional[Dict]:
        """
        Check conversation history for a previous incomplete asset creation request.
        Returns the incomplete request data if found, None otherwise.
        """
        if not conversation_history or len(conversation_history) < 2:
            return None
        
        # Look for pattern: user message about adding asset, followed by assistant asking for missing info
        # Check last 6 messages (3 exchanges) to catch more context
        recent_messages = conversation_history[-6:] if len(conversation_history) >= 6 else conversation_history
        
        # Find the last assistant message that asks for missing information
        incomplete_request = None
        for i in range(len(recent_messages) - 1, -1, -1):
            msg = recent_messages[i]
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                # Check if assistant is asking for missing information
                asking_keywords = ["need more information", "please provide", "missing", "specify", "need", "provide", "information"]
                if any(keyword in content for keyword in asking_keywords):
                    # Look backwards for the user's original request
                    for j in range(i - 1, -1, -1):
                        prev_msg = recent_messages[j]
                        if prev_msg.get("role") == "user":
                            prev_content = prev_msg.get("content", "").lower()
                            # Check if the previous user message mentions adding/purchasing assets
                            asset_keywords = ["purchase", "buy", "add", "create", "stock", "share", "mutual fund", "bank account", "asset"]
                            if any(keyword in prev_content for keyword in asset_keywords):
                                # This is likely the incomplete request
                                incomplete_request = {
                                    "original_message": prev_msg.get("content", ""),
                                    "missing_info_message": msg.get("content", "")
                                }
                                break
                    if incomplete_request:
                        break
        
        return incomplete_request
    
    async def _process_with_gemini(
        self,
        user_message: str,
        user_id: str,
        portfolio_data: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        print(f"DEBUG asset_llm_service: user_message length: {len(user_message)}")
        print(f"DEBUG asset_llm_service: First 500 chars of user_message:\n{user_message[:500]}")
        print(f"DEBUG asset_llm_service: conversation_history length: {len(conversation_history) if conversation_history else 0}")
        """
        Process asset command using Gemini LLM
        """
        # Note: We no longer combine messages here - instead we pass full conversation history to LLM
        # This allows the LLM to extract information from all messages in the conversation
        # The conversation_history will be included in the prompt so LLM can see all context
        
        try:
            from google import genai
            from google.genai import types
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {
                    "action": "none",
                    "response": "GEMINI_API_KEY not found. Please set it in your .env file."
                }
            
            client = genai.Client(api_key=api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            
            # Build prompt with portfolio context
            portfolio_context = ""
            if portfolio_data:
                # Create a simplified asset list with IDs for easier matching
                asset_list = []
                for market in ["india", "europe"]:
                    if market in portfolio_data:
                        for asset_type in ["stocks", "mutual_funds", "bank_accounts", "fixed_deposits", "insurance_policies", "commodities"]:
                            if asset_type in portfolio_data[market]:
                                for asset in portfolio_data[market][asset_type]:
                                    asset_info = {
                                        "id": asset.get("id"),
                                        "name": asset.get("name"),
                                        "type": asset_type[:-1] if asset_type.endswith("s") else asset_type,  # Remove plural
                                        "currency": asset.get("currency", "USD")
                                    }
                                    # Add type-specific identifiers
                                    if asset_type == "stocks":
                                        asset_info["symbol"] = asset.get("symbol")
                                    elif asset_type == "mutual_funds":
                                        asset_info["code"] = asset.get("mutual_fund_code")
                                    elif asset_type == "bank_accounts":
                                        asset_info["bank_name"] = asset.get("bank_name")
                                        asset_info["account_number"] = asset.get("account_number")
                                    elif asset_type == "insurance_policies":
                                        asset_info["policy_number"] = asset.get("policy_number")
                                    elif asset_type == "commodities":
                                        asset_info["commodity_name"] = asset.get("commodity_name")
                                    
                                    asset_list.append(asset_info)
                
                portfolio_json = json.dumps(portfolio_data, indent=2, default=str)
                asset_list_json = json.dumps(asset_list, indent=2, default=str)
                
                # Extract family members from portfolio data if available
                family_members_info = ""
                if portfolio_data and "family_members" in portfolio_data:
                    family_members_list = portfolio_data.get("family_members", [])
                    if family_members_list:
                        family_members_names = [fm.get("name", "") for fm in family_members_list]
                family_members_info = f"""
AVAILABLE FAMILY MEMBERS (for stock owner):
{json.dumps(family_members_list, indent=2, default=str)}

Family Member Names: {', '.join(family_members_names) if family_members_names else 'None'}

IMPORTANT: 
- Use one of the family member names above (e.g., "{family_members_names[0] if family_members_names else 'John'}") if the stock belongs to that family member
- Use "self" or "me" if the asset belongs to the user themselves
- The family_member_name field is REQUIRED for stocks
"""
                
                portfolio_context = f"""
Current Portfolio (Full Details):
```json
{portfolio_json}
```

Asset List (for ID matching):
```json
{asset_list_json}
```

{family_members_info}

AVAILABLE MARKETS:
- "india" (currency: INR, ₹, rupees) - for Indian stocks and assets
- "europe" (currency: EUR, €, euros) - for European stocks and assets

IMPORTANT: The market field is REQUIRED and must be either "india" or "europe".

When the user wants to delete or update an asset, you MUST find the matching asset ID from the Asset List above. Match assets by:
- Name (exact or partial match)
- Symbol (for stocks)
- Code (for mutual funds)
- Bank name and account number (for bank accounts)
- Policy number (for insurance)
- Commodity name (for commodities)

If you cannot find a matching asset, set action to "none" and explain that the asset was not found.
"""
            
            # Build conversation history context if available
            conversation_context = ""
            if conversation_history and len(conversation_history) > 0:
                # Get recent conversation (last 20 messages) for context - enough to see full multi-turn conversations
                recent_messages = conversation_history[-20:] if len(conversation_history) > 20 else conversation_history
                conversation_context = "\n\n=== CONVERSATION HISTORY (READ ALL MESSAGES BELOW) ===\n"
                for i, msg in enumerate(recent_messages, 1):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if role == "user":
                        conversation_context += f"[Message {i}] User: {content}\n"
                    elif role == "assistant":
                        conversation_context += f"[Message {i}] Assistant: {content}\n"
                conversation_context += "\n=== END CONVERSATION HISTORY ===\n\n"
                conversation_context += "CRITICAL INSTRUCTION: You MUST extract information from ALL messages in the conversation history above, not just the current/last message. "
                conversation_context += "If the user mentioned quantity in message 1, stock name in message 2, and price in message 3, you MUST combine all of them. "
                conversation_context += "Only ask for information that is truly missing from ALL messages in the conversation.\n"
            else:
                conversation_context = "\n\n=== NO PREVIOUS CONVERSATION HISTORY ===\n"
                conversation_context += "This is the first message in the conversation. All information must be extracted from the current user message below.\n"
            
            prompt = f"""You are a financial assistant that helps users manage their assets through natural language commands.

{portfolio_context}
{conversation_context}

Analyze the user's message and the conversation history above to determine if they want to:
1. ADD a new asset (e.g., "Add 10 shares of AAPL", "Create a bank account", "I bought 5 units of XYZ mutual fund")
2. DELETE an asset (e.g., "Remove my AAPL stock", "Delete the savings account", "Remove asset with ID abc123")
3. UPDATE an asset (e.g., "Update my AAPL quantity to 20", "Change the balance of my savings account to 5000")
4. NONE - if the message is just a question, not about asset management, OR if critical information is missing

CRITICAL RULES - EXTRACT INFORMATION THAT IS PRESENT:
- EXTRACT all information that is explicitly mentioned in the user's message OR in the conversation history above. Do not ask for information that is already provided in ANY part of the conversation.
- Look through the ENTIRE conversation history to find all relevant information before asking for missing details.
- If information was mentioned in a previous message, use it - don't ask for it again.
- For stock names like "Reliance", "TCS", "Infosys", "HDFC", "ICICI", "SBI" - these are Indian companies, so market should be "india". Extract the stock name as stock_symbol (e.g., "RELIANCE" for "Reliance", "TCS" for "TCS").
- For US stocks like "AAPL", "GOOGL", "MSFT" - these are US companies. Since we only support India and Europe markets, if the user mentions these, ask which market they want (India or Europe), or infer from currency if mentioned.
- Convert dates from any format (DD.MM.YYYY, DD-MM-YYYY, etc.) to YYYY-MM-DD format. For example, "24.11.2025" becomes "2025-11-24", "24-11-2025" becomes "2025-11-24".
- If the user mentions "rupees" or "₹" or "INR", the market is "india". If they mention "euros" or "€" or "EUR", the market is "europe".
- Extract quantities from phrases like "100 shares" or "100 stocks" or "100" → quantity: 100
- Extract prices from phrases like "at 1550" or "for 1500 rupees" or "costs 1550" → purchase_price: 1550 or 1500
- Extract stock symbols from stock names: "Reliance" → "RELIANCE", "TCS" → "TCS", "Infosys" → "INFY"
- Only set action to "none" if CRITICAL information is missing and cannot be extracted or inferred from the message.
- IMPORTANT: Add assets with whatever information is available. Use default values for missing optional fields:
  * If purchase_date is missing, use today's date (YYYY-MM-DD format)
  * If family_member_name is missing for stocks/bank accounts, use "self"
  * If market is missing, infer from stock name (Indian stocks → "india", others → ask)
- DO NOT put assumptions in the "notes" field. 
- For CSV file uploads: Process each row and add assets with available data. You can add multiple assets in one request.
- For DELETE and UPDATE operations, you MUST provide the asset_id from the portfolio data. If you cannot find a matching asset, set action to "none" and ask the user to clarify which asset they mean.

For ADD operations, EXTRACT all information from the ENTIRE conversation history (all messages above), not just the current message.

SPECIAL HANDLING FOR CSV FILE UPLOADS:
- If the user has uploaded a CSV file, the user message will contain ALL rows from the CSV file
- You MUST process EVERY row in the CSV file
- Each row represents a separate asset that needs to be added
- Extract asset information from each row individually
- CRITICAL: For CSV files with multiple rows, you MUST return an array of assets in the "assets" field
- If multiple assets are present in the CSV, return them ALL in the "assets" array
- If a row is missing critical required information (stock_symbol, quantity, purchase_price), skip that row but process all other rows

REQUIRED VS OPTIONAL FIELDS BY ASSET TYPE:
- Stock:
  * REQUIRED: stock_symbol, quantity, purchase_price, market
  * OPTIONAL (use defaults if missing): asset_name (can be derived from stock_symbol), purchase_date (default to today's date), family_member_name (default to "self")
- Mutual Fund: asset_name, mutual_fund_code, units, market (all required)
- Bank Account:
  * REQUIRED: bank_name, account_number, account_type, current_value, market
  * OPTIONAL: family_member_name (default to "self"), asset_name (defaults to bank_name)
- Fixed Deposit: asset_name, principal_amount, fd_interest_rate, start_date, maturity_date, market (all required)
- Insurance Policy: asset_name, policy_number, amount_insured, issue_date, date_of_maturity, premium, market (all required)
- Commodity: asset_name, commodity_name, form, commodity_quantity, commodity_units, commodity_purchase_date, commodity_purchase_price, market (all required)

IMPORTANT FOR STOCKS AND BANK ACCOUNTS:
- family_member_name is REQUIRED for both stocks and bank accounts. It must be the name of a family member from the portfolio, or "self" if the asset belongs to the user.
- If the user mentions a family member name that is not in the portfolio, you should still extract it, but note that it needs to be added in the Profile.
- Extract family member names from phrases like "for my brother", "for John", "for my father", "for self", "for me", "my account", "my bank account", etc.
- CRITICAL: If the user says "I", "self", "me", "myself", "I purchased", "I bought", "my stock", "my account", "my bank account", "owner is self", "account owner is self", "stock owner is self", "stock owner is me", or any variation indicating the asset belongs to the user, you MUST set family_member_name to "self". Do NOT leave it empty or undefined.

IMPORTANT FOR BANK ACCOUNTS:
- Extract bank name from phrases like "HDFC bank", "SBI account", "ICICI savings", etc.
- Extract account number if mentioned (e.g., "account number 1234567890", "acc no 1234")
- Extract account type from phrases like "savings account", "checking account", "current account", or infer from context
- Extract current balance from phrases like "balance of 50000", "has 10000 rupees", "with 5000 euros", etc.
- If balance is mentioned in rupees/INR, market is "india". If mentioned in euros/EUR, market is "europe".

EXTRACTION RULES (APPLY TO ALL MESSAGES IN CONVERSATION HISTORY):
- Extract stock names from ANY message in the conversation (e.g., "Reliance" → stock_symbol: "RELIANCE", asset_name: "Reliance Industries")
- Extract quantities from ANY message (e.g., "100 shares" → quantity: 100)
- Extract prices from ANY message (e.g., "at 1550" or "for 1500 rupees" → purchase_price: 1550 or 1500)
- Extract dates from ANY message and convert to YYYY-MM-DD format (e.g., "24.11.2025" → "2025-11-24", "24-12-2025" → "2025-12-24")
- Extract family member names from ANY message (e.g., "for my brother", "Natesh purchased", "for John", "my account", "my bank account" → family_member_name)
- CRITICAL for family_member_name: If ANY message contains "I", "self", "me", "myself", "I purchased", "I bought", "my account", "my bank account", "owner is self", "account owner is self", "stock owner is self", "stock owner is me", or similar phrases indicating the user owns the asset, you MUST set family_member_name to "self". This is a REQUIRED field for stocks and bank accounts - do not leave it empty.
- Extract bank account information from ANY message: bank name, account number, account type, balance
- Infer market from ANY message in the conversation:
  * Indian stock names (Reliance, TCS, Infosys, HDFC, ICICI, SBI, etc.) → market: "india"
  * Mentions of "rupees", "₹", "INR", "Indian market" → market: "india"
  * Mentions of "euros", "€", "EUR", "European market" → market: "europe"
  * If truly ambiguous across ALL messages, ask the user

IMPORTANT:
- Market must be either "india" or "europe" (not currency codes like INR, EUR, USD)
- Convert dates from any format (DD.MM.YYYY, DD-MM-YYYY, etc.) to YYYY-MM-DD format
- Only set action to "none" if information is TRULY missing and cannot be extracted or inferred from context

=== CURRENT USER MESSAGE (LATEST) - THIS IS THE MAIN DATA SOURCE ===
{user_message}
=== END OF CURRENT USER MESSAGE ===

CRITICAL: The current user message above contains the complete data (especially for CSV file uploads which include all rows).
Extract ALL information from the current user message. 
If there is conversation history above, also check those messages for any additional context.
Remember: Extract information from ALL messages in the conversation history above AND especially from the current user message!

CRITICAL: You MUST respond with ONLY a valid JSON object. No markdown, no code blocks, no explanations - just the raw JSON.

If all information is present, return:
- For a single asset OR CSV files with multiple assets:
{{
  "action": "add",
  "assets": [
    {{
      "asset_type": "stock",
      "asset_name": "...",
      "stock_symbol": "...",
      "quantity": 100,
      "purchase_price": 1550,
      "purchase_date": "2025-11-24",
      "market": "india",
      "family_member_name": "self"
    }},
    {{
      "asset_type": "stock",
      "asset_name": "...",
      "stock_symbol": "...",
      "quantity": 50,
      "purchase_price": 2000,
      "purchase_date": "2025-11-24",
      "market": "india",
      "family_member_name": "self"
    }}
  ]
}}

- For CSV files: The "assets" array MUST contain one asset object for EACH row in the CSV file that has the required fields (stock_symbol, quantity, purchase_price, market)
- If the user message contains CSV data with multiple rows, process ALL rows and return ALL assets in the "assets" array
- Each asset in the array should have all the fields for that specific row

If information is missing for ALL assets, return:
{{
  "action": "none",
  "message": "I need a few more details to add this asset: Please specify the market (India or Europe), the stock symbol (e.g., RELIANCE, AAPL), and the purchase date."
}}

CRITICAL: When action is "none" because information is missing:
- You MUST include a "message" field (NOT "notes") with a clear, user-friendly explanation
- The message should list exactly what information is needed
- Do NOT put the message in the "notes" field - use "message" field only

Respond with ONLY the JSON object."""

            # Use JSON mode instead of function calling for more reliable parsing
            # Configure to request JSON response
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",  # Request JSON response
                    response_schema=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "action": types.Schema(type=types.Type.STRING, enum=["add", "delete", "update", "none"]),
                            "asset_type": types.Schema(type=types.Type.STRING, enum=["stock", "mutual_fund", "bank_account", "fixed_deposit", "insurance_policy", "commodity"]),
                            "asset_id": types.Schema(type=types.Type.STRING),
                            "asset_name": types.Schema(type=types.Type.STRING),
                            "currency": types.Schema(type=types.Type.STRING, enum=["USD", "INR", "EUR"]),
                            "stock_symbol": types.Schema(type=types.Type.STRING),
                            "quantity": types.Schema(type=types.Type.NUMBER),
                            "purchase_price": types.Schema(type=types.Type.NUMBER),
                            "purchase_date": types.Schema(type=types.Type.STRING),
                            "mutual_fund_code": types.Schema(type=types.Type.STRING),
                            "units": types.Schema(type=types.Type.NUMBER),
                            "bank_name": types.Schema(type=types.Type.STRING),
                            "account_type": types.Schema(type=types.Type.STRING, enum=["savings", "checking", "current"]),
                            "current_value": types.Schema(type=types.Type.NUMBER),
                            "notes": types.Schema(type=types.Type.STRING),
                            "family_member_name": types.Schema(type=types.Type.STRING),
                            "market": types.Schema(type=types.Type.STRING, enum=["india", "europe"]),
                        }
                    )
                )
            except Exception as config_error:
                # Fallback to simple JSON mode if schema doesn't work
                config = types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            
            # Call Gemini
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            )
            
            # Extract JSON response (since we're using JSON mode)
            text_response = ""
            if hasattr(response, 'text') and response.text:
                text_response = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                    text_response = "".join(text_parts)
            
            
            # Parse JSON from response
            args = {}
            if text_response:
                try:
                    # Clean the response - remove markdown code blocks if present
                    cleaned_response = text_response.strip()
                    if cleaned_response.startswith('```json'):
                        cleaned_response = cleaned_response[7:]
                    if cleaned_response.startswith('```'):
                        cleaned_response = cleaned_response[3:]
                    if cleaned_response.endswith('```'):
                        cleaned_response = cleaned_response[:-3]
                    cleaned_response = cleaned_response.strip()
                    
                    # Try to parse as JSON
                    args = json.loads(cleaned_response)
                except json.JSONDecodeError as json_parse_error:
                    return {
                        "action": "none",
                        "response": "I encountered an error parsing your request. Please try rephrasing your asset management command."
                    }
                except Exception as parse_error:
                    import traceback
                    return {
                        "action": "none",
                        "response": "I encountered an error processing your request. Please try again."
                    }
            else:
                return {
                    "action": "none",
                    "response": "I didn't receive a valid response. Please try again."
                }
            
            action = args.get('action', 'none') if args else 'none'
            
            # Post-process to extract information that LLM might have missed
            # Only run post-processing if action is 'add' OR if user message contains asset-related keywords
            # This prevents false positives from greetings like "hi"
            user_lower = user_message.lower()
            asset_keywords = ['add', 'create', 'purchase', 'buy', 'stock', 'share', 'mutual fund', 'bank account', 'account', 'asset', 'portfolio', 'invest']
            has_asset_intent = any(keyword in user_lower for keyword in asset_keywords)
            
            # Only post-process if action is 'add' OR if user message suggests asset management intent
            if action == 'add' or (action == 'none' and has_asset_intent and args.get('asset_type')):
                args = self._extract_info_from_message(user_message, args, conversation_history, portfolio_data)
                # Only change action from 'none' to 'add' if:
                # 1. User message contains asset management intent
                # 2. We have asset_type
                # 3. We have at least some other required information (not just asset_type)
                if action == 'none' and has_asset_intent and args.get('asset_type'):
                    # Check if we have at least one other piece of information (name, quantity, price, etc.)
                    # Include fields for both stocks and bank accounts
                    has_additional_info = any(args.get(key) for key in ['asset_name', 'stock_symbol', 'quantity', 'purchase_price', 'purchase_date', 'market', 'bank_name', 'account_number', 'account_type', 'current_value', 'family_member_name'])
                    if has_additional_info:
                        action = 'add'  # Try to proceed if we have asset type AND some other info
                        args['action'] = 'add'
                    else:
                        # No additional info, keep action as 'none'
                        pass
            
            # Validate required fields if action is "add" - only block on truly critical fields
            if action == 'add':
                asset_type = args.get('asset_type')
                missing_critical_fields = []
                
                # Check for market (required for all asset types) - convert to currency later
                market = args.get('market')
                if not market:
                    missing_critical_fields.append('market (India or Europe)')
                elif market.lower() not in ['india', 'europe']:
                    missing_critical_fields.append('market (must be "India" or "Europe")')
                
                # Check critical fields by asset type (allow optional fields to be missing)
                if asset_type == 'stock':
                    if not args.get('stock_symbol'):
                        missing_critical_fields.append('stock symbol')
                    if not args.get('quantity'):
                        missing_critical_fields.append('quantity (number of shares)')
                    if not args.get('purchase_price'):
                        missing_critical_fields.append('purchase price')
                    
                    # Set defaults for optional fields
                    if not args.get('asset_name') and args.get('stock_symbol'):
                        args['asset_name'] = args.get('stock_symbol')  # Use symbol as name
                    if not args.get('purchase_date'):
                        from datetime import date
                        args['purchase_date'] = date.today().strftime('%Y-%m-%d')  # Default to today
                    if not args.get('family_member_name'):
                        args['family_member_name'] = 'self'  # Default to self
                elif asset_type == 'mutual_fund':
                    if not args.get('asset_name'):
                        missing_critical_fields.append('asset name')
                    if not args.get('mutual_fund_code'):
                        missing_critical_fields.append('mutual fund code')
                    if not args.get('units'):
                        missing_critical_fields.append('units')
                elif asset_type == 'bank_account':
                    if not args.get('bank_name'):
                        missing_critical_fields.append('bank name')
                    # Note: asset_name is optional - if not provided, bank_name will be used as account_name
                    # So we don't require asset_name if bank_name is present
                    if not args.get('account_number'):
                        missing_critical_fields.append('account number')
                    if not args.get('account_type'):
                        missing_critical_fields.append('account type (savings, checking, or current)')
                    if not args.get('current_value'):
                        missing_critical_fields.append('current balance (bank balance)')
                    # Set default for family_member_name if missing
                    if not args.get('family_member_name'):
                        args['family_member_name'] = 'self'  # Default to self
                
                if missing_critical_fields:
                    action = 'none'
                    args['action'] = 'none'
                    args['missing_fields'] = missing_critical_fields
                    args['message'] = f"I need more information to add this {asset_type} asset. Please provide: {', '.join(missing_critical_fields)}."
                else:
                    # Convert market to currency
                    if market:
                        market_lower = market.lower()
                        if market_lower == 'india':
                            args['currency'] = 'INR'
                        elif market_lower == 'europe':
                            args['currency'] = 'EUR'
            
            if action == 'none':
                # Check if there's a custom message from LLM about missing fields
                # LLM might put the message in "message", "notes", or "response" field
                missing_fields = args.get('missing_fields', [])
                custom_message = args.get('message') or args.get('notes') or args.get('response', '')
                
                
                # Clean up the message - remove any JSON formatting artifacts
                if custom_message:
                    # Remove any markdown code blocks if present
                    custom_message = custom_message.strip()
                    if custom_message.startswith('```'):
                        custom_message = custom_message.split('```')[1] if '```' in custom_message[3:] else custom_message[3:]
                    if custom_message.endswith('```'):
                        custom_message = custom_message[:-3]
                    custom_message = custom_message.strip()
                
                # Use custom message if it exists and seems to be asking for information
                # Check if it's a helpful message (not just empty or generic)
                if custom_message and len(custom_message) > 20:
                    # Check if it's asking for information (contains keywords or is from our validation)
                    is_helpful = (
                        'need' in custom_message.lower() or 
                        'missing' in custom_message.lower() or 
                        'provide' in custom_message.lower() or 
                        'specify' in custom_message.lower() or
                        'details' in custom_message.lower() or
                        'information' in custom_message.lower()
                    )
                    if is_helpful:
                        response_msg = custom_message
                    else:
                        # Use missing_fields message if available, otherwise use custom message
                        if missing_fields:
                            response_msg = f"I need more information to process your request. Please provide: {', '.join(missing_fields)}."
                        else:
                            response_msg = custom_message
                elif missing_fields:
                    response_msg = f"I need more information to process your request. Please provide: {', '.join(missing_fields)}."
                else:
                    response_msg = "I understand your message, but it doesn't appear to be a request to add, delete, or update an asset. How can I help you with your portfolio?"
                
                return {
                    "action": "none",
                    "response": response_msg
                }
            
            # Build response message
            if action == 'add':
                asset_type = args.get('asset_type', 'unknown')
                asset_name = args.get('asset_name', args.get('stock_symbol', 'New Asset'))
                response_msg = f"I've added a new {asset_type} asset: {asset_name} to your portfolio."
                needs_confirmation = False  # Don't need confirmation since we're adding with available data
            elif action == 'delete':
                asset_id = args.get('asset_id', '')
                response_msg = f"I'll delete the asset with ID: {asset_id}"
                needs_confirmation = True
            elif action == 'update':
                asset_id = args.get('asset_id', '')
                response_msg = f"I'll update the asset with ID: {asset_id}"
                needs_confirmation = True
            else:
                return {
                    "action": "none",
                    "response": "I couldn't determine what action you want to perform. Please be more specific."
                }
            
            return {
                "action": action,
                "asset_data": args,
                "asset_id": args.get('asset_id'),
                "response": response_msg,
                "needs_confirmation": needs_confirmation
            }
            
        except ImportError:
            return {
                "action": "none",
                "response": "google-genai package not installed. Please run: pip install google-genai"
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in asset LLM service: {str(e)}")
            print(f"Traceback: {error_details}")
            return {
                "action": "none",
                "response": f"I encountered an error processing your request: {str(e)}. Please try again or use the asset management UI."
            }


# Global instance
asset_llm_service = AssetLLMService()

