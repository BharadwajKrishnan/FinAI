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
    
    def _extract_info_from_message(self, user_message: str, args: Dict) -> Dict:
        """Post-process to extract information that LLM might have missed"""
        import re
        from datetime import datetime, date
        
        user_lower = user_message.lower()
        
        # Extract quantity if missing
        if not args.get('quantity'):
            # Try explicit numbers with shares/stocks
            quantity_match = re.search(r'(\d+)\s*(?:shares?|stocks?|units?)', user_lower)
            if quantity_match:
                args['quantity'] = int(quantity_match.group(1))
                print(f"DEBUG: Extracted quantity from message: {args['quantity']}")
            else:
                # Check for "a [name] stock" or "a stock" or "a share" (implies quantity = 1)
                # Pattern: "a" followed by optional words, then "stock" or "share"
                if re.search(r'\ba\s+[\w\s]*?(?:stock|share)', user_lower):
                    args['quantity'] = 1
                    print(f"DEBUG: Extracted quantity=1 from 'a [name] stock/share' pattern")
                # Check for standalone numbers that might be quantity (e.g., "100 Reliance")
                elif re.search(r'\b(\d+)\s+(?:reliance|tcs|infosys|hdfc|icici|sbi|wipro|apple|aapl|google|googl)', user_lower):
                    quantity_match = re.search(r'\b(\d+)\s+(?:reliance|tcs|infosys|hdfc|icici|sbi|wipro|apple|aapl|google|googl)', user_lower)
                    if quantity_match:
                        args['quantity'] = int(quantity_match.group(1))
                        print(f"DEBUG: Extracted quantity from message: {args['quantity']}")
                # Check for number at the start (e.g., "100 Reliance stock")
                elif re.search(r'^(\d+)\s+', user_message):
                    quantity_match = re.search(r'^(\d+)\s+', user_message)
                    if quantity_match:
                        args['quantity'] = int(quantity_match.group(1))
                        print(f"DEBUG: Extracted quantity from start of message: {args['quantity']}")
        
        # Extract price if missing
        if not args.get('purchase_price'):
            price_match = re.search(r'(?:at|for|costs?|@)\s*(\d+(?:\.\d+)?)', user_lower)
            if price_match:
                args['purchase_price'] = float(price_match.group(1))
                print(f"DEBUG: Extracted purchase_price from message: {args['purchase_price']}")
        
        # Extract date if missing
        if not args.get('purchase_date'):
            # Try DD.MM.YYYY format
            date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', user_message)
            if date_match:
                day, month, year = date_match.groups()
                try:
                    args['purchase_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    print(f"DEBUG: Extracted purchase_date from message: {args['purchase_date']}")
                except:
                    pass
            else:
                # Try DD-MM-YYYY format
                date_match = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', user_message)
                if date_match:
                    day, month, year = date_match.groups()
                    try:
                        args['purchase_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        print(f"DEBUG: Extracted purchase_date from message: {args['purchase_date']}")
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
                    print(f"DEBUG: Extracted stock_symbol and market from message: {symbol}, india")
                    break
        
        # Extract market from currency mentions if missing
        if not args.get('market'):
            if 'rupee' in user_lower or '₹' in user_message or 'inr' in user_lower:
                args['market'] = 'india'
                print(f"DEBUG: Extracted market from currency: india")
            elif 'euro' in user_lower or '€' in user_message or 'eur' in user_lower:
                args['market'] = 'europe'
                print(f"DEBUG: Extracted market from currency: europe")
        
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
                                print(f"DEBUG: Found incomplete request in history: {incomplete_request['original_message'][:100]}")
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
        """
        Process asset command using Gemini LLM
        """
        # Check if this is a follow-up to an incomplete request
        incomplete_request = self._extract_incomplete_request_from_history(conversation_history)
        if incomplete_request:
            # Combine the original message with the new message
            combined_message = f"{incomplete_request['original_message']}. {user_message}"
            print(f"DEBUG: Detected follow-up message. Combined message: {combined_message[:200]}")
            user_message = combined_message
        
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
                portfolio_context = f"""
Current Portfolio (Full Details):
```json
{portfolio_json}
```

Asset List (for ID matching):
```json
{asset_list_json}
```

When the user wants to delete or update an asset, you MUST find the matching asset ID from the Asset List above. Match assets by:
- Name (exact or partial match)
- Symbol (for stocks)
- Code (for mutual funds)
- Bank name and account number (for bank accounts)
- Policy number (for insurance)
- Commodity name (for commodities)

If you cannot find a matching asset, set action to "none" and explain that the asset was not found.
"""
            
            prompt = f"""You are a financial assistant that helps users manage their assets through natural language commands.

{portfolio_context}

Analyze the user's message and determine if they want to:
1. ADD a new asset (e.g., "Add 10 shares of AAPL", "Create a bank account", "I bought 5 units of XYZ mutual fund")
2. DELETE an asset (e.g., "Remove my AAPL stock", "Delete the savings account", "Remove asset with ID abc123")
3. UPDATE an asset (e.g., "Update my AAPL quantity to 20", "Change the balance of my savings account to 5000")
4. NONE - if the message is just a question, not about asset management, OR if critical information is missing

CRITICAL RULES - EXTRACT INFORMATION THAT IS PRESENT:
- EXTRACT all information that is explicitly mentioned in the user's message. Do not ask for information that is already provided.
- For stock names like "Reliance", "TCS", "Infosys", "HDFC", "ICICI", "SBI" - these are Indian companies, so market should be "india". Extract the stock name as stock_symbol (e.g., "RELIANCE" for "Reliance", "TCS" for "TCS").
- For US stocks like "AAPL", "GOOGL", "MSFT" - these are US companies. Since we only support India and Europe markets, if the user mentions these, ask which market they want (India or Europe), or infer from currency if mentioned.
- Convert dates from any format (DD.MM.YYYY, DD-MM-YYYY, etc.) to YYYY-MM-DD format. For example, "24.11.2025" becomes "2025-11-24", "24-11-2025" becomes "2025-11-24".
- If the user mentions "rupees" or "₹" or "INR", the market is "india". If they mention "euros" or "€" or "EUR", the market is "europe".
- Extract quantities from phrases like "100 shares" or "100 stocks" or "100" → quantity: 100
- Extract prices from phrases like "at 1550" or "for 1500 rupees" or "costs 1550" → purchase_price: 1550 or 1500
- Extract stock symbols from stock names: "Reliance" → "RELIANCE", "TCS" → "TCS", "Infosys" → "INFY"
- Only set action to "none" if information is TRULY missing and cannot be extracted or inferred from the message.
- DO NOT put assumptions in the "notes" field. If information is missing, set action to "none" instead of proceeding.
- DO NOT proceed with action "add" if ANY required field is missing. You MUST set action to "none" and ask for the missing information.
- For DELETE and UPDATE operations, you MUST provide the asset_id from the portfolio data. If you cannot find a matching asset, set action to "none" and ask the user to clarify which asset they mean.

For ADD operations, EXTRACT all information from the user's message:

REQUIRED FIELDS BY ASSET TYPE:
- Stock: asset_name, stock_symbol, quantity, purchase_price, purchase_date, market
- Mutual Fund: asset_name, mutual_fund_code, units, market
- Bank Account: asset_name, bank_name, account_type, current_value, market
- Fixed Deposit: asset_name, principal_amount, fd_interest_rate, start_date, maturity_date, market
- Insurance Policy: asset_name, policy_number, amount_insured, issue_date, date_of_maturity, premium, market
- Commodity: asset_name, commodity_name, form, commodity_quantity, commodity_units, commodity_purchase_date, commodity_purchase_price, market

EXTRACTION RULES:
- Extract stock names from the message (e.g., "Reliance" → stock_symbol: "RELIANCE", asset_name: "Reliance Industries")
- Extract quantities (e.g., "100 shares" → quantity: 100)
- Extract prices (e.g., "at 1550" or "for 1500 rupees" → purchase_price: 1550 or 1500)
- Extract dates and convert to YYYY-MM-DD format (e.g., "24.11.2025" → "2025-11-24", "24-11-2025" → "2025-11-24")
- Infer market from context:
  * Indian stock names (Reliance, TCS, Infosys, HDFC, ICICI, SBI, etc.) → market: "india"
  * Mentions of "rupees", "₹", "INR" → market: "india"
  * Mentions of "euros", "€", "EUR" → market: "europe"
  * If truly ambiguous, ask the user

IMPORTANT:
- Market must be either "india" or "europe" (not currency codes like INR, EUR, USD)
- Convert dates from any format (DD.MM.YYYY, DD-MM-YYYY, etc.) to YYYY-MM-DD format
- Only set action to "none" if information is TRULY missing and cannot be extracted or inferred from context

User message: {user_message}

CRITICAL: You MUST respond with ONLY a valid JSON object. No markdown, no code blocks, no explanations - just the raw JSON.

If all information is present, return:
{{
  "action": "add",
  "asset_type": "stock",
  "asset_name": "...",
  "stock_symbol": "...",
  "quantity": 100,
  "purchase_price": 1550,
  "purchase_date": "2025-11-24",
  "market": "india"
}}

If information is missing, return:
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
                        }
                    )
                )
            except Exception as config_error:
                # Fallback to simple JSON mode if schema doesn't work
                print(f"Warning: Could not set response schema, using simple JSON mode: {config_error}")
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
            
            print(f"DEBUG: LLM JSON response: {text_response[:500]}...")
            
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
                    print(f"DEBUG: Successfully parsed JSON: {args}")
                except json.JSONDecodeError as json_parse_error:
                    print(f"DEBUG: Could not parse JSON from response: {json_parse_error}")
                    print(f"DEBUG: Full response was: {text_response}")
                    return {
                        "action": "none",
                        "response": "I encountered an error parsing your request. Please try rephrasing your asset management command."
                    }
                except Exception as parse_error:
                    print(f"DEBUG: Error parsing JSON: {parse_error}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    return {
                        "action": "none",
                        "response": "I encountered an error processing your request. Please try again."
                    }
            else:
                print(f"DEBUG: No text response from LLM")
                return {
                    "action": "none",
                    "response": "I didn't receive a valid response. Please try again."
                }
            
            action = args.get('action', 'none') if args else 'none'
            print(f"DEBUG: Extracted action: {action}, args keys: {list(args.keys()) if args else 'None'}")
            
            # Post-process to extract information that LLM might have missed
            # Run post-processing if action is 'add' or if LLM returned 'none' but we have asset_type (might be extractable)
            if action == 'add' or (action == 'none' and args.get('asset_type')):
                args = self._extract_info_from_message(user_message, args)
                print(f"DEBUG: After post-processing, args keys: {list(args.keys())}")
                # If we extracted information and now have asset_type, try to proceed
                if action == 'none' and args.get('asset_type'):
                    action = 'add'  # Try to proceed if we have asset type
                    args['action'] = 'add'
                    print(f"DEBUG: Changed action from 'none' to 'add' after post-processing")
            
            # Validate required fields if action is "add" - if missing, change to "none"
            if action == 'add':
                asset_type = args.get('asset_type')
                missing_fields = []
                
                # Check for market (required for all asset types) - convert to currency later
                market = args.get('market')
                if not market:
                    missing_fields.append('market (India or Europe)')
                elif market.lower() not in ['india', 'europe']:
                    missing_fields.append('market (must be "India" or "Europe")')
                
                # Check required fields by asset type
                if asset_type == 'stock':
                    if not args.get('asset_name'):
                        missing_fields.append('asset name')
                    if not args.get('stock_symbol'):
                        missing_fields.append('stock symbol')
                    if not args.get('quantity'):
                        missing_fields.append('quantity (number of shares)')
                    if not args.get('purchase_price'):
                        missing_fields.append('purchase price')
                    if not args.get('purchase_date'):
                        missing_fields.append('purchase date')
                elif asset_type == 'mutual_fund':
                    if not args.get('asset_name'):
                        missing_fields.append('asset name')
                    if not args.get('mutual_fund_code'):
                        missing_fields.append('mutual fund code')
                    if not args.get('units'):
                        missing_fields.append('units')
                elif asset_type == 'bank_account':
                    if not args.get('asset_name'):
                        missing_fields.append('account name')
                    if not args.get('bank_name'):
                        missing_fields.append('bank name')
                    if not args.get('account_type'):
                        missing_fields.append('account type (savings, checking, or current)')
                    if not args.get('current_value'):
                        missing_fields.append('current balance')
                
                if missing_fields:
                    print(f"DEBUG: Missing required fields: {missing_fields}, changing action to 'none'")
                    action = 'none'
                    args['action'] = 'none'
                    args['missing_fields'] = missing_fields
                    args['message'] = f"I need more information to add this {asset_type} asset. Please provide: {', '.join(missing_fields)}."
                else:
                    # Convert market to currency
                    if market:
                        market_lower = market.lower()
                        if market_lower == 'india':
                            args['currency'] = 'INR'
                        elif market_lower == 'europe':
                            args['currency'] = 'EUR'
                        print(f"DEBUG: Converted market '{market}' to currency '{args.get('currency')}'")
            
            if action == 'none':
                # Check if there's a custom message from LLM about missing fields
                # LLM might put the message in "message", "notes", or "response" field
                missing_fields = args.get('missing_fields', [])
                custom_message = args.get('message') or args.get('notes') or args.get('response', '')
                
                print(f"DEBUG: action='none', custom_message from LLM: {custom_message[:200] if custom_message else 'None'}")
                print(f"DEBUG: missing_fields: {missing_fields}")
                
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
                        print(f"DEBUG: Using custom message from LLM: {response_msg[:100]}...")
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
                
                print(f"DEBUG: Final response message: {response_msg[:100]}...")
                return {
                    "action": "none",
                    "response": response_msg
                }
            
            # Build response message
            if action == 'add':
                asset_type = args.get('asset_type', 'unknown')
                asset_name = args.get('asset_name', 'New Asset')
                response_msg = f"I'll add a new {asset_type} asset: {asset_name}"
                needs_confirmation = True
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

