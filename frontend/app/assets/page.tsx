"use client";

import { useState, useEffect } from "react";
import ResizablePanel from "@/components/ResizablePanel";
import ChatWindow from "@/components/ChatWindow";

type Market = "india" | "europe";

const marketConfig = {
  india: {
    name: "India",
    currency: "INR",
    symbol: "₹",
  },
  europe: {
    name: "Europe",
    currency: "EUR",
    symbol: "€",
  },
};

type AssetType = "stock" | "bank_account" | "mutual_fund" | "fixed_deposit";

const assetTypeOptions = [
  { value: "stock", label: "Stock" },
  { value: "bank_account", label: "Bank Account" },
  { value: "mutual_fund", label: "Mutual Funds" },
  { value: "fixed_deposit", label: "Fixed Deposits" },
];

type ActiveTab = "stocks" | "bank_accounts" | "mutual_funds" | "fixed_deposits";

const tabConfig = [
  { id: "stocks" as ActiveTab, label: "Stocks" },
  { id: "bank_accounts" as ActiveTab, label: "Bank Accounts" },
  { id: "mutual_funds" as ActiveTab, label: "Mutual Funds" },
  { id: "fixed_deposits" as ActiveTab, label: "Fixed Deposits" },
];

// Helper function to format date as DD/MM/YYYY
const formatDateDDMMYYYY = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  } catch (error) {
    // If date parsing fails, try to parse YYYY-MM-DD format directly
    const parts = dateString.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return dateString; // Return as-is if parsing fails
  }
};

