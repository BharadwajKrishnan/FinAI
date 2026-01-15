"""
Stock Price Service - Fetches real-time stock prices and searches stocks
"""

import asyncio
import aiohttp
from typing import Dict, Optional, List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class StockPriceService:
    """Service to fetch stock prices from various APIs"""
    
    def __init__(self):
        # You can add API keys here if needed
        self.alpha_vantage_api_key = None  # Set via environment variable if using Alpha Vantage
    
    async def get_stock_price(self, symbol: str, market: str = "US") -> Optional[Decimal]:
        """
        Get current stock price for a given symbol
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "RELIANCE.NS")
            market: Market region ("US", "IN", "EU")
        
        Returns:
            Current price as Decimal, or None if not found
        """
        try:
            if market == "IN":
                # For Indian stocks, use NSE format (symbol.NS) or BSE format (symbol.BO)
                # Try NSE first
                price = await self._fetch_yahoo_price(f"{symbol}.NS")
                if price is None:
                    # Try BSE
                    price = await self._fetch_yahoo_price(f"{symbol}.BO")
                return price
            elif market == "EU":
                # For European stocks, try different exchanges (same approach as Indian stocks)
                # Format: SYMBOL.EX (e.g., ASML.AS for Amsterdam, SAP.DE for Frankfurt)
                # Try common European exchanges
                for ext in ["L", "PA", "DE", "AS", "MI"]:  # London, Paris, Frankfurt, Amsterdam, Milan
                    price = await self._fetch_yahoo_price(f"{symbol}.{ext}")
                    if price:
                        break
                return price
            else:
                # US market (default)
                return await self._fetch_yahoo_price(symbol)
        except Exception as e:
            logger.error(f"Error fetching stock price for {symbol}: {str(e)}")
            return None
    
    async def _fetch_yahoo_price(self, symbol: str) -> Optional[Decimal]:
        """
        Fetch stock price from Yahoo Finance (free, no API key required)
        Uses yfinance library or direct API call
        """
        try:
            # Using yfinance library (install: pip install yfinance)
            import yfinance as yf
            
            # Create ticker object
            ticker = yf.Ticker(symbol)
            
            # Get current price
            info = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if current_price:
                return Decimal(str(current_price))
            
            # Fallback: try to get last close price
            hist = ticker.history(period="1d")
            if not hist.empty:
                return Decimal(str(hist['Close'].iloc[-1]))
            
            return None
        except ImportError:
            # If yfinance is not installed, use alternative method
            logger.warning("yfinance not installed, using alternative method")
            return await self._fetch_yahoo_api(symbol)
        except Exception as e:
            logger.error(f"Error fetching from Yahoo Finance for {symbol}: {str(e)}")
            return None
    
    async def _fetch_yahoo_api(self, symbol: str) -> Optional[Decimal]:
        """
        Alternative method: Direct API call to Yahoo Finance
        (Less reliable, but doesn't require yfinance)
        """
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'result' in data and len(data['result']) > 0:
                            result = data['result'][0]
                            if 'meta' in result and 'regularMarketPrice' in result['meta']:
                                price = result['meta']['regularMarketPrice']
                                return Decimal(str(price))
            return None
        except Exception as e:
            logger.error(f"Error fetching from Yahoo API for {symbol}: {str(e)}")
            return None
    
    async def get_multiple_prices(self, symbols: list[str], market: str = "US") -> Dict[str, Optional[Decimal]]:
        """
        Fetch prices for multiple symbols concurrently
        
        Args:
            symbols: List of stock symbols
            market: Market region
        
        Returns:
            Dictionary mapping symbol to price
        """
        tasks = [self.get_stock_price(symbol, market=market) for symbol in symbols]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for symbol, price in zip(symbols, prices):
            if isinstance(price, Exception):
                logger.error(f"Error fetching price for {symbol}: {price}")
                result[symbol] = None
            else:
                result[symbol] = price
        
        return result
    
    async def search_stocks(self, query: str, market: str = "US", limit: int = 20) -> List[Dict]:
        """
        Search for stocks by name or symbol using Finnhub API
        
        Args:
            query: Search query (stock name or symbol)
            market: Market region ("US", "IN", "EU")
            limit: Maximum number of results
        
        Returns:
            List of stock dictionaries with name, symbol, exchange info
        """
        try:
            import os
            finnhub_api_key = os.getenv("FINNHUB_API_KEY")
            
            if not finnhub_api_key:
                logger.warning("FINNHUB_API_KEY not set, falling back to predefined list")
                return await self._search_from_predefined_list(query, market, limit)
            
            # Use Finnhub search API
            results = await self._search_finnhub(query, market, finnhub_api_key, limit)
            
            if results:
                return results
            else:
                # Fallback to predefined list if no results
                logger.debug("No results from Finnhub, using fallback")
                return await self._search_from_predefined_list(query, market, limit)
                
        except Exception as e:
            logger.error(f"Error searching stocks: {str(e)}")
            # Fallback to predefined list on error
            return await self._search_from_predefined_list(query, market, limit)
    
    async def _search_finnhub(self, query: str, market: str, api_key: str, limit: int) -> List[Dict]:
        """
        Search stocks using Finnhub API
        Documentation: https://finnhub.io/docs/api/stock-symbols
        """
        try:
            # Finnhub search endpoint
            url = f"https://finnhub.io/api/v1/search?q={query}&token={api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        # Finnhub returns results in 'result' field
                        if 'result' in data and isinstance(data['result'], list):
                            logger.debug(f"Finnhub returned {len(data['result'])} results for query '{query}'")
                            
                            for item in data['result'][:limit * 3]:  # Get more to filter
                                symbol = item.get('symbol', '')
                                description = item.get('description', '')
                                display_symbol = item.get('displaySymbol', symbol)
                                
                                # Determine exchange and market from symbol/description
                                exchange = item.get('mic', '') or item.get('exchange', '') or item.get('type', '')
                                
                                # Filter by market - be more lenient with matching
                                # If we can't determine market, include it anyway (better to show results than none)
                                is_match = False
                                has_foreign_suffix = any(ext in symbol.upper() for ext in ['.NS', '.BO', '.L', '.PA', '.DE', '.AS', '.MI', '.BR', '.ST', '.OL', '.VI', '.LS'])
                                
                                if market == "IN":
                                    # Indian stocks: NSE or BSE
                                    is_match = (
                                        'NSE' in exchange.upper() or 
                                        'BSE' in exchange.upper() or 
                                        '.NS' in symbol.upper() or 
                                        '.BO' in symbol.upper() or
                                        'INDIA' in exchange.upper() or
                                        'BOMBAY' in exchange.upper() or
                                        'NATIONAL STOCK EXCHANGE' in exchange.upper()
                                    )
                                elif market == "EU":
                                    # European stocks: LSE, XETR, XPAR, XMIL, XAMS, etc.
                                    eu_exchanges = ['LSE', 'XETR', 'XPAR', 'XMIL', 'XAMS', 'XBRU', 'XSTO', 'XOSL', 'LONDON', 'FRANKFURT', 'PARIS', 'MILAN', 'AMSTERDAM', 'EURONEXT']
                                    eu_suffixes = ['.L', '.PA', '.DE', '.AS', '.MI', '.BR', '.ST', '.OL', '.VI', '.LS']
                                    is_match = (
                                        any(ex.upper() in exchange.upper() for ex in eu_exchanges) or 
                                        any(ext.upper() in symbol.upper() for ext in eu_suffixes)
                                    )
                                else:  # US
                                    # US stocks: NASDAQ, NYSE, etc.
                                    us_exchanges = ['NASDAQ', 'NYSE', 'AMEX', 'OTC', 'BATS', 'IEX', 'NEW YORK']
                                    # US stocks typically don't have suffixes like .NS, .L, etc.
                                    is_match = (
                                        any(ex.upper() in exchange.upper() for ex in us_exchanges) or 
                                        (not has_foreign_suffix and symbol and len(symbol) <= 6)  # Most US symbols are short
                                    )
                                
                                # If no clear match but we have results, include first few anyway (for better UX)
                                # This helps when exchange info is missing or unclear
                                if not is_match and len(results) == 0 and market == "US" and not has_foreign_suffix:
                                    is_match = True  # Include first result if no matches yet
                                
                                if is_match and symbol and description:
                                    results.append({
                                        'symbol': symbol,
                                        'name': description,
                                        'exchange': exchange or display_symbol or 'Unknown',
                                        'market': market
                                    })
                                
                                if len(results) >= limit:
                                    break
                            
                            logger.debug(f"Filtered to {len(results)} results for market '{market}'")
                        else:
                            logger.warning(f"Unexpected Finnhub response format: {data}")
                        
                        return results
                    elif response.status == 429:
                        logger.warning("Finnhub API rate limit exceeded")
                        return []
                    else:
                        error_text = await response.text()
                        logger.warning(f"Finnhub API returned status {response.status}: {error_text}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling Finnhub API: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error calling Finnhub API: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _search_us_stocks(self, query: str, limit: int) -> List[Dict]:
        """Search US stocks using yfinance"""
        try:
            import yfinance as yf
            
            # Use yfinance's search functionality
            # Note: yfinance doesn't have a direct search, so we'll use a workaround
            # For production, consider using a dedicated stock search API
            
            # Try to get info for the symbol directly
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            
            if info and 'symbol' in info and info.get('symbol'):
                return [{
                    'symbol': info['symbol'],
                    'name': info.get('longName', info.get('shortName', query)),
                    'exchange': info.get('exchange', 'NASDAQ'),
                    'market': 'US'
                }]
        except Exception as e:
            logger.debug(f"Error searching US stocks: {str(e)}")
        
        # Fallback: Use a predefined list of popular stocks for autocomplete
        # In production, use a proper stock search API like Alpha Vantage, IEX Cloud, or Finnhub
        return await self._search_from_predefined_list(query, 'US', limit)
    
    async def _search_nse_stocks(self, query: str, limit: int) -> List[Dict]:
        """Search NSE (National Stock Exchange of India) stocks"""
        try:
            import yfinance as yf
            
            # NSE stocks typically end with .NS
            # Try searching with .NS suffix
            symbol = query.upper().replace('.NS', '') + '.NS'
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if info and 'symbol' in info:
                return [{
                    'symbol': info['symbol'],
                    'name': info.get('longName', info.get('shortName', query)),
                    'exchange': 'NSE',
                    'market': 'IN'
                }]
        except Exception as e:
            logger.debug(f"Error searching NSE stocks: {str(e)}")
        
        return await self._search_from_predefined_list(query, 'IN', limit)
    
    async def _search_bse_stocks(self, query: str, limit: int) -> List[Dict]:
        """Search BSE (Bombay Stock Exchange) stocks"""
        try:
            import yfinance as yf
            
            # BSE stocks typically end with .BO
            symbol = query.upper().replace('.BO', '') + '.BO'
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if info and 'symbol' in info:
                return [{
                    'symbol': info['symbol'],
                    'name': info.get('longName', info.get('shortName', query)),
                    'exchange': 'BSE',
                    'market': 'IN'
                }]
        except Exception as e:
            logger.debug(f"Error searching BSE stocks: {str(e)}")
        
        return []
    
    async def _search_european_stocks(self, query: str, limit: int) -> List[Dict]:
        """Search European stocks"""
        # European exchanges: .L (London), .PA (Paris), .DE (Frankfurt), .AS (Amsterdam), .MI (Milan)
        exchanges = [
            ('L', 'LSE'), ('PA', 'Euronext Paris'), ('DE', 'XETRA'), 
            ('AS', 'Euronext Amsterdam'), ('MI', 'Borsa Italiana')
        ]
        
        results = []
        for ext, exchange_name in exchanges:
            try:
                import yfinance as yf
                symbol = query.upper().replace(f'.{ext}', '') + f'.{ext}'
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                if info and 'symbol' in info:
                    results.append({
                        'symbol': info['symbol'],
                        'name': info.get('longName', info.get('shortName', query)),
                        'exchange': exchange_name,
                        'market': 'EU'
                    })
                    if len(results) >= limit:
                        break
            except:
                continue
        
        return results
    
    async def _search_from_predefined_list(self, query: str, market: str, limit: int) -> List[Dict]:
        """Search from a predefined list of popular stocks (fallback)"""
        query_lower = query.lower()
        results = []
        
        # Popular stocks by market
        if market == 'US':
            popular_stocks = [
                {'symbol': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ'},
                {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ'},
                {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ'},
                {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ'},
                {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ'},
                {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ'},
                {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ'},
                {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'exchange': 'NYSE'},
                {'symbol': 'V', 'name': 'Visa Inc.', 'exchange': 'NYSE'},
                {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE'},
            ]
        elif market == 'IN':
            popular_stocks = [
                {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries Ltd', 'exchange': 'NSE'},
                {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services Ltd', 'exchange': 'NSE'},
                {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank Ltd', 'exchange': 'NSE'},
                {'symbol': 'INFY.NS', 'name': 'Infosys Ltd', 'exchange': 'NSE'},
                {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank Ltd', 'exchange': 'NSE'},
                {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever Ltd', 'exchange': 'NSE'},
                {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'exchange': 'NSE'},
                {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel Ltd', 'exchange': 'NSE'},
                {'symbol': 'ITC.NS', 'name': 'ITC Ltd', 'exchange': 'NSE'},
                {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank Ltd', 'exchange': 'NSE'},
            ]
        else:  # EU
            popular_stocks = [
                {'symbol': 'ASML.AS', 'name': 'ASML Holding N.V.', 'exchange': 'Euronext Amsterdam'},
                {'symbol': 'SAP.DE', 'name': 'SAP SE', 'exchange': 'XETRA'},
                {'symbol': 'SHEL.L', 'name': 'Shell plc', 'exchange': 'LSE'},
                {'symbol': 'HSBA.L', 'name': 'HSBC Holdings plc', 'exchange': 'LSE'},
                {'symbol': 'SAN.PA', 'name': 'Sanofi', 'exchange': 'Euronext Paris'},
                {'symbol': 'OR.PA', 'name': "L'Oréal S.A.", 'exchange': 'Euronext Paris'},
                {'symbol': 'ENEL.MI', 'name': 'Enel S.p.A.', 'exchange': 'Borsa Italiana'},
                {'symbol': 'INGA.AS', 'name': 'ING Groep N.V.', 'exchange': 'Euronext Amsterdam'},
            ]
        
        for stock in popular_stocks:
            if query_lower in stock['name'].lower() or query_lower in stock['symbol'].lower():
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'exchange': stock['exchange'],
                    'market': market
                })
                if len(results) >= limit:
                    break
        
        return results


# Singleton instance
stock_price_service = StockPriceService()