export default function AssetsPage() {
  const [selectedMarket, setSelectedMarket] = useState<Market>("india");
  const [isAddAssetModalOpen, setIsAddAssetModalOpen] = useState(false);
  const [selectedAssetType, setSelectedAssetType] = useState<AssetType | "">("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("stocks");
  const [editingStockId, setEditingStockId] = useState<string | null>(null);
  const [editingBankAccountId, setEditingBankAccountId] = useState<string | null>(null);
  const [editingMutualFundId, setEditingMutualFundId] = useState<string | null>(null);
  const [editingFixedDepositId, setEditingFixedDepositId] = useState<string | null>(null);
  
  // Separate net worth for each market
  const [netWorth, setNetWorth] = useState<Record<Market, number>>({
    india: 0,
    europe: 0,
  });
  
  // Store stocks by market
  const [stocks, setStocks] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    name: string;
    symbol?: string; // Stock symbol for price fetching
    price: number; // Average purchase price
    quantity: number;
    totalInvested: number; // Total amount invested
    actualWorth: number; // Current market value (for now same as invested, will be updated with real-time prices)
    purchaseDate?: string; // Purchase date
  }>>>({
    india: [],
    europe: [],
  });
  
  // Store bank accounts by market
  const [bankAccounts, setBankAccounts] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    bankName: string;
    accountNumber?: string;
    balance: number;
  }>>>({
    india: [],
    europe: [],
  });
  
  // Store mutual funds by market
  const [mutualFunds, setMutualFunds] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    fundName: string;
    nav: number; // Net Asset Value
    units: number; // Number of units purchased
    totalInvested: number; // NAV * Units
    currentWorth: number; // Current NAV * Units (for now same as invested, can be updated later)
    purchaseDate?: string; // Purchase date
  }>>>({
    india: [],
    europe: [],
  });
  
  // Store fixed deposits by market
  const [fixedDeposits, setFixedDeposits] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    bankName: string;
    amountInvested: number; // Principal amount
    rateOfInterest: number; // Annual interest rate in percentage
    duration: number; // Duration in months
    maturityAmount: number; // Calculated amount at maturity
    startDate: string; // Start date of FD
    maturityDate: string; // Calculated maturity date
  }>>>({
    india: [],
    europe: [],
  });
  
  const [isLoadingAssets, setIsLoadingAssets] = useState(true);
  
  // Stock-specific fields
  const [stockName, setStockName] = useState("");
  const [stockSymbol, setStockSymbol] = useState(""); // Store the actual stock symbol
  const [stockPrice, setStockPrice] = useState("");
  const [stockQuantity, setStockQuantity] = useState("");
  const [stockPurchaseDate, setStockPurchaseDate] = useState(new Date().toISOString().split('T')[0]); // Purchase date
  
  // Bank Account-specific fields
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [bankBalance, setBankBalance] = useState("");
  
  // Mutual Fund-specific fields
  const [fundName, setFundName] = useState("");
  const [nav, setNav] = useState("");
  const [units, setUnits] = useState("");
  const [mutualFundPurchaseDate, setMutualFundPurchaseDate] = useState(new Date().toISOString().split('T')[0]); // Purchase date
  const [stockCurrentWorth, setStockCurrentWorth] = useState(""); // For editing stock current value
  const [mutualFundCurrentWorth, setMutualFundCurrentWorth] = useState(""); // For editing mutual fund current value
  
  // Fixed Deposit-specific fields
  const [fdBankName, setFdBankName] = useState("");
  const [fdAmount, setFdAmount] = useState("");
  const [fdRate, setFdRate] = useState("");
  const [fdDuration, setFdDuration] = useState(""); // Duration in months
  const [fdStartDate, setFdStartDate] = useState(new Date().toISOString().split('T')[0]); // Start date
  
  const currentMarket = marketConfig[selectedMarket];
  const currentNetWorth = netWorth[selectedMarket];
  
  // Calculate total amount invested for stocks
  const calculateStockTotal = () => {
    const price = parseFloat(stockPrice) || 0;
    const quantity = parseFloat(stockQuantity) || 0;
    return price * quantity;
  };
  
  // Calculate maturity amount for fixed deposit (compound interest)
  // Fixed deposits compound annually
  const calculateMaturityAmount = (principal: number, rate: number, durationMonths: number): number => {
    if (principal <= 0 || rate <= 0 || durationMonths <= 0) {
      return 0;
    }
    // Convert annual rate to decimal (divide by 100)
    const annualRate = rate / 100;
    // Calculate number of years
    const years = durationMonths / 12;
    // Calculate compound interest: A = P(1 + r)^n
    // For annual compounding: A = P(1 + annualRate)^years
    const maturityAmount = principal * Math.pow(1 + annualRate, years);
    return maturityAmount;
  };
  
  // Recalculate net worth from all assets for a given market
  const recalculateNetWorth = (market: Market) => {
    const marketStocks = stocks[market];
    const marketBankAccounts = bankAccounts[market];
    const marketMutualFunds = mutualFunds[market];
    const marketFixedDeposits = fixedDeposits[market];
    
    // Use actualWorth (current market value) for stocks, not totalInvested
    const stocksTotal = marketStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
    const bankAccountsTotal = marketBankAccounts.reduce((sum, account) => sum + account.balance, 0);
    const mutualFundsTotal = marketMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
    // For fixed deposits, use amount invested (not maturity amount) - this is an exception
    const fixedDepositsTotal = marketFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
    
    return stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
  };
  
  // Calculate total amount invested for mutual funds
  const calculateMutualFundTotal = () => {
    const navValue = parseFloat(nav) || 0;
    const unitsValue = parseFloat(units) || 0;
    return navValue * unitsValue;
  };
  
  const mutualFundTotal = calculateMutualFundTotal();
  
  const stockTotal = calculateStockTotal();
  
  // Fetch assets from database on component mount
  useEffect(() => {
    const fetchAssets = async () => {
      try {
        const accessToken = localStorage.getItem("access_token");
        if (!accessToken) {
          console.warn("No access token found, redirecting to login");
          setIsLoadingAssets(false);
          window.location.href = "/";
          return;
        }

        // Fetch all assets
        const response = await fetch("/api/assets", {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (response.ok) {
          const assets = await response.json();
          console.log(`Fetched ${assets.length} assets from database`);
          if (assets.length > 0) {
            console.log("Sample asset:", assets[0]);
          }
          
          // Separate assets by market (based on currency)
          const indiaStocks: typeof stocks.india = [];
          const europeStocks: typeof stocks.europe = [];
          const indiaBankAccounts: typeof bankAccounts.india = [];
          const europeBankAccounts: typeof bankAccounts.europe = [];
          const indiaMutualFunds: typeof mutualFunds.india = [];
          const europeMutualFunds: typeof mutualFunds.europe = [];
          const indiaFixedDeposits: typeof fixedDeposits.india = [];
          const europeFixedDeposits: typeof fixedDeposits.europe = [];
          
          assets.forEach((asset: any) => {
            const currency = asset.currency || "USD";
            const market: Market = currency === "INR" ? "india" : "europe";
            
            if (asset.type === "stock") {
              // Use current_price if available, otherwise use purchase_price
              const purchasePrice = parseFloat(asset.purchase_price || "0");
              const currentPrice = parseFloat(asset.current_price || purchasePrice || "0");
              const quantity = parseFloat(asset.quantity || "0");
              const totalInvested = purchasePrice * quantity;
              const actualWorth = currentPrice * quantity; // Current market value
              
              const stock = {
                id: asset.id,
                dbId: asset.id,
                name: asset.name,
                symbol: asset.stock_symbol, // Store the symbol
                price: purchasePrice, // Average purchase price
                quantity: quantity,
                totalInvested: totalInvested,
                actualWorth: actualWorth, // Current market value
                purchaseDate: asset.purchase_date || new Date().toISOString().split('T')[0],
              };
              
              if (market === "india") {
                indiaStocks.push(stock);
              } else {
                europeStocks.push(stock);
              }
            } else if (asset.type === "bank_account") {
              const bankAccount = {
                id: asset.id,
                dbId: asset.id,
                bankName: asset.bank_name || asset.name,
                accountNumber: asset.account_number,
                balance: parseFloat(asset.current_value || "0"),
              };
              
              if (market === "india") {
                indiaBankAccounts.push(bankAccount);
              } else {
                europeBankAccounts.push(bankAccount);
              }
            } else if (asset.type === "mutual_fund") {
              const navValue = parseFloat(asset.nav || "0");
              const unitsValue = parseFloat(asset.units || "0");
              const totalInvested = navValue * unitsValue;
              const currentWorth = navValue * unitsValue; // For now, same as invested (can update with current NAV later)
              
              const mutualFund = {
                id: asset.id,
                dbId: asset.id,
                fundName: asset.name,
                nav: navValue,
                units: unitsValue,
                totalInvested: totalInvested,
                currentWorth: currentWorth,
                purchaseDate: asset.nav_purchase_date || new Date().toISOString().split('T')[0],
              };
              
              if (market === "india") {
                indiaMutualFunds.push(mutualFund);
              } else {
                europeMutualFunds.push(mutualFund);
              }
            } else if (asset.type === "fixed_deposit") {
              const principalAmount = parseFloat(asset.principal_amount || "0");
              const interestRate = parseFloat(asset.fd_interest_rate || "0");
              // Calculate duration from start_date and maturity_date
              const startDate = asset.start_date ? new Date(asset.start_date) : new Date();
              const maturityDate = asset.maturity_date ? new Date(asset.maturity_date) : new Date();
              const durationMonths = Math.round((maturityDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 30));
              const maturityAmount = calculateMaturityAmount(principalAmount, interestRate, durationMonths);
              
              const fixedDeposit = {
                id: asset.id,
                dbId: asset.id,
                bankName: asset.name,
                amountInvested: principalAmount,
                rateOfInterest: interestRate,
                duration: durationMonths,
                maturityAmount: maturityAmount,
                startDate: asset.start_date || new Date().toISOString().split('T')[0],
                maturityDate: asset.maturity_date || new Date().toISOString().split('T')[0],
              };
              
              if (market === "india") {
                indiaFixedDeposits.push(fixedDeposit);
              } else {
                europeFixedDeposits.push(fixedDeposit);
              }
            }
          });
          
          setStocks({
            india: indiaStocks,
            europe: europeStocks,
          });
          
          setBankAccounts({
            india: indiaBankAccounts,
            europe: europeBankAccounts,
          });
          
          setMutualFunds({
            india: indiaMutualFunds,
            europe: europeMutualFunds,
          });
          
          setFixedDeposits({
            india: indiaFixedDeposits,
            europe: europeFixedDeposits,
          });
          
          // Recalculate net worth (using actualWorth for stocks, not totalInvested)
          const indiaNetWorth = indiaStocks.reduce((sum, s) => sum + s.actualWorth, 0) +
                               indiaBankAccounts.reduce((sum, a) => sum + a.balance, 0) +
                               indiaMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0) +
                               indiaFixedDeposits.reduce((sum, fd) => sum + fd.maturityAmount, 0);
          const europeNetWorth = europeStocks.reduce((sum, s) => sum + s.actualWorth, 0) +
                                europeBankAccounts.reduce((sum, a) => sum + a.balance, 0) +
                                europeMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0) +
                                europeFixedDeposits.reduce((sum, fd) => sum + fd.maturityAmount, 0);
          
          setNetWorth({
            india: indiaNetWorth,
            europe: europeNetWorth,
          });
        }
      } catch (error) {
        console.error("Error fetching assets:", error);
      } finally {
        setIsLoadingAssets(false);
      }
    };

    fetchAssets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Periodically update stock prices
  useEffect(() => {
    const updateStockPrices = async () => {
      try {
        const accessToken = localStorage.getItem("access_token");
        if (!accessToken) return;

        // Update prices in database
        const response = await fetch("/api/assets/update-prices", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (response.ok) {
          // Refetch assets to get updated prices
          const assetsResponse = await fetch("/api/assets", {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          });

          if (assetsResponse.ok) {
            const assets = await assetsResponse.json();
            
            // Update stocks with new prices
            setStocks((prev) => {
              const updatedStocks: typeof prev = {
                india: [...prev.india],
                europe: [...prev.europe],
              };

              assets.forEach((asset: any) => {
                if (asset.type === "stock") {
                  const currency = asset.currency || "USD";
                  const market: Market = currency === "INR" ? "india" : "europe";
                  const marketStocks = updatedStocks[market];
                  const stockIndex = marketStocks.findIndex(s => s.dbId === asset.id);

                  if (stockIndex >= 0) {
                    const currentPrice = parseFloat(asset.current_price || asset.purchase_price || "0");
                    const quantity = parseFloat(asset.quantity || "0");
                    const actualWorth = currentPrice * quantity;

                    updatedStocks[market][stockIndex] = {
                      ...marketStocks[stockIndex],
                      actualWorth: actualWorth,
                    };
                  }
                }
              });

              // Recalculate net worth
              const indiaNetWorth = updatedStocks.india.reduce((sum, s) => sum + s.actualWorth, 0) +
                                   bankAccounts.india.reduce((sum, a) => sum + a.balance, 0) +
                                   mutualFunds.india.reduce((sum, f) => sum + f.currentWorth, 0);
              const europeNetWorth = updatedStocks.europe.reduce((sum, s) => sum + s.actualWorth, 0) +
                                    bankAccounts.europe.reduce((sum, a) => sum + a.balance, 0) +
                                    mutualFunds.europe.reduce((sum, f) => sum + f.currentWorth, 0);

              setNetWorth({
                india: indiaNetWorth,
                europe: europeNetWorth,
              });

              return updatedStocks;
            });
          }
        }
      } catch (error) {
        console.error("Error updating stock prices:", error);
      }
    };

    // Update immediately on mount
    if (!isLoadingAssets) {
      updateStockPrices();
    }

    // Update every 60 seconds (adjust interval as needed)
    const interval = setInterval(updateStockPrices, 60000);

    return () => clearInterval(interval);
  }, [isLoadingAssets, bankAccounts]);
  
  // Save stock to database
  const saveStockToDatabase = async (stock: {
    id: string;
    dbId?: string;
    name: string;
    price: number;
    quantity: number;
    totalInvested: number;
    actualWorth: number;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        console.error("No access token found when saving stock");
        return;
      }

      const currency = marketConfig[market].currency;
      // Calculate current price from actualWorth (current value) and quantity
      const currentPrice = stock.quantity > 0 ? (stock.actualWorth / stock.quantity) : stock.price;
      const assetData = {
        name: stock.name,
        type: "stock",
        currency: currency,
        stock_symbol: stockSymbol || stock.name.substring(0, 20), // Use selected symbol or fallback
        quantity: stock.quantity.toString(),
        purchase_price: stock.price.toString(),
        current_price: currentPrice.toString(), // Use calculated current price from actualWorth
        current_value: stock.actualWorth.toString(), // Use the manually set current value
        purchase_date: stockPurchaseDate, // Use user-selected purchase date
        is_active: true, // Explicitly set is_active
      };

      console.log(`Saving stock to database: ${stock.name}, market: ${market}, currency: ${currency}`);

      if (stock.dbId) {
        // Update existing asset
        console.log(`Updating existing stock with dbId: ${stock.dbId}`);
        const response = await fetch(`/api/assets/${stock.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        return response.ok;
      } else {
        // Create new asset
        const response = await fetch("/api/assets", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (response.ok) {
          const createdAsset = await response.json();
          return createdAsset.id;
        }
        return null;
      }
    } catch (error) {
      console.error("Error saving stock to database:", error);
      return null;
    }
  };

  // Delete asset from database
  const deleteAssetFromDatabase = async (assetId: string) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        console.error("No access token found when deleting asset");
        return false;
      }

      console.log(`Deleting asset with ID: ${assetId}`);
      const response = await fetch(`/api/assets/${assetId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
        console.error(`Failed to delete asset: ${errorData.message || response.statusText}`, errorData);
        return false;
      }

      console.log(`Successfully deleted asset: ${assetId}`);
      return true;
    } catch (error) {
      console.error("Error deleting asset from database:", error);
      return false;
    }
  };

  // Save fixed deposit to database
  const saveFixedDepositToDatabase = async (fd: {
    id: string;
    dbId?: string;
    bankName: string;
    amountInvested: number;
    rateOfInterest: number;
    duration: number;
    maturityAmount: number;
    startDate: string;
    maturityDate: string;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData = {
        name: fd.bankName,
        type: "fixed_deposit",
        currency: currency,
        principal_amount: fd.amountInvested.toString(),
        fd_interest_rate: fd.rateOfInterest.toString(),
        start_date: fd.startDate,
        maturity_date: fd.maturityDate,
        current_value: fd.amountInvested.toString(), // Use principal amount, not maturity amount
        is_active: true, // Explicitly set is_active
      };

      console.log(`Saving fixed deposit to database: ${fd.bankName}, market: ${market}, currency: ${currency}`);

      if (fd.dbId) {
        // Update existing asset
        console.log(`Updating existing fixed deposit with dbId: ${fd.dbId}`);
        const response = await fetch(`/api/assets/${fd.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to update fixed deposit: ${errorData.message || response.statusText}`);
        } else {
          console.log(`Successfully updated fixed deposit: ${fd.bankName}`);
        }
        return response.ok;
      } else {
        // Create new asset
        console.log(`Creating new fixed deposit: ${fd.bankName}`);
        const response = await fetch("/api/assets", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (response.ok) {
          const createdAsset = await response.json();
          console.log(`Successfully created fixed deposit: ${fd.bankName}, dbId: ${createdAsset.id}`);
          return createdAsset.id;
        } else {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to create fixed deposit: ${errorData.message || response.statusText}`, errorData);
        }
        return null;
      }
    } catch (error) {
      console.error("Error saving fixed deposit to database:", error);
      return null;
    }
  };

  // Save mutual fund to database
  const saveMutualFundToDatabase = async (fund: {
    id: string;
    dbId?: string;
    fundName: string;
    nav: number;
    units: number;
    totalInvested: number;
    currentWorth: number;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData = {
        name: fund.fundName,
        type: "mutual_fund",
        currency: currency,
        nav: fund.nav.toString(),
        units: fund.units.toString(),
        current_value: fund.currentWorth.toString(), // Use the manually set current value
        nav_purchase_date: (fund as any).purchaseDate || mutualFundPurchaseDate, // Use user-selected purchase date
        is_active: true, // Explicitly set is_active
      };

      console.log(`Saving mutual fund to database: ${fund.fundName}, market: ${market}, currency: ${currency}`);

      if (fund.dbId) {
        // Update existing asset
        console.log(`Updating existing mutual fund with dbId: ${fund.dbId}`);
        const response = await fetch(`/api/assets/${fund.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to update mutual fund: ${errorData.message || response.statusText}`);
        } else {
          console.log(`Successfully updated mutual fund: ${fund.fundName}`);
        }
        return response.ok;
      } else {
        // Create new asset
        console.log(`Creating new mutual fund: ${fund.fundName}`);
        const response = await fetch("/api/assets", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (response.ok) {
          const createdAsset = await response.json();
          console.log(`Successfully created mutual fund: ${fund.fundName}, dbId: ${createdAsset.id}`);
          return createdAsset.id;
        } else {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to create mutual fund: ${errorData.message || response.statusText}`, errorData);
        }
        return null;
      }
    } catch (error) {
      console.error("Error saving mutual fund to database:", error);
      return null;
    }
  };

  // Save bank account to database
  const saveBankAccountToDatabase = async (account: {
    id: string;
    dbId?: string;
    bankName: string;
    accountNumber?: string;
    balance: number;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData = {
        name: account.bankName,
        type: "bank_account",
        currency: currency,
        bank_name: account.bankName,
        account_number: account.accountNumber || null,
        account_type: "savings", // Default to savings
        current_value: account.balance.toString(),
        notes: null,
        is_active: true, // Explicitly set is_active
      };

      console.log(`Saving bank account to database: ${account.bankName}, market: ${market}, currency: ${currency}`);

      if (account.dbId) {
        // Update existing asset
        const response = await fetch(`/api/assets/${account.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to update bank account: ${errorData.message || response.statusText}`);
        } else {
          console.log(`Successfully updated bank account: ${account.bankName}`);
        }
        return response.ok;
      } else {
        // Create new asset
        console.log(`Creating new bank account: ${account.bankName}`);
        const response = await fetch("/api/assets", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });
        
        if (response.ok) {
          const createdAsset = await response.json();
          console.log(`Successfully created bank account: ${account.bankName}, dbId: ${createdAsset.id}`);
          return createdAsset.id;
        } else {
          const errorData = await response.json().catch(() => ({ message: "Unknown error" }));
          console.error(`Failed to create bank account: ${errorData.message || response.statusText}`, errorData);
        }
        return null;
      }
    } catch (error) {
      console.error("Error saving bank account to database:", error);
      return null;
    }
  };
  
  if (isLoadingAssets) {
    return (
      <main className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your assets...</p>
        </div>
      </main>
    );
  }
  
  return (
    <main className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Financial Assets</h1>
            <p className="text-sm text-gray-600">Manage your stocks, mutual funds, bank accounts, and fixed deposits</p>
          </div>
          <div className="flex items-center space-x-4">
            {/* Market Selection Dropdown */}
            <div className="flex items-center space-x-2">
              <label htmlFor="market-select" className="text-sm font-medium text-gray-700">
                Market:
              </label>
              <select
                id="market-select"
                value={selectedMarket}
                onChange={(e) => setSelectedMarket(e.target.value as Market)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              >
                <option value="india">India (INR)</option>
                <option value="europe">Europe (EUR)</option>
              </select>
            </div>
            <button
              onClick={() => (window.location.href = "/expenses")}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            >
              Expense Tracker
            </button>
            <button className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900">
              Profile
            </button>
            <button
              onClick={() => {
                localStorage.removeItem("access_token");
                localStorage.removeItem("refresh_token");
                window.location.href = "/";
              }}
              className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content with Resizable Panels */}
      <div className="flex-1 overflow-hidden">
        <ResizablePanel
          left={
            <div className="h-full bg-gray-50 p-8 overflow-y-auto">
              <div className="max-w-4xl mx-auto">
                {/* Total Net Worth Section */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                        Total Net Worth
                      </h3>
                      <p className="text-xs text-gray-400 mt-1">Individual</p>
                    </div>
                    <div className="text-right">
                      <div className="flex items-baseline space-x-2">
                        <p className="text-3xl font-bold text-gray-900">
                          {currentMarket.symbol}
                          {currentNetWorth.toLocaleString("en-IN", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </p>
                        <span className="text-sm text-gray-500">
                          {currentMarket.currency}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        {currentMarket.name} Market
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {/* TODO: Add change indicator when data is available */}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Asset Tabs Section */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200">
                  {/* Tabs */}
                  <div className="border-b border-gray-200">
                    <nav className="flex -mb-px" aria-label="Tabs">
                      {tabConfig.map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`
                            flex-1 px-4 py-3 text-sm font-medium text-center border-b-2 transition-colors
                            ${
                              activeTab === tab.id
                                ? "border-primary-500 text-primary-600 bg-primary-50"
                                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                            }
                          `}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </nav>
                  </div>

                  {/* Tab Content */}
                  <div className="p-6">
                    {activeTab === "stocks" && (
                      <div>
                        {stocks[selectedMarket].length === 0 ? (
                          <div className="text-center py-12">
                            <svg
                              className="mx-auto h-12 w-12 text-gray-400 mb-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                              />
                            </svg>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Stocks Added</h3>
                            <p className="text-gray-500 mb-4">
                              Start building your portfolio by adding your first stock
                            </p>
                            <button
                              onClick={() => {
                                setSelectedAssetType("stock");
                                setIsAddAssetModalOpen(true);
                              }}
                              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                            >
                              Add Stock
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {stocks[selectedMarket].length} {stocks[selectedMarket].length === 1 ? "Stock" : "Stocks"}
                              </h3>
                              <button
                                onClick={() => {
                                  setSelectedAssetType("stock");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                + Add Stock
                              </button>
                            </div>
                            <div className="space-y-2">
                              {stocks[selectedMarket].map((stock) => (
                                <div
                                  key={stock.id}
                                  className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                                >
                                  <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1">
                                      <h4 className="text-sm font-semibold text-gray-900 mb-2">
                                        {stock.name}
                                      </h4>
                                      <div className="flex items-center space-x-4 text-xs text-gray-600">
                                        <span>
                                          Avg. Price: {currentMarket.symbol}
                                          {stock.price.toLocaleString("en-IN", {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2,
                                          })}
                                        </span>
                                        <span>Qty: {stock.quantity}</span>
                                        {stock.purchaseDate && (
                                          <span>
                                            Purchase Date: {formatDateDDMMYYYY(stock.purchaseDate)}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="flex items-center space-x-1">
                                      <button
                                        onClick={() => {
                                          setEditingStockId(stock.id);
                                          setSelectedAssetType("stock");
                                          setStockName(stock.name);
                                          // Stock name already set above
                                          setStockSymbol(stock.symbol || ""); // Load existing symbol
                                          setStockPrice(stock.price.toString());
                                          setStockQuantity(stock.quantity.toString());
                                          setStockPurchaseDate(stock.purchaseDate || new Date().toISOString().split('T')[0]);
                                          setStockCurrentWorth(stock.actualWorth.toString()); // Load current worth
                                          setIsAddAssetModalOpen(true);
                                        }}
                                        className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                        title="Edit stock"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                          />
                                        </svg>
                                      </button>
                                      <button
                                        onClick={async () => {
                                          if (window.confirm(`Are you sure you want to delete ${stock.name}? This action cannot be undone.`)) {
                                            const dbId = stock.dbId || stock.id;
                                            const deleted = await deleteAssetFromDatabase(dbId);
                                            
                                            if (deleted) {
                                              // Remove from state
                                              setStocks((prev) => {
                                                const updatedStocks = prev[selectedMarket].filter(s => s.id !== stock.id);
                                                
                                                // Recalculate net worth
                                                const updatedBankAccounts = bankAccounts[selectedMarket];
                                                const updatedMutualFunds = mutualFunds[selectedMarket];
                                                const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                const bankAccountsTotal = updatedBankAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                const mutualFundsTotal = updatedMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                const updatedFixedDeposits = fixedDeposits[selectedMarket];
                                                const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                                                
                                                setNetWorth((prev) => ({
                                                  ...prev,
                                                  [selectedMarket]: newNetWorth,
                                                }));
                                                
                                                return {
                                                  ...prev,
                                                  [selectedMarket]: updatedStocks,
                                                };
                                              });
                                            } else {
                                              alert("Failed to delete stock. Please try again.");
                                            }
                                          }
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                        title="Delete stock"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                          />
                                        </svg>
                                      </button>
                                    </div>
                                  </div>
                                  <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                                    <div>
                                      <p className="text-xs text-gray-500 mb-1">Total Amount Invested</p>
                                      <p className="text-sm font-semibold text-gray-900">
                                        {currentMarket.symbol}
                                        {stock.totalInvested.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </p>
                                    </div>
                                    <div className="text-right">
                                      <p className="text-xs text-gray-500 mb-1">Actual Worth</p>
                                      <p className="text-sm font-semibold text-gray-900">
                                        {currentMarket.symbol}
                                        {stock.actualWorth.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "bank_accounts" && (
                      <div>
                        {bankAccounts[selectedMarket].length === 0 ? (
                          <div className="text-center py-12">
                            <svg
                              className="mx-auto h-12 w-12 text-gray-400 mb-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                              />
                            </svg>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Bank Accounts Added</h3>
                            <p className="text-gray-500 mb-4">
                              Track your bank account balances and transactions
                            </p>
                            <button
                              onClick={() => {
                                setSelectedAssetType("bank_account");
                                setIsAddAssetModalOpen(true);
                              }}
                              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                            >
                              Add Bank Account
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {bankAccounts[selectedMarket].length} {bankAccounts[selectedMarket].length === 1 ? "Bank Account" : "Bank Accounts"}
                              </h3>
                              <button
                                onClick={() => {
                                  setSelectedAssetType("bank_account");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                + Add Bank Account
                              </button>
                            </div>
                            <div className="space-y-2">
                              {bankAccounts[selectedMarket].map((account) => (
                                <div
                                  key={account.id}
                                  className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                                >
                                  <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1">
                                      <h4 className="text-sm font-semibold text-gray-900 mb-2">
                                        {account.bankName}
                                      </h4>
                                      {account.accountNumber && (
                                        <p className="text-xs text-gray-600 mb-1">
                                          Account: {account.accountNumber}
                                        </p>
                                      )}
                                    </div>
                                    <div className="flex items-center space-x-1">
                                      <button
                                        onClick={() => {
                                          setEditingBankAccountId(account.id);
                                          setSelectedAssetType("bank_account");
                                          setBankName(account.bankName);
                                          setAccountNumber(account.accountNumber || "");
                                          setBankBalance(account.balance.toString());
                                          setIsAddAssetModalOpen(true);
                                        }}
                                        className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                        title="Edit bank account"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                          />
                                        </svg>
                                      </button>
                                      <button
                                        onClick={async () => {
                                          if (window.confirm(`Are you sure you want to delete ${account.bankName}? This action cannot be undone.`)) {
                                            const dbId = account.dbId || account.id;
                                            const deleted = await deleteAssetFromDatabase(dbId);
                                            
                                            if (deleted) {
                                              // Remove from state
                                              setBankAccounts((prev) => {
                                                const updatedAccounts = prev[selectedMarket].filter(a => a.id !== account.id);
                                                
                                                // Recalculate net worth
                                                const updatedStocks = stocks[selectedMarket];
                                                const updatedMutualFunds = mutualFunds[selectedMarket];
                                                const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                const bankAccountsTotal = updatedAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                const mutualFundsTotal = updatedMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                const updatedFixedDeposits = fixedDeposits[selectedMarket];
                                                const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                                                
                                                setNetWorth((prev) => ({
                                                  ...prev,
                                                  [selectedMarket]: newNetWorth,
                                                }));
                                                
                                                return {
                                                  ...prev,
                                                  [selectedMarket]: updatedAccounts,
                                                };
                                              });
                                            } else {
                                              alert("Failed to delete bank account. Please try again.");
                                            }
                                          }
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                        title="Delete bank account"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                          />
                                        </svg>
                                      </button>
                                    </div>
                                  </div>
                                  <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                                    <div>
                                      <p className="text-xs text-gray-500 mb-1">Balance</p>
                                      <p className="text-lg font-semibold text-gray-900">
                                        {currentMarket.symbol}
                                        {account.balance.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </p>
                                      <p className="text-xs text-gray-500 mt-1">
                                        {currentMarket.currency}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "mutual_funds" && (
                      <div>
                        {mutualFunds[selectedMarket].length === 0 ? (
                          <div className="text-center py-12">
                            <svg
                              className="mx-auto h-12 w-12 text-gray-400 mb-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                              />
                            </svg>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Mutual Funds Added</h3>
                            <p className="text-gray-500 mb-4">
                              Manage your mutual fund investments and track performance
                            </p>
                            <button
                              onClick={() => {
                                setSelectedAssetType("mutual_fund");
                                setIsAddAssetModalOpen(true);
                              }}
                              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                            >
                              Add Mutual Fund
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {mutualFunds[selectedMarket].length} {mutualFunds[selectedMarket].length === 1 ? "Mutual Fund" : "Mutual Funds"}
                              </h3>
                              <button
                                onClick={() => {
                                  setSelectedAssetType("mutual_fund");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                + Add Mutual Fund
                              </button>
                            </div>
                            <div className="space-y-2">
                              {mutualFunds[selectedMarket].map((fund) => (
                                <div
                                  key={fund.id}
                                  className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                                >
                                  <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1">
                                      <h4 className="text-sm font-semibold text-gray-900 mb-2">
                                        {fund.fundName}
                                      </h4>
                                      <div className="flex items-center space-x-4 text-xs text-gray-600">
                                        <span>
                                          NAV: {currentMarket.symbol}
                                          {fund.nav.toLocaleString("en-IN", {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2,
                                          })}
                                        </span>
                                        <span>Units: {fund.units.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}</span>
                                        {fund.purchaseDate && (
                                          <span>
                                            Purchase Date: {formatDateDDMMYYYY(fund.purchaseDate)}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="flex items-center space-x-1">
                                      <button
                                        onClick={() => {
                                          setEditingMutualFundId(fund.id);
                                          setSelectedAssetType("mutual_fund");
                                          setFundName(fund.fundName);
                                          setNav(fund.nav.toString());
                                          setUnits(fund.units.toString());
                                          setMutualFundPurchaseDate(fund.purchaseDate || new Date().toISOString().split('T')[0]);
                                          setMutualFundCurrentWorth(fund.currentWorth.toString()); // Load current worth
                                          setIsAddAssetModalOpen(true);
                                        }}
                                        className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                        title="Edit mutual fund"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                          />
                                        </svg>
                                      </button>
                                      <button
                                        onClick={async () => {
                                          if (window.confirm(`Are you sure you want to delete ${fund.fundName}? This action cannot be undone.`)) {
                                            const dbId = fund.dbId || fund.id;
                                            const deleted = await deleteAssetFromDatabase(dbId);
                                            
                                            if (deleted) {
                                              // Remove from state
                                              setMutualFunds((prev) => {
                                                const updatedFunds = prev[selectedMarket].filter(f => f.id !== fund.id);
                                                
                                                // Recalculate net worth
                                                const updatedStocks = stocks[selectedMarket];
                                                const updatedBankAccounts = bankAccounts[selectedMarket];
                                                const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                const bankAccountsTotal = updatedBankAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                const mutualFundsTotal = updatedFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                const updatedFixedDeposits = fixedDeposits[selectedMarket];
                                                const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                                                
                                                setNetWorth((prev) => ({
                                                  ...prev,
                                                  [selectedMarket]: newNetWorth,
                                                }));
                                                
                                                return {
                                                  ...prev,
                                                  [selectedMarket]: updatedFunds,
                                                };
                                              });
                                            } else {
                                              alert("Failed to delete mutual fund. Please try again.");
                                            }
                                          }
                                        }}
                                        className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                        title="Delete mutual fund"
                                      >
                                        <svg
                                          className="h-4 w-4"
                                          fill="none"
                                          viewBox="0 0 24 24"
                                          stroke="currentColor"
                                        >
                                          <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                          />
                                        </svg>
                                      </button>
                                    </div>
                                  </div>
                                  <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                                    <div>
                                      <p className="text-xs text-gray-500 mb-1">Total Amount Invested</p>
                                      <p className="text-sm font-semibold text-gray-900">
                                        {currentMarket.symbol}
                                        {fund.totalInvested.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </p>
                                    </div>
                                    <div className="text-right">
                                      <p className="text-xs text-gray-500 mb-1">Current Worth</p>
                                      <p className="text-sm font-semibold text-gray-900">
                                        {currentMarket.symbol}
                                        {fund.currentWorth.toLocaleString("en-IN", {
                                          minimumFractionDigits: 2,
                                          maximumFractionDigits: 2,
                                        })}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "fixed_deposits" && (
                      <div>
                        {fixedDeposits[selectedMarket].length === 0 ? (
                          <div className="text-center py-12">
                            <div className="mx-auto h-16 w-16 mb-4 flex items-center justify-center bg-gray-100 rounded-full">
                              <span className="text-3xl font-semibold text-gray-600">
                                {currentMarket.symbol}
                              </span>
                            </div>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Fixed Deposits Added</h3>
                            <p className="text-gray-500 mb-4">
                              Track your fixed deposit investments and maturity dates
                            </p>
                            <button
                              onClick={() => {
                                setSelectedAssetType("fixed_deposit");
                                setIsAddAssetModalOpen(true);
                              }}
                              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                            >
                              Add Fixed Deposit
                            </button>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {fixedDeposits[selectedMarket].length} {fixedDeposits[selectedMarket].length === 1 ? "Fixed Deposit" : "Fixed Deposits"}
                              </h3>
                              <button
                                onClick={() => {
                                  setSelectedAssetType("fixed_deposit");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                + Add Fixed Deposit
                              </button>
                            </div>
                            <div className="space-y-2">
                              {fixedDeposits[selectedMarket].map((fd) => {
                                const maturityDate = new Date(fd.maturityDate);
                                const isMatured = maturityDate < new Date();
                                
                                return (
                                  <div
                                    key={fd.id}
                                    className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
                                  >
                                    <div className="flex items-start justify-between mb-3">
                                      <div className="flex-1">
                                        <h4 className="text-sm font-semibold text-gray-900 mb-2">
                                          {fd.bankName}
                                        </h4>
                                        <div className="flex items-center space-x-4 text-xs text-gray-600">
                                          <span>
                                            Amount: {currentMarket.symbol}
                                            {fd.amountInvested.toLocaleString("en-IN", {
                                              minimumFractionDigits: 2,
                                              maximumFractionDigits: 2,
                                            })}
                                          </span>
                                          <span>Rate: {fd.rateOfInterest}% p.a.</span>
                                          <span>Duration: {fd.duration} months</span>
                                        </div>
                                        <div className="mt-2 text-xs text-gray-500">
                                          <span>Start: {new Date(fd.startDate).toLocaleDateString()}</span>
                                          <span className="ml-4">Maturity: {maturityDate.toLocaleDateString()}</span>
                                          {isMatured && (
                                            <span className="ml-2 text-green-600 font-medium">(Matured)</span>
                                          )}
                                        </div>
                                      </div>
                                      <div className="flex items-center space-x-1">
                                        <button
                                          onClick={() => {
                                            setEditingFixedDepositId(fd.id);
                                            setSelectedAssetType("fixed_deposit");
                                            setFdBankName(fd.bankName);
                                            setFdAmount(fd.amountInvested.toString());
                                            setFdRate(fd.rateOfInterest.toString());
                                            setFdDuration(fd.duration.toString());
                                            setFdStartDate(fd.startDate || new Date().toISOString().split('T')[0]);
                                            setIsAddAssetModalOpen(true);
                                          }}
                                          className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                          title="Edit fixed deposit"
                                        >
                                          <svg
                                            className="h-4 w-4"
                                            fill="none"
                                            viewBox="0 0 24 24"
                                            stroke="currentColor"
                                          >
                                            <path
                                              strokeLinecap="round"
                                              strokeLinejoin="round"
                                              strokeWidth={2}
                                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                            />
                                          </svg>
                                        </button>
                                        <button
                                          onClick={async () => {
                                            if (window.confirm(`Are you sure you want to delete ${fd.bankName} fixed deposit? This action cannot be undone.`)) {
                                              const dbId = fd.dbId || fd.id;
                                              const deleted = await deleteAssetFromDatabase(dbId);
                                              
                                              if (deleted) {
                                                // Remove from state
                                                setFixedDeposits((prev) => {
                                                  const updatedFDs = prev[selectedMarket].filter(f => f.id !== fd.id);
                                                  
                                                  // Recalculate net worth
                                                  const updatedStocks = stocks[selectedMarket];
                                                  const updatedBankAccounts = bankAccounts[selectedMarket];
                                                  const updatedMutualFunds = mutualFunds[selectedMarket];
                                                  const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                  const bankAccountsTotal = updatedBankAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                  const mutualFundsTotal = updatedMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                  const fixedDepositsTotal = updatedFDs.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                  const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                                                  
                                                  setNetWorth((prev) => ({
                                                    ...prev,
                                                    [selectedMarket]: newNetWorth,
                                                  }));
                                                  
                                                  return {
                                                    ...prev,
                                                    [selectedMarket]: updatedFDs,
                                                  };
                                                });
                                              } else {
                                                alert("Failed to delete fixed deposit. Please try again.");
                                              }
                                            }
                                          }}
                                          className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                          title="Delete fixed deposit"
                                        >
                                          <svg
                                            className="h-4 w-4"
                                            fill="none"
                                            viewBox="0 0 24 24"
                                            stroke="currentColor"
                                          >
                                            <path
                                              strokeLinecap="round"
                                              strokeLinejoin="round"
                                              strokeWidth={2}
                                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                            />
                                          </svg>
                                        </button>
                                      </div>
                                    </div>
                                    <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                                      <div>
                                        <p className="text-xs text-gray-500 mb-1">Amount Invested</p>
                                        <p className="text-sm font-semibold text-gray-900">
                                          {currentMarket.symbol}
                                          {fd.amountInvested.toLocaleString("en-IN", {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2,
                                          })}
                                        </p>
                                      </div>
                                      <div className="text-right">
                                        <p className="text-xs text-gray-500 mb-1">Amount at Maturity</p>
                                        <p className="text-sm font-semibold text-gray-900">
                                          {currentMarket.symbol}
                                          {fd.maturityAmount.toLocaleString("en-IN", {
                                            minimumFractionDigits: 2,
                                            maximumFractionDigits: 2,
                                          })}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          }
          right={<ChatWindow context="assets" />}
          defaultLeftWidth={60}
        />
      </div>

      {/* Add Asset Modal */}
      {isAddAssetModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
            onClick={() => setIsAddAssetModalOpen(false)}
          ></div>

          {/* Modal */}
          <div className="flex min-h-full items-center justify-center p-4">
            <div
              className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {editingStockId || editingBankAccountId || editingMutualFundId || editingFixedDepositId ? "Edit Asset" : "Add New Asset"}
                </h2>
                <button
                  onClick={() => setIsAddAssetModalOpen(false)}
                  className="text-gray-400 hover:text-gray-500 focus:outline-none"
                >
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              {/* Form */}
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  
                  if (selectedAssetType === "bank_account") {
                    const balance = parseFloat(bankBalance) || 0;
                    
                    if (editingBankAccountId) {
                      // Update existing bank account
                      setBankAccounts((prev) => {
                        const marketAccounts = prev[selectedMarket];
                        const accountIndex = marketAccounts.findIndex(acc => acc.id === editingBankAccountId);
                        
                        if (accountIndex >= 0) {
                          const accountToUpdate = marketAccounts[accountIndex];
                          // Update the account
                          const updatedAccounts = [...marketAccounts];
                          updatedAccounts[accountIndex] = {
                            ...accountToUpdate,
                            bankName: bankName,
                            accountNumber: accountNumber || undefined,
                            balance: balance,
                          };
                          
                          // Save to database (async, but don't wait)
                          saveBankAccountToDatabase(updatedAccounts[accountIndex], selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated accounts
                          const updatedStocks = stocks[selectedMarket];
                          const updatedMutualFunds = mutualFunds[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const updatedFixedDeposits = fixedDeposits[selectedMarket];
                          const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedAccounts,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingBankAccountId(null);
                    } else {
                      // Add new bank account
                      const tempId = `bank-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                      const newBankAccount: typeof bankAccounts.india[0] = {
                        id: tempId,
                        bankName: bankName,
                        accountNumber: accountNumber || undefined,
                        balance: balance,
                      };
                      
                      // Save to database
                      const dbId = await saveBankAccountToDatabase(newBankAccount, selectedMarket);
                      if (dbId && typeof dbId === 'string') {
                        newBankAccount.dbId = dbId;
                        newBankAccount.id = dbId; // Use database ID as the main ID
                      }
                      
                      setBankAccounts((prev) => {
                        const updatedAccounts = [...prev[selectedMarket], newBankAccount];
                        
                        // Calculate new net worth with updated accounts
                        const updatedStocks = stocks[selectedMarket];
                        const updatedMutualFunds = mutualFunds[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedAccounts,
                        };
                      });
                    }
                  } else if (selectedAssetType === "stock") {
                    const totalInvested = calculateStockTotal();
                    const price = parseFloat(stockPrice) || 0;
                    const quantity = parseFloat(stockQuantity) || 0;
                    
                    if (editingStockId) {
                      // Update existing stock
                      const currentWorth = parseFloat(stockCurrentWorth) || totalInvested; // Use manually entered value or fallback to calculated
                      setStocks((prev) => {
                        const marketStocks = prev[selectedMarket];
                        const stockIndex = marketStocks.findIndex(s => s.id === editingStockId);
                        
                        if (stockIndex >= 0) {
                          // Update the stock
                          const updatedStocks = [...marketStocks];
                          updatedStocks[stockIndex] = {
                            ...marketStocks[stockIndex],
                            name: stockName,
                            symbol: stockSymbol || marketStocks[stockIndex].symbol, // Update symbol if provided
                            price: price,
                            quantity: quantity,
                            totalInvested: totalInvested,
                            actualWorth: currentWorth, // Use manually entered current value
                            purchaseDate: stockPurchaseDate, // Include purchase date
                          };
                          
                          // Save to database (async, but don't wait)
                          saveStockToDatabase(updatedStocks[stockIndex], selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated stocks
                          const updatedBankAccounts = bankAccounts[selectedMarket];
                          const updatedMutualFunds = mutualFunds[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const updatedFixedDeposits = fixedDeposits[selectedMarket];
                          const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedStocks,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingStockId(null);
                    } else {
                      // Add new stock (with merge logic for same name)
                      const marketStocks = stocks[selectedMarket];
                      // Check if stock with same name already exists (case-insensitive)
                      const existingStockIndex = marketStocks.findIndex(
                        (s) => s.name.toLowerCase() === stockName.toLowerCase()
                      );
                      
                      let updatedStocks: typeof marketStocks;
                      let stockToSave: typeof marketStocks[0];
                      
                      if (existingStockIndex >= 0) {
                        // Stock exists - merge with existing entry
                        const existingStock = marketStocks[existingStockIndex];
                        const newQuantity = existingStock.quantity + quantity;
                        const newTotalInvested = existingStock.totalInvested + totalInvested;
                        // Calculate weighted average price
                        const newAveragePrice = newTotalInvested / newQuantity;
                        
                          const updatedStock = {
                            ...existingStock,
                            symbol: stockSymbol || existingStock.symbol, // Keep or update symbol
                            price: newAveragePrice,
                            quantity: newQuantity,
                            totalInvested: newTotalInvested,
                            actualWorth: newTotalInvested, // Will be updated by price update service
                            purchaseDate: stockPurchaseDate, // Include purchase date
                          };
                        
                        // Update the existing stock
                        updatedStocks = [...marketStocks];
                        updatedStocks[existingStockIndex] = updatedStock;
                        stockToSave = updatedStock;
                      } else {
                        // New stock - create new entry
                        const tempId = `stock-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                          const newStock: typeof marketStocks[0] = {
                            id: tempId,
                            name: stockName,
                            symbol: stockSymbol, // Store the symbol
                            price: price,
                            quantity: quantity,
                            totalInvested: totalInvested,
                            actualWorth: totalInvested, // Will be updated by price update service
                            purchaseDate: stockPurchaseDate, // Include purchase date
                          };
                        
                        updatedStocks = [...marketStocks, newStock];
                        stockToSave = newStock;
                      }
                      
                      // Save to database
                      const dbId = await saveStockToDatabase(stockToSave, selectedMarket);
                      if (dbId && typeof dbId === 'string') {
                        // Update the stock with database ID
                        const finalStockIndex = existingStockIndex >= 0 ? existingStockIndex : updatedStocks.length - 1;
                        updatedStocks[finalStockIndex] = {
                          ...updatedStocks[finalStockIndex],
                          id: dbId,
                          dbId: dbId,
                        };
                      }
                      
                      setStocks((prev) => {
                        // Calculate new net worth with updated stocks
                        const updatedBankAccounts = bankAccounts[selectedMarket];
                        const updatedMutualFunds = mutualFunds[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedStocks,
                        };
                      });
                    }
                  } else if (selectedAssetType === "mutual_fund") {
                    const totalInvested = calculateMutualFundTotal();
                    const navValue = parseFloat(nav) || 0;
                    const unitsValue = parseFloat(units) || 0;
                    
                    if (editingMutualFundId) {
                      // Update existing mutual fund
                      const currentWorth = parseFloat(mutualFundCurrentWorth) || totalInvested; // Use manually entered value or fallback to calculated
                      setMutualFunds((prev) => {
                        const marketFunds = prev[selectedMarket];
                        const fundIndex = marketFunds.findIndex(f => f.id === editingMutualFundId);
                        
                        if (fundIndex >= 0) {
                          // Update the fund
                          const updatedFunds = [...marketFunds];
                          updatedFunds[fundIndex] = {
                            ...marketFunds[fundIndex],
                            fundName: fundName,
                            nav: navValue,
                            units: unitsValue,
                            totalInvested: totalInvested,
                            currentWorth: currentWorth, // Use manually entered current value
                            purchaseDate: mutualFundPurchaseDate, // Include purchase date
                          };
                          
                          // Save to database (async, but don't wait)
                          saveMutualFundToDatabase({ ...updatedFunds[fundIndex], purchaseDate: mutualFundPurchaseDate } as any, selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated funds
                          const updatedStocks = stocks[selectedMarket];
                          const updatedBankAccounts = bankAccounts[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const updatedFixedDeposits = fixedDeposits[selectedMarket];
                          const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedFunds,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingMutualFundId(null);
                    } else {
                      // Add new mutual fund
                      const tempId = `mutual-fund-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                      const newMutualFund: typeof mutualFunds.india[0] = {
                        id: tempId,
                        fundName: fundName,
                        nav: navValue,
                        units: unitsValue,
                        totalInvested: totalInvested,
                        currentWorth: totalInvested, // For now, same as invested
                        purchaseDate: mutualFundPurchaseDate, // Include purchase date
                      };
                      
                      // Save to database
                      const dbId = await saveMutualFundToDatabase({ ...newMutualFund, purchaseDate: mutualFundPurchaseDate } as any, selectedMarket);
                      if (dbId && typeof dbId === 'string') {
                        newMutualFund.dbId = dbId;
                        newMutualFund.id = dbId; // Use database ID as the main ID
                      }
                      
                      setMutualFunds((prev) => {
                        const updatedFunds = [...prev[selectedMarket], newMutualFund];
                        
                        // Calculate new net worth with updated funds
                        const updatedStocks = stocks[selectedMarket];
                        const updatedBankAccounts = bankAccounts[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedFunds,
                        };
                      });
                    }
                  } else if (selectedAssetType === "fixed_deposit") {
                    const amountInvested = parseFloat(fdAmount) || 0;
                    const rateOfInterest = parseFloat(fdRate) || 0;
                    const duration = parseFloat(fdDuration) || 0;
                    const maturityAmount = calculateMaturityAmount(amountInvested, rateOfInterest, duration);
                    
                    // Calculate dates
                    const startDate = new Date(fdStartDate);
                    const maturityDate = new Date(startDate);
                    maturityDate.setMonth(maturityDate.getMonth() + duration);
                    
                    if (editingFixedDepositId) {
                      // Update existing fixed deposit
                      setFixedDeposits((prev) => {
                        const marketFDs = prev[selectedMarket];
                        const fdIndex = marketFDs.findIndex(f => f.id === editingFixedDepositId);
                        
                        if (fdIndex >= 0) {
                          // Update the fixed deposit
                          const updatedFDs = [...marketFDs];
                          updatedFDs[fdIndex] = {
                            ...marketFDs[fdIndex],
                            bankName: fdBankName,
                            amountInvested: amountInvested,
                            rateOfInterest: rateOfInterest,
                            duration: duration,
                            maturityAmount: maturityAmount,
                            startDate: startDate.toISOString().split('T')[0],
                            maturityDate: maturityDate.toISOString().split('T')[0],
                          };
                          
                          // Save to database (async, but don't wait)
                          saveFixedDepositToDatabase(updatedFDs[fdIndex], selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated fixed deposits
                          const updatedStocks = stocks[selectedMarket];
                          const updatedBankAccounts = bankAccounts[selectedMarket];
                          const updatedMutualFunds = mutualFunds[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const fixedDepositsTotal = updatedFDs.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedFDs,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingFixedDepositId(null);
                    } else {
                      // Add new fixed deposit
                      const tempId = `fixed-deposit-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                      const newFixedDeposit: typeof fixedDeposits.india[0] = {
                        id: tempId,
                        bankName: fdBankName,
                        amountInvested: amountInvested,
                        rateOfInterest: rateOfInterest,
                        duration: duration,
                        maturityAmount: maturityAmount,
                        startDate: startDate.toISOString().split('T')[0],
                        maturityDate: maturityDate.toISOString().split('T')[0],
                      };
                      
                      // Save to database
                      const dbId = await saveFixedDepositToDatabase(newFixedDeposit, selectedMarket);
                      if (dbId && typeof dbId === 'string') {
                        newFixedDeposit.dbId = dbId;
                        newFixedDeposit.id = dbId; // Use database ID as the main ID
                      }
                      
                      setFixedDeposits((prev) => {
                        const updatedFDs = [...prev[selectedMarket], newFixedDeposit];
                        
                        // Calculate new net worth with updated fixed deposits
                        const updatedStocks = stocks[selectedMarket];
                        const updatedBankAccounts = bankAccounts[selectedMarket];
                        const updatedMutualFunds = mutualFunds[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const fixedDepositsTotal = updatedFDs.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedFDs,
                        };
                      });
                    }
                  }
                  
                  // Reset form
                  setSelectedAssetType("");
                  setStockName("");
                  setStockSymbol("");
                  setStockPrice("");
                  setStockQuantity("");
                  setStockPurchaseDate(new Date().toISOString().split('T')[0]);
                  setStockCurrentWorth("");
                  setBankName("");
                  setAccountNumber("");
                  setBankBalance("");
                  setFundName("");
                  setNav("");
                  setUnits("");
                  setMutualFundPurchaseDate(new Date().toISOString().split('T')[0]);
                  setMutualFundCurrentWorth("");
                  setFdBankName("");
                  setFdAmount("");
                  setFdRate("");
                  setFdDuration("");
                  setFdStartDate(new Date().toISOString().split('T')[0]);
                  setEditingStockId(null);
                  setEditingBankAccountId(null);
                  setEditingMutualFundId(null);
                  setEditingFixedDepositId(null);
                  setIsAddAssetModalOpen(false);
                }}
                className="space-y-4"
              >
                {/* Stock-specific fields */}
                {selectedAssetType === "stock" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="stock-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Stock Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="stock-name"
                        value={stockName}
                        onChange={(e) => setStockName(e.target.value)}
                        required
                        placeholder="Enter stock name (e.g., Apple, Reliance, Microsoft)"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    {/* Show selected stock info */}
                    {stockSymbol && (
                      <div className="mt-2 text-xs text-gray-600">
                        Selected: <span className="font-medium">{stockName}</span> ({stockSymbol})
                      </div>
                    )}
                    
                    <div>
                      <label
                        htmlFor="stock-price"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Stock Price ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="stock-price"
                        value={stockPrice}
                        onChange={(e) => setStockPrice(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter stock price"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="stock-quantity"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Quantity <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="stock-quantity"
                        value={stockQuantity}
                        onChange={(e) => setStockQuantity(e.target.value)}
                        step="1"
                        min="1"
                        required
                        placeholder="Enter quantity"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="stock-purchase-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Purchase Date <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="stock-purchase-date"
                        value={stockPurchaseDate}
                        onChange={(e) => setStockPurchaseDate(e.target.value)}
                        required
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    {/* Calculated Total */}
                    {stockTotal > 0 && (
                      <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-700">
                            Total Amount Invested:
                          </span>
                          <span className="text-lg font-semibold text-gray-900">
                            {currentMarket.symbol}
                            {stockTotal.toLocaleString("en-IN", {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </span>
                        </div>
                      </div>
                    )}
                    
                    {/* Current Value field (only shown when editing) */}
                    {editingStockId && (
                      <div>
                        <label
                          htmlFor="stock-current-worth"
                          className="block text-sm font-medium text-gray-700 mb-2"
                        >
                          Current Value ({currentMarket.symbol}) <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="number"
                          id="stock-current-worth"
                          value={stockCurrentWorth}
                          onChange={(e) => setStockCurrentWorth(e.target.value)}
                          step="0.01"
                          min="0"
                          required
                          placeholder="Enter current market value"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Manually set the current market value of this stock
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Bank Account-specific fields */}
                {selectedAssetType === "bank_account" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="bank-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Bank Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="bank-name"
                        value={bankName}
                        onChange={(e) => setBankName(e.target.value)}
                        required
                        placeholder="e.g., State Bank of India, HDFC Bank"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="account-number"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Account Number <span className="text-gray-400 text-xs">(Optional)</span>
                      </label>
                      <input
                        type="text"
                        id="account-number"
                        value={accountNumber}
                        onChange={(e) => setAccountNumber(e.target.value)}
                        placeholder="Enter account number"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="bank-balance"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Bank Balance ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="bank-balance"
                        value={bankBalance}
                        onChange={(e) => setBankBalance(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter current balance"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                  </div>
                )}

                {/* Mutual Fund-specific fields */}
                {selectedAssetType === "mutual_fund" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="fund-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Fund Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="fund-name"
                        value={fundName}
                        onChange={(e) => setFundName(e.target.value)}
                        required
                        placeholder="e.g., HDFC Equity Fund, SBI Bluechip Fund"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="nav"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        NAV (Net Asset Value) ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="nav"
                        value={nav}
                        onChange={(e) => setNav(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter NAV"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="units"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Number of Units Purchased <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="units"
                        value={units}
                        onChange={(e) => setUnits(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter number of units"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="mutual-fund-purchase-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Purchase Date <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="mutual-fund-purchase-date"
                        value={mutualFundPurchaseDate}
                        onChange={(e) => setMutualFundPurchaseDate(e.target.value)}
                        required
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    {/* Calculated Total */}
                    {mutualFundTotal > 0 && (
                      <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-700">
                            Total Amount Invested:
                          </span>
                          <span className="text-lg font-semibold text-gray-900">
                            {currentMarket.symbol}
                            {mutualFundTotal.toLocaleString("en-IN", {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </span>
                        </div>
                      </div>
                    )}
                    
                    {/* Current Value field (only shown when editing) */}
                    {editingMutualFundId && (
                      <div>
                        <label
                          htmlFor="mutual-fund-current-worth"
                          className="block text-sm font-medium text-gray-700 mb-2"
                        >
                          Current Value ({currentMarket.symbol}) <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="number"
                          id="mutual-fund-current-worth"
                          value={mutualFundCurrentWorth}
                          onChange={(e) => setMutualFundCurrentWorth(e.target.value)}
                          step="0.01"
                          min="0"
                          required
                          placeholder="Enter current market value"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Manually set the current market value of this mutual fund
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Fixed Deposit-specific fields */}
                {selectedAssetType === "fixed_deposit" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="fd-bank-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Bank Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="fd-bank-name"
                        value={fdBankName}
                        onChange={(e) => setFdBankName(e.target.value)}
                        required
                        placeholder="e.g., State Bank of India, HDFC Bank"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="fd-amount"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Amount Invested ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="fd-amount"
                        value={fdAmount}
                        onChange={(e) => setFdAmount(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter amount invested"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="fd-rate"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Rate of Interest (% per annum) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="fd-rate"
                        value={fdRate}
                        onChange={(e) => setFdRate(e.target.value)}
                        step="0.01"
                        min="0"
                        max="100"
                        required
                        placeholder="Enter interest rate"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="fd-duration"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Duration (months) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="fd-duration"
                        value={fdDuration}
                        onChange={(e) => setFdDuration(e.target.value)}
                        step="1"
                        min="1"
                        required
                        placeholder="Enter duration in months"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="fd-start-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Start Date <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="fd-start-date"
                        value={fdStartDate}
                        onChange={(e) => setFdStartDate(e.target.value)}
                        required
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    {/* Calculated Maturity Amount */}
                    {(() => {
                      const amount = parseFloat(fdAmount) || 0;
                      const rate = parseFloat(fdRate) || 0;
                      const duration = parseFloat(fdDuration) || 0;
                      const maturityAmount = duration > 0 && amount > 0 && rate > 0 
                        ? calculateMaturityAmount(amount, rate, duration)
                        : 0;
                      
                      return maturityAmount > 0 ? (
                        <div className="bg-gray-50 rounded-md p-4 border border-gray-200">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700">
                              Amount at Maturity:
                            </span>
                            <span className="text-lg font-semibold text-gray-900">
                              {currentMarket.symbol}
                              {maturityAmount.toLocaleString("en-IN", {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </span>
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>
                )}

                {/* Form Actions */}
                <div className="flex items-center justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddAssetModalOpen(false);
                      setSelectedAssetType("");
                      setStockName("");
                      setStockSymbol("");
                      setStockPrice("");
                      setStockQuantity("");
                      setStockCurrentWorth("");
                      setBankName("");
                      setAccountNumber("");
                      setBankBalance("");
                      setFundName("");
                      setNav("");
                      setUnits("");
                      setMutualFundCurrentWorth("");
                      setFdBankName("");
                      setFdAmount("");
                      setFdRate("");
                      setFdDuration("");
                      setEditingStockId(null);
                      setEditingBankAccountId(null);
                      setEditingMutualFundId(null);
                      setEditingFixedDepositId(null);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                  >
                    Continue
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

