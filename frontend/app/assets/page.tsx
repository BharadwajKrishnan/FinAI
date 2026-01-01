"use client";

import { useState, useEffect } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
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

type AssetType = "stock" | "bank_account" | "mutual_fund" | "fixed_deposit" | "insurance_policy" | "commodity";

const assetTypeOptions = [
  { value: "stock", label: "Stock" },
  { value: "bank_account", label: "Bank Account" },
  { value: "mutual_fund", label: "Mutual Funds" },
  { value: "fixed_deposit", label: "Fixed Deposits" },
  { value: "insurance_policy", label: "Insurance Policy" },
  { value: "commodity", label: "Commodity" },
];

type ActiveTab = "stocks" | "bank_accounts" | "mutual_funds" | "fixed_deposits" | "insurance_policies" | "commodities";

const tabConfig = [
  { id: "stocks" as ActiveTab, label: "Stocks" },
  { id: "bank_accounts" as ActiveTab, label: "Bank Accounts" },
  { id: "mutual_funds" as ActiveTab, label: "Mutual Funds" },
  { id: "fixed_deposits" as ActiveTab, label: "Fixed Deposits" },
  { id: "insurance_policies" as ActiveTab, label: "Insurance Policies" },
  { id: "commodities" as ActiveTab, label: "Commodities" },
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

// Sortable Item Component
function SortableItem({ 
  id, 
  children, 
  dragHandle 
}: { 
  id: string; 
  children: React.ReactNode;
  dragHandle?: React.ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="relative">
      {dragHandle && (
        <div className="absolute left-0 top-0 h-full flex items-center cursor-grab active:cursor-grabbing z-10" {...attributes} {...listeners}>
          {dragHandle}
        </div>
      )}
      <div className={dragHandle ? "pl-8" : ""}>
        {children}
      </div>
    </div>
  );
}

export default function AssetsPage() {
  const [selectedMarket, setSelectedMarket] = useState<Market>("india");
  const [isAddAssetModalOpen, setIsAddAssetModalOpen] = useState(false);
  const [selectedAssetType, setSelectedAssetType] = useState<AssetType | "">("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("stocks");
  const [editingStockId, setEditingStockId] = useState<string | null>(null);
  const [editingBankAccountId, setEditingBankAccountId] = useState<string | null>(null);
  const [editingMutualFundId, setEditingMutualFundId] = useState<string | null>(null);
  const [editingFixedDepositId, setEditingFixedDepositId] = useState<string | null>(null);
  const [editingInsurancePolicyId, setEditingInsurancePolicyId] = useState<string | null>(null);
  const [editingCommodityId, setEditingCommodityId] = useState<string | null>(null);
  
  // Asset order state - stores order by asset type and market
  const [assetOrder, setAssetOrder] = useState<Record<string, string[]>>({});
  
  // Selected assets state - stores selected asset IDs by asset type and market
  const [selectedAssets, setSelectedAssets] = useState<Record<string, Set<string>>>({});
  
  // Family members state (for filtering only - management moved to Profile page)
  const [familyMembers, setFamilyMembers] = useState<Array<{
    id: string;
    name: string;
    relationship: string;
    notes?: string;
  }>>([]);
  
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
    familyMemberId?: string; // Optional: assigned to a family member
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
    familyMemberId?: string; // Optional: assigned to a family member
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
    familyMemberId?: string; // Optional: assigned to a family member
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
    familyMemberId?: string; // Optional: assigned to a family member
  }>>>({
    india: [],
    europe: [],
  });
  
  // Store insurance policies by market
  const [insurancePolicies, setInsurancePolicies] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    insuranceName: string;
    policyNumber: string;
    amountInsured: number;
    issueDate: string;
    dateOfMaturity: string;
    premium: number;
    nominee?: string;
    premiumPaymentDate?: string;
    familyMemberId?: string; // Optional: assigned to a family member
  }>>>({
    india: [],
    europe: [],
  });
  
  // Store commodities by market
  const [commodities, setCommodities] = useState<Record<Market, Array<{
    id: string;
    dbId?: string; // Database ID for persistence
    commodityName: string;
    form: string;
    quantity: number;
    units: string;
    purchaseDate: string;
    purchasePrice: number;
    currentValue: number; // Current value of the commodity
    familyMemberId?: string; // Optional: assigned to a family member
  }>>>({
    india: [],
    europe: [],
  });
  
  const [isLoadingAssets, setIsLoadingAssets] = useState(true);
  const [isUploadingPdf, setIsUploadingPdf] = useState(false);
  
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
  
  // Insurance Policy-specific fields
  const [insuranceName, setInsuranceName] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [amountInsured, setAmountInsured] = useState("");
  const [issueDate, setIssueDate] = useState(new Date().toISOString().split('T')[0]);
  const [dateOfMaturity, setDateOfMaturity] = useState("");
  const [premium, setPremium] = useState("");
  const [nominee, setNominee] = useState("");
  const [premiumPaymentDate, setPremiumPaymentDate] = useState("");
  
  // Commodity-specific fields
  const [commodityName, setCommodityName] = useState("");
  const [commodityForm, setCommodityForm] = useState("");
  const [commodityQuantity, setCommodityQuantity] = useState("");
  const [commodityUnits, setCommodityUnits] = useState("grams");
  const [commodityPurchaseDate, setCommodityPurchaseDate] = useState(new Date().toISOString().split('T')[0]);
  const [commodityPurchasePrice, setCommodityPurchasePrice] = useState("");
  
  // Family member assignment for assets
  const [selectedFamilyMemberId, setSelectedFamilyMemberId] = useState<string | undefined>(undefined);
  
  // Family member filter for dashboard
  const [selectedFamilyMemberFilter, setSelectedFamilyMemberFilter] = useState<string | "all">("all");
  
  const currentMarket = marketConfig[selectedMarket];
  const currentNetWorth = netWorth[selectedMarket];
  
  // Calculate total amount invested for stocks
  const calculateStockTotal = () => {
    const price = parseFloat(stockPrice) || 0;
    const quantity = parseFloat(stockQuantity) || 0;
    return price * quantity;
  };
  
  // Recalculate net worth from all assets for a given market
  const recalculateNetWorth = (market: Market) => {
    const marketStocks = stocks[market];
    const marketBankAccounts = bankAccounts[market];
    const marketMutualFunds = mutualFunds[market];
    const marketFixedDeposits = fixedDeposits[market];
    const marketCommodities = commodities[market];
    
    // Use actualWorth (current market value) for stocks, not totalInvested
    const stocksTotal = marketStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
    const bankAccountsTotal = marketBankAccounts.reduce((sum, account) => sum + account.balance, 0);
    const mutualFundsTotal = marketMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
    // For fixed deposits, use amount invested (not maturity amount) - this is an exception
    const fixedDepositsTotal = marketFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
    // Commodities are included in net worth calculation
    const commoditiesTotal = marketCommodities.reduce((sum, commodity) => sum + commodity.currentValue, 0);
    // Insurance policies are NOT included in net worth calculation
    
    return stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
  };
  
  // Calculate total amount invested for mutual funds
  const calculateMutualFundTotal = () => {
    const navValue = parseFloat(nav) || 0;
    const unitsValue = parseFloat(units) || 0;
    return navValue * unitsValue;
  };
  
  const mutualFundTotal = calculateMutualFundTotal();
  
  const stockTotal = calculateStockTotal();
  
  // Filter assets based on selected family member
  const filterAssetsByFamilyMember = <T extends { familyMemberId?: string }>(assets: T[]): T[] => {
    if (selectedFamilyMemberFilter === "all") {
      return assets;
    }
    // Find the Self member (relationship === "Self")
    const selfMember = familyMembers.find(m => m.relationship.toLowerCase() === "self");
    
    // If selected filter is the Self member's ID, show assets with no family_member_id
    if (selfMember && selectedFamilyMemberFilter === selfMember.id) {
      return assets.filter(asset => {
        const memberId = asset.familyMemberId;
        // Asset belongs to Self if familyMemberId is null, undefined, or empty string
        return !memberId || memberId === null || memberId === undefined || memberId === "";
      });
    }
    // Show only assets assigned to the selected family member
    // Use strict comparison to ensure exact match
    return assets.filter(asset => {
      const memberId = asset.familyMemberId;
      // Only include if memberId exists and matches exactly
      if (!memberId || memberId === null || memberId === undefined || memberId === "") {
        return false;
      }
      return String(memberId).trim() === String(selectedFamilyMemberFilter).trim();
    });
  };
  
  // Helper function to get order key for asset type and market
  const getOrderKey = (assetType: string, market: Market) => `${assetType}_${market}`;
  
  // Helper function to get ordered assets
  const getOrderedAssets = <T extends { id: string }>(
    assets: T[],
    assetType: string,
    market: Market
  ): T[] => {
    const orderKey = getOrderKey(assetType, market);
    const order = assetOrder[orderKey] || [];
    
    // If no order exists, return assets as-is
    if (order.length === 0) {
      return assets;
    }
    
    // Sort assets according to order
    const ordered = [...assets].sort((a, b) => {
      const indexA = order.indexOf(a.id);
      const indexB = order.indexOf(b.id);
      
      // If both are in order, sort by order
      if (indexA !== -1 && indexB !== -1) {
        return indexA - indexB;
      }
      // If only A is in order, A comes first
      if (indexA !== -1) return -1;
      // If only B is in order, B comes first
      if (indexB !== -1) return 1;
      // If neither is in order, maintain original order
      return 0;
    });
    
    return ordered;
  };
  
  // Helper function to save order
  const saveOrder = (assetType: string, market: Market, orderedIds: string[]) => {
    const orderKey = getOrderKey(assetType, market);
    setAssetOrder((prev) => ({
      ...prev,
      [orderKey]: orderedIds,
    }));
    // Save to localStorage
    const storageKey = `asset_order_${orderKey}`;
    localStorage.setItem(storageKey, JSON.stringify(orderedIds));
  };
  
  // Helper function to load order from localStorage
  const loadOrder = (assetType: string, market: Market): string[] => {
    const orderKey = getOrderKey(assetType, market);
    const storageKey = `asset_order_${orderKey}`;
    const stored = localStorage.getItem(storageKey);
    return stored ? JSON.parse(stored) : [];
  };
  
  // Helper function to move asset up
  const moveAssetUp = <T extends { id: string }>(
    filteredAssets: T[],
    assetId: string,
    assetType: string,
    market: Market,
    setAssets: (updater: (prev: Record<Market, T[]>) => Record<Market, T[]>) => void
  ) => {
    const currentIndex = filteredAssets.findIndex(a => a.id === assetId);
    if (currentIndex <= 0) return; // Already at top
    
    // Get the order key and current order
    const orderKey = getOrderKey(assetType, market);
    const currentOrder = assetOrder[orderKey] || filteredAssets.map(a => a.id);
    
    // Find the actual indices in the order array
    const oldIndex = currentOrder.indexOf(assetId);
    const newIndex = oldIndex - 1;
    
    if (oldIndex > 0) {
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      saveOrder(assetType, market, newOrder);
      
      // Update the actual state based on the new order
      setAssets((prev) => {
        const marketAssets = [...prev[market]];
        // Reorder based on the new order
        const reordered = newOrder
          .map(id => marketAssets.find(a => a.id === id))
          .filter((a): a is T => a !== undefined)
          .concat(marketAssets.filter(a => !newOrder.includes(a.id)));
        
        return {
          ...prev,
          [market]: reordered,
        };
      });
    }
  };
  
  // Helper function to move asset down
  const moveAssetDown = <T extends { id: string }>(
    filteredAssets: T[],
    assetId: string,
    assetType: string,
    market: Market,
    setAssets: (updater: (prev: Record<Market, T[]>) => Record<Market, T[]>) => void
  ) => {
    const currentIndex = filteredAssets.findIndex(a => a.id === assetId);
    if (currentIndex >= filteredAssets.length - 1) return; // Already at bottom
    
    // Get the order key and current order
    const orderKey = getOrderKey(assetType, market);
    const currentOrder = assetOrder[orderKey] || filteredAssets.map(a => a.id);
    
    // Find the actual indices in the order array
    const oldIndex = currentOrder.indexOf(assetId);
    const newIndex = oldIndex + 1;
    
    if (oldIndex < currentOrder.length - 1) {
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      saveOrder(assetType, market, newOrder);
      
      // Update the actual state based on the new order
      setAssets((prev) => {
        const marketAssets = [...prev[market]];
        // Reorder based on the new order
        const reordered = newOrder
          .map(id => marketAssets.find(a => a.id === id))
          .filter((a): a is T => a !== undefined)
          .concat(marketAssets.filter(a => !newOrder.includes(a.id)));
        
        return {
          ...prev,
          [market]: reordered,
        };
      });
    }
  };
  
  // Handle drag end
  const handleDragEnd = (event: DragEndEvent, assetType: string, market: Market) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) {
      return;
    }
    
    const orderKey = getOrderKey(assetType, market);
    const currentOrder = assetOrder[orderKey] || [];
    
    const oldIndex = currentOrder.indexOf(active.id as string);
    const newIndex = currentOrder.indexOf(over.id as string);
    
    if (oldIndex !== -1 && newIndex !== -1) {
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
      saveOrder(assetType, market, newOrder);
    }
  };
  
  // Get filtered assets for display (with ordering applied)
  const getFilteredStocks = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(stocks[market]);
    return getOrderedAssets(filtered, "stocks", market);
  };
  const getFilteredBankAccounts = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(bankAccounts[market]);
    return getOrderedAssets(filtered, "bank_accounts", market);
  };
  const getFilteredMutualFunds = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(mutualFunds[market]);
    return getOrderedAssets(filtered, "mutual_funds", market);
  };
  const getFilteredFixedDeposits = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(fixedDeposits[market]);
    return getOrderedAssets(filtered, "fixed_deposits", market);
  };
  const getFilteredCommodities = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(commodities[market]);
    return getOrderedAssets(filtered, "commodities", market);
  };
  const getFilteredInsurancePolicies = (market: Market) => {
    const filtered = filterAssetsByFamilyMember(insurancePolicies[market]);
    return getOrderedAssets(filtered, "insurance_policies", market);
  };
  
  // Initialize drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
  // Initialize order from localStorage when assets are loaded
  useEffect(() => {
    const assetTypes = ["stocks", "bank_accounts", "mutual_funds", "fixed_deposits", "commodities", "insurance_policies"];
    const markets: Market[] = ["india", "europe"];
    const initialOrder: Record<string, string[]> = {};
    
    assetTypes.forEach(assetType => {
      markets.forEach(market => {
        const orderKey = getOrderKey(assetType, market);
        const loadedOrder = loadOrder(assetType, market);
        if (loadedOrder.length > 0) {
          initialOrder[orderKey] = loadedOrder;
        }
      });
    });
    
    if (Object.keys(initialOrder).length > 0) {
      setAssetOrder(initialOrder);
    }
  }, []);
  
  // Helper function to get family member name from familyMemberId
  const getFamilyMemberName = (familyMemberId?: string): string => {
    if (!familyMemberId || familyMemberId === null || familyMemberId === undefined || familyMemberId === "") {
      return "Self";
    }
    const member = familyMembers.find(m => m.id === familyMemberId);
    return member ? `${member.name} (${member.relationship})` : "Unknown";
  };
  
  // Calculate filtered net worth
  const calculateFilteredNetWorth = (market: Market): number => {
    const filteredStocks = getFilteredStocks(market);
    const filteredBankAccounts = getFilteredBankAccounts(market);
    const filteredMutualFunds = getFilteredMutualFunds(market);
    const filteredFixedDeposits = getFilteredFixedDeposits(market);
    const filteredCommodities = getFilteredCommodities(market);
    
    const stocksTotal = filteredStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
    const bankAccountsTotal = filteredBankAccounts.reduce((sum, account) => sum + account.balance, 0);
    const mutualFundsTotal = filteredMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
    const fixedDepositsTotal = filteredFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
    const commoditiesTotal = filteredCommodities.reduce((sum, commodity) => sum + commodity.currentValue, 0);
    
    return stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
  };
  
  // Fetch family members from database
  const fetchFamilyMembers = async () => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        return;
      }

      // Try with trailing slash first (to avoid redirect)
      let response = await fetch("/api/family-members/", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        redirect: "follow", // Follow redirects
      });

      // If 404 or other error, try without trailing slash
      if (!response.ok && response.status !== 200) {
        response = await fetch("/api/family-members", {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
          redirect: "follow",
        });
      }

      if (response.ok) {
        const members = await response.json();
        setFamilyMembers(members || []);
      } else if (response.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/";
      } else {
        console.error(`Failed to fetch family members: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error fetching family members:", error);
    }
  };

  // Note: Family member net worth calculation removed - now handled in Profile page

  // Handle PDF upload for fixed deposits
  const handleFixedDepositPdfUpload = async (file: File) => {
    setIsUploadingPdf(true);
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        alert("Please log in to upload files");
        setIsUploadingPdf(false);
        return;
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("asset_type", "fixed_deposit");
      formData.append("market", selectedMarket);

      const response = await fetch("/api/assets/upload-pdf", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (response.ok && data.success) {
        alert(data.message || `Successfully added ${data.created_count} fixed deposit(s) from PDF`);
        // Refresh assets to show the newly created fixed deposits
        await fetchAssets();
      } else {
        alert(data.message || "Failed to process PDF. Please try again.");
      }
    } catch (error) {
      console.error("Error uploading PDF:", error);
      alert("An error occurred while uploading the PDF. Please try again.");
    } finally {
      setIsUploadingPdf(false);
    }
  };

  // Function to fetch assets - made accessible for refresh callback
  const fetchAssets = async () => {
    try {
      setIsLoadingAssets(true);
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
        if (assets.length > 0) {
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
        const indiaInsurancePolicies: typeof insurancePolicies.india = [];
        const europeInsurancePolicies: typeof insurancePolicies.europe = [];
        const indiaCommodities: typeof commodities.india = [];
        const europeCommodities: typeof commodities.europe = [];
        
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
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
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
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
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
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
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
              // Do NOT calculate maturityAmount - use current_value from database if available, otherwise 0
              const maturityAmount = asset.current_value ? parseFloat(asset.current_value) : 0;
              
              const fixedDeposit = {
                id: asset.id,
                dbId: asset.id,
                bankName: asset.name,
                amountInvested: principalAmount,
                rateOfInterest: interestRate,
                duration: durationMonths,
                maturityAmount: maturityAmount, // Use value from database, not calculated
                startDate: asset.start_date || new Date().toISOString().split('T')[0],
                maturityDate: asset.maturity_date || new Date().toISOString().split('T')[0],
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
              };
              
              if (market === "india") {
                indiaFixedDeposits.push(fixedDeposit);
              } else {
                europeFixedDeposits.push(fixedDeposit);
              }
            } else if (asset.type === "insurance_policy") {
              const insurancePolicy = {
                id: asset.id,
                dbId: asset.id,
                insuranceName: asset.name,
                policyNumber: asset.policy_number || "",
                amountInsured: parseFloat(asset.amount_insured || "0"),
                issueDate: asset.issue_date || new Date().toISOString().split('T')[0],
                dateOfMaturity: asset.date_of_maturity || "",
                premium: parseFloat(asset.premium || "0"),
                nominee: asset.nominee || "",
                premiumPaymentDate: asset.premium_payment_date || "",
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
              };
              
              if (market === "india") {
                indiaInsurancePolicies.push(insurancePolicy);
              } else {
                europeInsurancePolicies.push(insurancePolicy);
              }
            } else if (asset.type === "commodity") {
              const quantity = parseFloat(asset.commodity_quantity || "0");
              const purchasePrice = parseFloat(asset.commodity_purchase_price || "0");
              const currentValue = parseFloat(asset.current_value || (quantity * purchasePrice));
              
              const commodity = {
                id: asset.id,
                dbId: asset.id,
                commodityName: asset.commodity_name || asset.name,
                form: asset.form || "",
                quantity: quantity,
                units: asset.commodity_units || "grams",
                purchaseDate: asset.commodity_purchase_date || new Date().toISOString().split('T')[0],
                purchasePrice: purchasePrice,
                currentValue: currentValue,
                familyMemberId: asset.family_member_id ? String(asset.family_member_id) : undefined,
              };
              
              if (market === "india") {
                indiaCommodities.push(commodity);
              } else {
                europeCommodities.push(commodity);
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
          
          setInsurancePolicies({
            india: indiaInsurancePolicies,
            europe: europeInsurancePolicies,
          });
          
          setCommodities({
            india: indiaCommodities,
            europe: europeCommodities,
          });
          
          // Recalculate net worth (using actualWorth for stocks, not totalInvested)
          // Insurance policies are NOT included in net worth calculation
          // Commodities are included in net worth calculation
          const indiaNetWorth = indiaStocks.reduce((sum, s) => sum + s.actualWorth, 0) +
                               indiaBankAccounts.reduce((sum, a) => sum + a.balance, 0) +
                               indiaMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0) +
                               indiaFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0) +
                               indiaCommodities.reduce((sum, c) => sum + c.currentValue, 0);
          const europeNetWorth = europeStocks.reduce((sum, s) => sum + s.actualWorth, 0) +
                                europeBankAccounts.reduce((sum, a) => sum + a.balance, 0) +
                                europeMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0) +
                                europeFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0) +
                                europeCommodities.reduce((sum, c) => sum + c.currentValue, 0);
          
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

  // Fetch assets from database on component mount
  useEffect(() => {
    fetchAssets();
    fetchFamilyMembers();
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
                                   mutualFunds.india.reduce((sum, f) => sum + f.currentWorth, 0) +
                                   fixedDeposits.india.reduce((sum, fd) => sum + fd.amountInvested, 0) +
                                   commodities.india.reduce((sum, c) => sum + c.currentValue, 0);
              const europeNetWorth = updatedStocks.europe.reduce((sum, s) => sum + s.actualWorth, 0) +
                                    bankAccounts.europe.reduce((sum, a) => sum + a.balance, 0) +
                                    mutualFunds.europe.reduce((sum, f) => sum + f.currentWorth, 0) +
                                    fixedDeposits.europe.reduce((sum, fd) => sum + fd.amountInvested, 0) +
                                    commodities.europe.reduce((sum, c) => sum + c.currentValue, 0);

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
    familyMemberId?: string;
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
      const assetData: any = {
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

      // Always set family_member_id - null for Self, or the family member ID
      assetData.family_member_id = stock.familyMemberId || null;


      if (stock.dbId) {
        // Update existing asset
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

      return true;
    } catch (error) {
      console.error("Error deleting asset from database:", error);
      return false;
    }
  };

  // Helper function to get selection key for asset type and market
  const getSelectionKey = (assetType: string, market: Market): string => {
    return `${assetType}_${market}`;
  };

  // Check if asset is selected
  const isAssetSelected = (assetId: string, assetType: string, market: Market): boolean => {
    const key = getSelectionKey(assetType, market);
    return selectedAssets[key]?.has(assetId) || false;
  };

  // Toggle asset selection
  const toggleAssetSelection = (assetId: string, assetType: string, market: Market) => {
    const key = getSelectionKey(assetType, market);
    setSelectedAssets((prev) => {
      const currentSet = prev[key] || new Set<string>();
      const newSet = new Set(currentSet);
      if (newSet.has(assetId)) {
        newSet.delete(assetId);
      } else {
        newSet.add(assetId);
      }
      return {
        ...prev,
        [key]: newSet,
      };
    });
  };

  // Select all assets of a type
  const selectAllAssets = (assetIds: string[], assetType: string, market: Market) => {
    const key = getSelectionKey(assetType, market);
    setSelectedAssets((prev) => ({
      ...prev,
      [key]: new Set(assetIds),
    }));
  };

  // Deselect all assets of a type
  const deselectAllAssets = (assetType: string, market: Market) => {
    const key = getSelectionKey(assetType, market);
    setSelectedAssets((prev) => {
      const newPrev = { ...prev };
      delete newPrev[key];
      return newPrev;
    });
  };

  // Check if all assets are selected
  const areAllAssetsSelected = (assetIds: string[], assetType: string, market: Market): boolean => {
    if (assetIds.length === 0) return false;
    const key = getSelectionKey(assetType, market);
    const selected = selectedAssets[key] || new Set<string>();
    return assetIds.every((id) => selected.has(id));
  };

  // Bulk delete selected assets
  const deleteSelectedAssets = async (assetType: string, market: Market) => {
    const key = getSelectionKey(assetType, market);
    const selected = selectedAssets[key];
    if (!selected || selected.size === 0) {
      alert("No assets selected for deletion.");
      return;
    }

    const selectedIds = Array.from(selected);
    const count = selectedIds.length;
    
    if (!window.confirm(`Are you sure you want to delete ${count} selected asset${count > 1 ? 's' : ''}? This action cannot be undone.`)) {
      return;
    }

    // Get all assets to find their dbIds
    let assetsToDelete: Array<{ id: string; dbId?: string }> = [];
    
    if (assetType === "stocks") {
      assetsToDelete = stocks[market].filter((s) => selectedIds.includes(s.id));
    } else if (assetType === "bank_accounts") {
      assetsToDelete = bankAccounts[market].filter((a) => selectedIds.includes(a.id));
    } else if (assetType === "mutual_funds") {
      assetsToDelete = mutualFunds[market].filter((f) => selectedIds.includes(f.id));
    } else if (assetType === "fixed_deposits") {
      assetsToDelete = fixedDeposits[market].filter((fd) => selectedIds.includes(fd.id));
    } else if (assetType === "insurance_policies") {
      assetsToDelete = insurancePolicies[market].filter((p) => selectedIds.includes(p.id));
    } else if (assetType === "commodities") {
      assetsToDelete = commodities[market].filter((c) => selectedIds.includes(c.id));
    }

    // Delete all selected assets
    const deletePromises = assetsToDelete.map((asset) => {
      const dbId = asset.dbId || asset.id;
      return deleteAssetFromDatabase(dbId);
    });

    const results = await Promise.all(deletePromises);
    const successCount = results.filter((r) => r === true).length;
    const failCount = results.length - successCount;

    if (successCount > 0) {
      // Refresh assets from database
      await fetchAssets();
      
      // Clear selections
      deselectAllAssets(assetType, market);
      
      if (failCount > 0) {
        alert(`Successfully deleted ${successCount} asset${successCount > 1 ? 's' : ''}. ${failCount} asset${failCount > 1 ? 's' : ''} failed to delete.`);
      }
    } else {
      alert(`Failed to delete assets. Please try again.`);
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
    familyMemberId?: string;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData: any = {
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

      // Always set family_member_id - null for Self, or the family member ID
      assetData.family_member_id = fd.familyMemberId || null;


      if (fd.dbId) {
        // Update existing asset
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
        }
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

  // Save insurance policy to database
  const saveInsurancePolicyToDatabase = async (policy: {
    id: string;
    dbId?: string;
    insuranceName: string;
    policyNumber: string;
    amountInsured: number;
    issueDate: string;
    dateOfMaturity: string;
    premium: number;
    nominee?: string;
    premiumPaymentDate?: string;
    familyMemberId?: string;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData: any = {
        name: policy.insuranceName,
        type: "insurance_policy",
        currency: currency,
        policy_number: policy.policyNumber,
        amount_insured: policy.amountInsured.toString(),
        issue_date: policy.issueDate,
        date_of_maturity: policy.dateOfMaturity,
        premium: policy.premium.toString(),
        current_value: policy.amountInsured.toString(), // Use amount insured as current value
        is_active: true,
      };

      if (policy.nominee) {
        assetData.nominee = policy.nominee;
      }
      if (policy.premiumPaymentDate) {
        assetData.premium_payment_date = policy.premiumPaymentDate;
      }
      // Always set family_member_id - null for Self, or the family member ID
      assetData.family_member_id = policy.familyMemberId || null;


      if (policy.dbId) {
        // Update existing asset
        const response = await fetch(`/api/assets/${policy.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Failed to update insurance policy" }));
          console.error(`Failed to update insurance policy: ${errorData.detail || response.statusText}`, errorData);
          throw new Error(errorData.detail || "Failed to update insurance policy");
        }

        const updatedAsset = await response.json();
        return updatedAsset.id;
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

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Failed to create insurance policy" }));
          console.error(`Failed to create insurance policy: ${errorData.detail || response.statusText}`, errorData);
          throw new Error(errorData.detail || "Failed to create insurance policy");
        }

        const createdAsset = await response.json();
        return createdAsset.id;
      }
    } catch (error) {
      console.error("Error saving insurance policy to database:", error);
      throw error;
    }
  };

  // Save commodity to database
  const saveCommodityToDatabase = async (commodity: {
    id: string;
    dbId?: string;
    commodityName: string;
    form: string;
    quantity: number;
    units: string;
    purchaseDate: string;
    purchasePrice: number;
    currentValue: number;
    familyMemberId?: string;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData: any = {
        name: commodity.commodityName,
        type: "commodity",
        currency: currency,
        commodity_name: commodity.commodityName,
        form: commodity.form,
        commodity_quantity: commodity.quantity.toString(),
        commodity_units: commodity.units,
        commodity_purchase_date: commodity.purchaseDate,
        commodity_purchase_price: commodity.purchasePrice.toString(),
        current_value: commodity.currentValue.toString(),
        is_active: true,
      };

      // Always set family_member_id - null for Self, or the family member ID
      assetData.family_member_id = commodity.familyMemberId || null;


      if (commodity.dbId) {
        // Update existing asset
        const response = await fetch(`/api/assets/${commodity.dbId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(assetData),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Failed to update commodity" }));
          console.error(`Failed to update commodity: ${errorData.detail || response.statusText}`, errorData);
          throw new Error(errorData.detail || "Failed to update commodity");
        }

        const updatedAsset = await response.json();
        return updatedAsset.id;
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

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Failed to create commodity" }));
          console.error(`Failed to create commodity: ${errorData.detail || response.statusText}`, errorData);
          throw new Error(errorData.detail || "Failed to create commodity");
        }

        const createdAsset = await response.json();
        return createdAsset.id;
      }
    } catch (error) {
      console.error("Error saving commodity to database:", error);
      throw error;
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
    familyMemberId?: string;
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
        // Always set family_member_id - null for Self, or the family member ID
        family_member_id: fund.familyMemberId || null,
      };


      if (fund.dbId) {
        // Update existing asset
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
        }
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
    familyMemberId?: string;
  }, market: Market) => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) return;

      const currency = marketConfig[market].currency;
      const assetData: any = {
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

      // Always set family_member_id - null for Self, or the family member ID
      assetData.family_member_id = account.familyMemberId || null;


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
        }
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
    <main className="h-screen flex flex-col relative">
      {/* PDF Upload Loading Overlay */}
      {isUploadingPdf && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 flex flex-col items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mb-4"></div>
            <p className="text-gray-700 font-medium">Processing PDF...</p>
            <p className="text-sm text-gray-500 mt-2">Extracting fixed deposit information</p>
          </div>
        </div>
      )}
      
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
            {/* Family Member Filter Dropdown */}
            {familyMembers.length > 0 && (
              <div className="flex items-center space-x-2">
                <label htmlFor="family-member-filter" className="text-sm font-medium text-gray-700">
                  Filter by:
                </label>
                  <select
                    id="family-member-filter"
                    value={selectedFamilyMemberFilter}
                    onChange={(e) => setSelectedFamilyMemberFilter(e.target.value as string | "all")}
                    className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  >
                    <option value="all">All Family Members</option>
                    {familyMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name} ({member.relationship})
                      </option>
                    ))}
                  </select>
              </div>
            )}
            <button
              onClick={() => (window.location.href = "/expenses")}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            >
              Expense Tracker
            </button>
            <button
              onClick={() => (window.location.href = "/profile")}
              className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900"
            >
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
                {/* Total Family Net Worth Section */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                        {selectedFamilyMemberFilter === "all" 
                          ? "Total Family Net Worth" 
                          : familyMembers.find(m => m.id === selectedFamilyMemberFilter) 
                            ? `${familyMembers.find(m => m.id === selectedFamilyMemberFilter)?.name}'s Net Worth`
                            : "Net Worth"}
                      </h3>
                      <p className="text-xs text-gray-400 mt-1">
                        {selectedFamilyMemberFilter === "all" 
                          ? "Combined" 
                          : "Filtered View"}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="flex items-baseline space-x-2">
                        <p className="text-3xl font-bold text-gray-900">
                          {currentMarket.symbol}
                          {calculateFilteredNetWorth(selectedMarket).toLocaleString("en-IN", {
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
                        {getFilteredStocks(selectedMarket).length > 0 && (
                          <div className="mb-4 flex items-center justify-between">
                            <label className="flex items-center space-x-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={areAllAssetsSelected(
                                  getFilteredStocks(selectedMarket).map(s => s.id),
                                  "stocks",
                                  selectedMarket
                                )}
                                onChange={(e) => {
                                  const filteredStocks = getFilteredStocks(selectedMarket);
                                  if (e.target.checked) {
                                    selectAllAssets(filteredStocks.map(s => s.id), "stocks", selectedMarket);
                                  } else {
                                    deselectAllAssets("stocks", selectedMarket);
                                  }
                                }}
                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-700">Select All</span>
                            </label>
                            <button
                              onClick={() => deleteSelectedAssets("stocks", selectedMarket)}
                              disabled={
                                !selectedAssets[getSelectionKey("stocks", selectedMarket)] ||
                                selectedAssets[getSelectionKey("stocks", selectedMarket)]?.size === 0
                              }
                              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Delete Selected ({selectedAssets[getSelectionKey("stocks", selectedMarket)]?.size || 0})
                            </button>
                          </div>
                        )}
                        {getFilteredStocks(selectedMarket).length === 0 ? (
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
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("stock");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Stock
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-stock-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  // Placeholder for future functionality
                                  if (e.target.files && e.target.files[0]) {
                                    console.log("PDF selected for stocks:", e.target.files[0]);
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-stock-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {getFilteredStocks(selectedMarket).length} {getFilteredStocks(selectedMarket).length === 1 ? "Stock" : "Stocks"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-stock-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    // Placeholder for future functionality
                                    if (e.target.files && e.target.files[0]) {
                                      console.log("PDF selected for stocks:", e.target.files[0]);
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-stock-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
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
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredStocks(selectedMarket);
                                const orderKey = getOrderKey("stocks", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(s => s.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("stocks", selectedMarket, newOrder);
                                  
                                  // Update stocks state to match the new order
                                  setStocks((prev) => {
                                    const marketStocks = [...prev[selectedMarket]];
                                    // Reorder based on the new order, preserving items not in order
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketStocks.find(s => s.id === id))
                                      .filter((s): s is typeof marketStocks[0] => s !== undefined);
                                    const unordered = marketStocks.filter(s => !orderedIds.has(s.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredStocks(selectedMarket).map(s => s.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredStocks(selectedMarket).map((stock, index) => {
                                    const filteredStocks = getFilteredStocks(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredStocks.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={stock.id}
                                        id={stock.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors">
                                          <div className="flex items-start justify-between mb-3">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(stock.id, "stocks", selectedMarket)}
                                                onChange={() => toggleAssetSelection(stock.id, "stocks", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
                                              <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                  <h4 className="text-sm font-semibold text-gray-900">
                                                    {stock.name}
                                                  </h4>
                                                {selectedFamilyMemberFilter === "all" && (
                                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                                                    {getFamilyMemberName(stock.familyMemberId)}
                                                  </span>
                                                )}
                                                </div>
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
                                            </div>
                                            <div className="flex items-center space-x-1">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredStocks,
                                                    stock.id,
                                                    "stocks",
                                                    selectedMarket,
                                                    setStocks
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredStocks,
                                                    stock.id,
                                                    "stocks",
                                                    selectedMarket,
                                                    setStocks
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
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
                                                  setSelectedFamilyMemberId(stock.familyMemberId);
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
                                                        const updatedCommodities = commodities[selectedMarket];
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
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
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "bank_accounts" && (
                      <div>
                        {getFilteredBankAccounts(selectedMarket).length > 0 && (
                          <div className="mb-4 flex items-center justify-between">
                            <label className="flex items-center space-x-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={areAllAssetsSelected(
                                  getFilteredBankAccounts(selectedMarket).map(a => a.id),
                                  "bank_accounts",
                                  selectedMarket
                                )}
                                onChange={(e) => {
                                  const filteredAccounts = getFilteredBankAccounts(selectedMarket);
                                  if (e.target.checked) {
                                    selectAllAssets(filteredAccounts.map(a => a.id), "bank_accounts", selectedMarket);
                                  } else {
                                    deselectAllAssets("bank_accounts", selectedMarket);
                                  }
                                }}
                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-700">Select All</span>
                            </label>
                            <button
                              onClick={() => deleteSelectedAssets("bank_accounts", selectedMarket)}
                              disabled={
                                !selectedAssets[getSelectionKey("bank_accounts", selectedMarket)] ||
                                selectedAssets[getSelectionKey("bank_accounts", selectedMarket)]?.size === 0
                              }
                              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Delete Selected ({selectedAssets[getSelectionKey("bank_accounts", selectedMarket)]?.size || 0})
                            </button>
                          </div>
                        )}
                        {getFilteredBankAccounts(selectedMarket).length === 0 ? (
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
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("bank_account");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Bank Account
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-bank-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  // Placeholder for future functionality
                                  if (e.target.files && e.target.files[0]) {
                                    console.log("PDF selected for bank accounts:", e.target.files[0]);
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-bank-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {getFilteredBankAccounts(selectedMarket).length} {getFilteredBankAccounts(selectedMarket).length === 1 ? "Bank Account" : "Bank Accounts"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-bank-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    // Placeholder for future functionality
                                    if (e.target.files && e.target.files[0]) {
                                      console.log("PDF selected for bank accounts:", e.target.files[0]);
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-bank-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
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
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredBankAccounts(selectedMarket);
                                const orderKey = getOrderKey("bank_accounts", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(a => a.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("bank_accounts", selectedMarket, newOrder);
                                  
                                  // Update bank accounts state to match the new order
                                  setBankAccounts((prev) => {
                                    const marketAccounts = [...prev[selectedMarket]];
                                    // Reorder based on the new order, preserving items not in order
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketAccounts.find(a => a.id === id))
                                      .filter((a): a is typeof marketAccounts[0] => a !== undefined);
                                    const unordered = marketAccounts.filter(a => !orderedIds.has(a.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredBankAccounts(selectedMarket).map(a => a.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredBankAccounts(selectedMarket).map((account, index) => {
                                    const filteredAccounts = getFilteredBankAccounts(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredAccounts.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={account.id}
                                        id={account.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors">
                                          <div className="flex items-start justify-between mb-3">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(account.id, "bank_accounts", selectedMarket)}
                                                onChange={() => toggleAssetSelection(account.id, "bank_accounts", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
                                              <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                  <h4 className="text-sm font-semibold text-gray-900">
                                                    {account.bankName}
                                                  </h4>
                                                {selectedFamilyMemberFilter === "all" && (
                                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                                                    {getFamilyMemberName(account.familyMemberId)}
                                                  </span>
                                                )}
                                                </div>
                                                {account.accountNumber && (
                                                  <p className="text-xs text-gray-600 mb-1">
                                                    Account: {account.accountNumber}
                                                  </p>
                                                )}
                                              </div>
                                            </div>
                                            <div className="flex items-center space-x-1">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredAccounts,
                                                    account.id,
                                                    "bank_accounts",
                                                    selectedMarket,
                                                    setBankAccounts
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredAccounts,
                                                    account.id,
                                                    "bank_accounts",
                                                    selectedMarket,
                                                    setBankAccounts
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
                                              <button
                                                onClick={() => {
                                                  setEditingBankAccountId(account.id);
                                                  setSelectedAssetType("bank_account");
                                                  setBankName(account.bankName);
                                                  setAccountNumber(account.accountNumber || "");
                                                  setBankBalance(account.balance.toString());
                                                  setSelectedFamilyMemberId(account.familyMemberId);
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
                                                        const updatedCommodities = commodities[selectedMarket];
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
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
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "mutual_funds" && (
                      <div>
                        {getFilteredMutualFunds(selectedMarket).length > 0 && (
                          <div className="mb-4 flex items-center justify-between">
                            <label className="flex items-center space-x-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={areAllAssetsSelected(
                                  getFilteredMutualFunds(selectedMarket).map(f => f.id),
                                  "mutual_funds",
                                  selectedMarket
                                )}
                                onChange={(e) => {
                                  const filteredFunds = getFilteredMutualFunds(selectedMarket);
                                  if (e.target.checked) {
                                    selectAllAssets(filteredFunds.map(f => f.id), "mutual_funds", selectedMarket);
                                  } else {
                                    deselectAllAssets("mutual_funds", selectedMarket);
                                  }
                                }}
                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-700">Select All</span>
                            </label>
                            <button
                              onClick={() => deleteSelectedAssets("mutual_funds", selectedMarket)}
                              disabled={
                                !selectedAssets[getSelectionKey("mutual_funds", selectedMarket)] ||
                                selectedAssets[getSelectionKey("mutual_funds", selectedMarket)]?.size === 0
                              }
                              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Delete Selected ({selectedAssets[getSelectionKey("mutual_funds", selectedMarket)]?.size || 0})
                            </button>
                          </div>
                        )}
                        {getFilteredMutualFunds(selectedMarket).length === 0 ? (
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
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("mutual_fund");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Mutual Fund
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-fund-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  // Placeholder for future functionality
                                  if (e.target.files && e.target.files[0]) {
                                    console.log("PDF selected for mutual funds:", e.target.files[0]);
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-fund-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {mutualFunds[selectedMarket].length} {mutualFunds[selectedMarket].length === 1 ? "Mutual Fund" : "Mutual Funds"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-fund-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    // Placeholder for future functionality
                                    if (e.target.files && e.target.files[0]) {
                                      console.log("PDF selected for mutual funds:", e.target.files[0]);
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-fund-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
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
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredMutualFunds(selectedMarket);
                                const orderKey = getOrderKey("mutual_funds", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(f => f.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("mutual_funds", selectedMarket, newOrder);
                                  
                                  // Update mutual funds state to match the new order
                                  setMutualFunds((prev) => {
                                    const marketFunds = [...prev[selectedMarket]];
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketFunds.find(f => f.id === id))
                                      .filter((f): f is typeof marketFunds[0] => f !== undefined);
                                    const unordered = marketFunds.filter(f => !orderedIds.has(f.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredMutualFunds(selectedMarket).map(f => f.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredMutualFunds(selectedMarket).map((fund, index) => {
                                    const filteredFunds = getFilteredMutualFunds(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredFunds.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={fund.id}
                                        id={fund.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors">
                                          <div className="flex items-start justify-between mb-3">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(fund.id, "mutual_funds", selectedMarket)}
                                                onChange={() => toggleAssetSelection(fund.id, "mutual_funds", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
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
                                            </div>
                                            <div className="flex items-center space-x-1">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredFunds,
                                                    fund.id,
                                                    "mutual_funds",
                                                    selectedMarket,
                                                    setMutualFunds
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredFunds,
                                                    fund.id,
                                                    "mutual_funds",
                                                    selectedMarket,
                                                    setMutualFunds
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
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
                                                        const updatedCommodities = commodities[selectedMarket];
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
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
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "fixed_deposits" && (
                      <div>
                        {getFilteredFixedDeposits(selectedMarket).length > 0 && (
                          <div className="mb-4 flex items-center justify-between">
                            <label className="flex items-center space-x-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={areAllAssetsSelected(
                                  getFilteredFixedDeposits(selectedMarket).map(fd => fd.id),
                                  "fixed_deposits",
                                  selectedMarket
                                )}
                                onChange={(e) => {
                                  const filteredFDs = getFilteredFixedDeposits(selectedMarket);
                                  if (e.target.checked) {
                                    selectAllAssets(filteredFDs.map(fd => fd.id), "fixed_deposits", selectedMarket);
                                  } else {
                                    deselectAllAssets("fixed_deposits", selectedMarket);
                                  }
                                }}
                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-700">Select All</span>
                            </label>
                            <button
                              onClick={() => deleteSelectedAssets("fixed_deposits", selectedMarket)}
                              disabled={
                                !selectedAssets[getSelectionKey("fixed_deposits", selectedMarket)] ||
                                selectedAssets[getSelectionKey("fixed_deposits", selectedMarket)]?.size === 0
                              }
                              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Delete Selected ({selectedAssets[getSelectionKey("fixed_deposits", selectedMarket)]?.size || 0})
                            </button>
                          </div>
                        )}
                        {getFilteredFixedDeposits(selectedMarket).length === 0 ? (
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
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("fixed_deposit");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Fixed Deposit
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-fd-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  if (e.target.files && e.target.files[0]) {
                                    handleFixedDepositPdfUpload(e.target.files[0]);
                                    // Reset input so the same file can be selected again
                                    e.target.value = '';
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-fd-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {getFilteredFixedDeposits(selectedMarket).length} {getFilteredFixedDeposits(selectedMarket).length === 1 ? "Fixed Deposit" : "Fixed Deposits"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-fd-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    if (e.target.files && e.target.files[0]) {
                                      handleFixedDepositPdfUpload(e.target.files[0]);
                                      // Reset input so the same file can be selected again
                                      e.target.value = '';
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-fd-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
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
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredFixedDeposits(selectedMarket);
                                const orderKey = getOrderKey("fixed_deposits", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(fd => fd.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("fixed_deposits", selectedMarket, newOrder);
                                  
                                  // Update fixed deposits state to match the new order
                                  setFixedDeposits((prev) => {
                                    const marketFDs = [...prev[selectedMarket]];
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketFDs.find(fd => fd.id === id))
                                      .filter((fd): fd is typeof marketFDs[0] => fd !== undefined);
                                    const unordered = marketFDs.filter(fd => !orderedIds.has(fd.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredFixedDeposits(selectedMarket).map(fd => fd.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredFixedDeposits(selectedMarket).map((fd, index) => {
                                    const maturityDate = new Date(fd.maturityDate);
                                    const isMatured = maturityDate < new Date();
                                    const filteredFDs = getFilteredFixedDeposits(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredFDs.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={fd.id}
                                        id={fd.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors">
                                          <div className="flex items-start justify-between mb-3">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(fd.id, "fixed_deposits", selectedMarket)}
                                                onChange={() => toggleAssetSelection(fd.id, "fixed_deposits", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
                                              <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                  <h4 className="text-sm font-semibold text-gray-900">
                                                    {fd.bankName}
                                                  </h4>
                                                {selectedFamilyMemberFilter === "all" && (
                                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                                                    {getFamilyMemberName(fd.familyMemberId)}
                                                  </span>
                                                )}
                                                </div>
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
                                                  <span>Start: {formatDateDDMMYYYY(fd.startDate)}</span>
                                                  <span className="ml-4">Maturity: {formatDateDDMMYYYY(fd.maturityDate)}</span>
                                                  {isMatured && (
                                                    <span className="ml-2 text-green-600 font-medium">(Matured)</span>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                            <div className="flex items-center space-x-1">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredFDs,
                                                    fd.id,
                                                    "fixed_deposits",
                                                    selectedMarket,
                                                    setFixedDeposits
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredFDs,
                                                    fd.id,
                                                    "fixed_deposits",
                                                    selectedMarket,
                                                    setFixedDeposits
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
                                              <button
                                                onClick={() => {
                                                  setEditingFixedDepositId(fd.id);
                                                  setSelectedAssetType("fixed_deposit");
                                                  setFdBankName(fd.bankName);
                                                  setFdAmount(fd.amountInvested.toString());
                                                  setFdRate(fd.rateOfInterest.toString());
                                                  setFdDuration(fd.duration.toString());
                                                  setFdStartDate(fd.startDate || new Date().toISOString().split('T')[0]);
                                                  setSelectedFamilyMemberId(fd.familyMemberId);
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
                                                        const updatedCommodities = commodities[selectedMarket];
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
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
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "insurance_policies" && (
                      <div>
                        {getFilteredInsurancePolicies(selectedMarket).length === 0 ? (
                          <div className="text-center py-12">
                            <div className="mx-auto h-16 w-16 mb-4 flex items-center justify-center bg-gray-100 rounded-full">
                              <span className="text-3xl font-semibold text-gray-600">
                                {currentMarket.symbol}
                              </span>
                            </div>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Insurance Policies Added</h3>
                            <p className="text-gray-500 mb-4">
                              Track your insurance policies and coverage details
                            </p>
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("insurance_policy");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Insurance Policy
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-policy-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  // Placeholder for future functionality
                                  if (e.target.files && e.target.files[0]) {
                                    console.log("PDF selected for insurance policies:", e.target.files[0]);
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-policy-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {getFilteredInsurancePolicies(selectedMarket).length} {getFilteredInsurancePolicies(selectedMarket).length === 1 ? "Insurance Policy" : "Insurance Policies"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-policy-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    // Placeholder for future functionality
                                    if (e.target.files && e.target.files[0]) {
                                      console.log("PDF selected for insurance policies:", e.target.files[0]);
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-policy-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedAssetType("insurance_policy");
                                    setIsAddAssetModalOpen(true);
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                                >
                                  + Add Insurance Policy
                                </button>
                              </div>
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredInsurancePolicies(selectedMarket);
                                const orderKey = getOrderKey("insurance_policies", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(p => p.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("insurance_policies", selectedMarket, newOrder);
                                  
                                  // Update insurance policies state to match the new order
                                  setInsurancePolicies((prev) => {
                                    const marketPolicies = [...prev[selectedMarket]];
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketPolicies.find(p => p.id === id))
                                      .filter((p): p is typeof marketPolicies[0] => p !== undefined);
                                    const unordered = marketPolicies.filter(p => !orderedIds.has(p.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredInsurancePolicies(selectedMarket).map(p => p.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredInsurancePolicies(selectedMarket).map((policy, index) => {
                                    const maturityDate = policy.dateOfMaturity ? new Date(policy.dateOfMaturity) : null;
                                    const isMatured = maturityDate && maturityDate < new Date();
                                    const filteredPolicies = getFilteredInsurancePolicies(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredPolicies.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={policy.id}
                                        id={policy.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors">
                                          <div className="flex items-start justify-between mb-3">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(policy.id, "insurance_policies", selectedMarket)}
                                                onChange={() => toggleAssetSelection(policy.id, "insurance_policies", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
                                              <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                  <h4 className="text-sm font-semibold text-gray-900">
                                                    {policy.insuranceName}
                                                  </h4>
                                                {selectedFamilyMemberFilter === "all" && (
                                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                                                    {getFamilyMemberName(policy.familyMemberId)}
                                                  </span>
                                                )}
                                                </div>
                                                <div className="flex items-center space-x-4 text-xs text-gray-600">
                                                  <span>Policy #: {policy.policyNumber}</span>
                                                  {policy.nominee && <span>Nominee: {policy.nominee}</span>}
                                                </div>
                                                <div className="mt-2 text-xs text-gray-500">
                                                  <span>Issue Date: {formatDateDDMMYYYY(policy.issueDate)}</span>
                                                  {maturityDate && (
                                                    <>
                                                      <span className="ml-4">Maturity: {formatDateDDMMYYYY(policy.dateOfMaturity || "")}</span>
                                                      {isMatured && (
                                                        <span className="ml-2 text-green-600 font-medium">(Matured)</span>
                                                      )}
                                                    </>
                                                  )}
                                                  {policy.premiumPaymentDate && (
                                                    <span className="ml-4">Next Premium: {formatDateDDMMYYYY(policy.premiumPaymentDate)}</span>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                            <div className="flex items-center space-x-1">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredPolicies,
                                                    policy.id,
                                                    "insurance_policies",
                                                    selectedMarket,
                                                    setInsurancePolicies
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredPolicies,
                                                    policy.id,
                                                    "insurance_policies",
                                                    selectedMarket,
                                                    setInsurancePolicies
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
                                              <button
                                                onClick={() => {
                                                  setEditingInsurancePolicyId(policy.id);
                                                  setSelectedAssetType("insurance_policy");
                                                  setInsuranceName(policy.insuranceName);
                                                  setPolicyNumber(policy.policyNumber);
                                                  setAmountInsured(policy.amountInsured.toString());
                                                  setIssueDate(policy.issueDate);
                                                  setDateOfMaturity(policy.dateOfMaturity);
                                                  setPremium(policy.premium.toString());
                                                  setNominee(policy.nominee || "");
                                                  setPremiumPaymentDate(policy.premiumPaymentDate || "");
                                                  setIsAddAssetModalOpen(true);
                                                }}
                                                className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                                title="Edit insurance policy"
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
                                                  if (window.confirm(`Are you sure you want to delete ${policy.insuranceName} insurance policy? This action cannot be undone.`)) {
                                                    const dbId = policy.dbId || policy.id;
                                                    const deleted = await deleteAssetFromDatabase(dbId);
                                                    
                                                    if (deleted) {
                                                      // Remove from state
                                                      setInsurancePolicies((prev) => {
                                                        const updatedPolicies = prev[selectedMarket].filter(p => p.id !== policy.id);
                                                        
                                                        // Recalculate net worth
                                                        const updatedStocks = stocks[selectedMarket];
                                                        const updatedBankAccounts = bankAccounts[selectedMarket];
                                                        const updatedMutualFunds = mutualFunds[selectedMarket];
                                                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                                                        const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                        const updatedCommodities = commodities[selectedMarket];
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        // Insurance policies are NOT included in net worth calculation
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
                                                        setNetWorth((prev) => ({
                                                          ...prev,
                                                          [selectedMarket]: newNetWorth,
                                                        }));
                                                        
                                                        return {
                                                          ...prev,
                                                          [selectedMarket]: updatedPolicies,
                                                        };
                                                      });
                                                    } else {
                                                      alert("Failed to delete insurance policy. Please try again.");
                                                    }
                                                  }
                                                }}
                                                className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                                title="Delete insurance policy"
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
                                              <p className="text-xs text-gray-500 mb-1">Amount Insured</p>
                                              <p className="text-sm font-semibold text-gray-900">
                                                {currentMarket.symbol}
                                                {policy.amountInsured.toLocaleString("en-IN", {
                                                  minimumFractionDigits: 2,
                                                  maximumFractionDigits: 2,
                                                })}
                                              </p>
                                            </div>
                                            <div className="text-right">
                                              <p className="text-xs text-gray-500 mb-1">Premium</p>
                                              <p className="text-sm font-semibold text-gray-900">
                                                {currentMarket.symbol}
                                                {policy.premium.toLocaleString("en-IN", {
                                                  minimumFractionDigits: 2,
                                                  maximumFractionDigits: 2,
                                                })}
                                              </p>
                                            </div>
                                          </div>
                                        </div>
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "commodities" && (
                      <div>
                        {getFilteredCommodities(selectedMarket).length > 0 && (
                          <div className="mb-4 flex items-center justify-between">
                            <label className="flex items-center space-x-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={areAllAssetsSelected(
                                  getFilteredCommodities(selectedMarket).map(c => c.id),
                                  "commodities",
                                  selectedMarket
                                )}
                                onChange={(e) => {
                                  const filteredCommodities = getFilteredCommodities(selectedMarket);
                                  if (e.target.checked) {
                                    selectAllAssets(filteredCommodities.map(c => c.id), "commodities", selectedMarket);
                                  } else {
                                    deselectAllAssets("commodities", selectedMarket);
                                  }
                                }}
                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                              />
                              <span className="text-sm text-gray-700">Select All</span>
                            </label>
                            <button
                              onClick={() => deleteSelectedAssets("commodities", selectedMarket)}
                              disabled={
                                !selectedAssets[getSelectionKey("commodities", selectedMarket)] ||
                                selectedAssets[getSelectionKey("commodities", selectedMarket)]?.size === 0
                              }
                              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Delete Selected ({selectedAssets[getSelectionKey("commodities", selectedMarket)]?.size || 0})
                            </button>
                          </div>
                        )}
                        {getFilteredCommodities(selectedMarket).length === 0 ? (
                          <div className="text-center py-12">
                            <div className="mx-auto h-16 w-16 mb-4 flex items-center justify-center bg-gray-100 rounded-full">
                              <span className="text-3xl font-semibold text-gray-600">
                                {currentMarket.symbol}
                              </span>
                            </div>
                            <h3 className="text-lg font-medium text-gray-900 mb-2">No Commodities Added</h3>
                            <p className="text-gray-500 mb-4">
                              Track your commodities like gold, silver, etc.
                            </p>
                            <div className="flex items-center gap-2 justify-center">
                              <button
                                onClick={() => {
                                  setSelectedAssetType("commodity");
                                  setIsAddAssetModalOpen(true);
                                }}
                                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                              >
                                Add Commodity
                              </button>
                              <input
                                type="file"
                                id="pdf-upload-commodity-empty"
                                accept=".pdf"
                                className="hidden"
                                onChange={(e) => {
                                  // Placeholder for future functionality
                                  if (e.target.files && e.target.files[0]) {
                                    console.log("PDF selected for commodities:", e.target.files[0]);
                                  }
                                }}
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const input = document.getElementById("pdf-upload-commodity-empty") as HTMLInputElement;
                                  input?.click();
                                }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-2"
                                title="Upload PDF"
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
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                  />
                                </svg>
                                Upload PDF
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="text-sm font-medium text-gray-700">
                                {getFilteredCommodities(selectedMarket).length} {getFilteredCommodities(selectedMarket).length === 1 ? "Commodity" : "Commodities"}
                              </h3>
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id="pdf-upload-commodity-header"
                                  accept=".pdf"
                                  className="hidden"
                                  onChange={(e) => {
                                    // Placeholder for future functionality
                                    if (e.target.files && e.target.files[0]) {
                                      console.log("PDF selected for commodities:", e.target.files[0]);
                                    }
                                  }}
                                />
                                <button
                                  type="button"
                                  onClick={() => {
                                    const input = document.getElementById("pdf-upload-commodity-header") as HTMLInputElement;
                                    input?.click();
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors flex items-center gap-1.5"
                                  title="Upload PDF"
                                >
                                  <svg
                                    className="h-3.5 w-3.5"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                                    />
                                  </svg>
                                  Upload PDF
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedAssetType("commodity");
                                    setIsAddAssetModalOpen(true);
                                  }}
                                  className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                                >
                                  + Add Commodity
                                </button>
                              </div>
                            </div>
                            <DndContext
                              sensors={sensors}
                              collisionDetection={closestCenter}
                              onDragEnd={(e) => {
                                if (!e.over) return;
                                
                                const filtered = getFilteredCommodities(selectedMarket);
                                const orderKey = getOrderKey("commodities", selectedMarket);
                                const currentOrder = assetOrder[orderKey] || filtered.map(c => c.id);
                                
                                const oldIndex = currentOrder.indexOf(e.active.id as string);
                                const newIndex = currentOrder.indexOf(e.over.id as string);
                                
                                if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
                                  const newOrder = arrayMove(currentOrder, oldIndex, newIndex);
                                  saveOrder("commodities", selectedMarket, newOrder);
                                  
                                  // Update commodities state to match the new order
                                  setCommodities((prev) => {
                                    const marketCommodities = [...prev[selectedMarket]];
                                    const orderedIds = new Set(newOrder);
                                    const reordered = newOrder
                                      .map(id => marketCommodities.find(c => c.id === id))
                                      .filter((c): c is typeof marketCommodities[0] => c !== undefined);
                                    const unordered = marketCommodities.filter(c => !orderedIds.has(c.id));
                                    
                                    return {
                                      ...prev,
                                      [selectedMarket]: [...reordered, ...unordered],
                                    };
                                  });
                                }
                              }}
                            >
                              <SortableContext
                                items={getFilteredCommodities(selectedMarket).map(c => c.id)}
                                strategy={verticalListSortingStrategy}
                              >
                                <div className="space-y-2">
                                  {getFilteredCommodities(selectedMarket).map((commodity, index) => {
                                    const filteredCommodities = getFilteredCommodities(selectedMarket);
                                    const isFirst = index === 0;
                                    const isLast = index === filteredCommodities.length - 1;
                                    
                                    return (
                                      <SortableItem
                                        key={commodity.id}
                                        id={commodity.id}
                                        dragHandle={
                                          <div className="px-2 text-gray-400 hover:text-gray-600">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                            </svg>
                                          </div>
                                        }
                                      >
                                        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                                          <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3 flex-1">
                                              <input
                                                type="checkbox"
                                                checked={isAssetSelected(commodity.id, "commodities", selectedMarket)}
                                                onChange={() => toggleAssetSelection(commodity.id, "commodities", selectedMarket)}
                                                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 cursor-pointer"
                                                onClick={(e) => e.stopPropagation()}
                                              />
                                              <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                  <h4 className="text-base font-semibold text-gray-900">
                                                    {commodity.commodityName}
                                                  </h4>
                                                {selectedFamilyMemberFilter === "all" && (
                                                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full">
                                                    {getFamilyMemberName(commodity.familyMemberId)}
                                                  </span>
                                                )}
                                                </div>
                                                <div className="space-y-1 text-sm text-gray-600">
                                                  <p>
                                                    <span className="font-medium">Form:</span> {commodity.form}
                                                  </p>
                                                  <p>
                                                    <span className="font-medium">Quantity:</span> {commodity.quantity.toLocaleString("en-IN", {
                                                      minimumFractionDigits: 2,
                                                      maximumFractionDigits: 4,
                                                    })} {commodity.units}
                                                  </p>
                                                  <p>
                                                    <span className="font-medium">Purchase Date:</span> {formatDateDDMMYYYY(commodity.purchaseDate)}
                                                  </p>
                                                  <p>
                                                    <span className="font-medium">Purchase Price:</span> {currentMarket.symbol}
                                                    {commodity.purchasePrice.toLocaleString("en-IN", {
                                                      minimumFractionDigits: 2,
                                                      maximumFractionDigits: 2,
                                                    })}
                                                  </p>
                                                </div>
                                              </div>
                                            </div>
                                            <div className="flex items-center gap-2 ml-4">
                                              {/* Up/Down buttons */}
                                              <div className="flex flex-col mr-1">
                                                <button
                                                  onClick={() => moveAssetUp(
                                                    filteredCommodities,
                                                    commodity.id,
                                                    "commodities",
                                                    selectedMarket,
                                                    setCommodities
                                                  )}
                                                  disabled={isFirst}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move up"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                                  </svg>
                                                </button>
                                                <button
                                                  onClick={() => moveAssetDown(
                                                    filteredCommodities,
                                                    commodity.id,
                                                    "commodities",
                                                    selectedMarket,
                                                    setCommodities
                                                  )}
                                                  disabled={isLast}
                                                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                                  title="Move down"
                                                >
                                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                  </svg>
                                                </button>
                                              </div>
                                              <button
                                                onClick={() => {
                                                  setEditingCommodityId(commodity.id);
                                                  setSelectedAssetType("commodity");
                                                  setCommodityName(commodity.commodityName);
                                                  setCommodityForm(commodity.form);
                                                  setCommodityQuantity(commodity.quantity.toString());
                                                  setCommodityUnits(commodity.units);
                                                  setCommodityPurchaseDate(commodity.purchaseDate);
                                                  setCommodityPurchasePrice(commodity.purchasePrice.toString());
                                                  setSelectedFamilyMemberId(commodity.familyMemberId);
                                                  setIsAddAssetModalOpen(true);
                                                }}
                                                className="ml-2 p-1.5 text-gray-400 hover:text-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded transition-colors"
                                                title="Edit commodity"
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
                                                  if (window.confirm(`Are you sure you want to delete ${commodity.commodityName} commodity? This action cannot be undone.`)) {
                                                    const dbId = commodity.dbId || commodity.id;
                                                    const deleted = await deleteAssetFromDatabase(dbId);
                                                    
                                                    if (deleted) {
                                                      // Remove from state
                                                      setCommodities((prev) => {
                                                        const updatedCommodities = prev[selectedMarket].filter(c => c.id !== commodity.id);
                                                        
                                                        // Recalculate net worth
                                                        const updatedStocks = stocks[selectedMarket];
                                                        const updatedBankAccounts = bankAccounts[selectedMarket];
                                                        const updatedMutualFunds = mutualFunds[selectedMarket];
                                                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                                                        const stocksTotal = updatedStocks.reduce((sum, s) => sum + s.actualWorth, 0);
                                                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, a) => sum + a.balance, 0);
                                                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, f) => sum + f.currentWorth, 0);
                                                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                                                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                                                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                                                        
                                                        setNetWorth((prev) => ({
                                                          ...prev,
                                                          [selectedMarket]: newNetWorth,
                                                        }));
                                                        
                                                        return {
                                                          ...prev,
                                                          [selectedMarket]: updatedCommodities,
                                                        };
                                                      });
                                                    } else {
                                                      alert("Failed to delete commodity. Please try again.");
                                                    }
                                                  }
                                                }}
                                                className="p-1.5 text-gray-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 rounded transition-colors"
                                                title="Delete commodity"
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
                                              <p className="text-xs text-gray-500 mb-1">Current Value</p>
                                              <p className="text-sm font-semibold text-gray-900">
                                                {currentMarket.symbol}
                                                {commodity.currentValue.toLocaleString("en-IN", {
                                                  minimumFractionDigits: 2,
                                                  maximumFractionDigits: 2,
                                                })}
                                              </p>
                                            </div>
                                          </div>
                                        </div>
                                      </SortableItem>
                                    );
                                  })}
                                </div>
                              </SortableContext>
                            </DndContext>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          }
          right={<ChatWindow context="assets" onAssetCreated={fetchAssets} />}
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
                  {editingStockId || editingBankAccountId || editingMutualFundId || editingFixedDepositId || editingInsurancePolicyId || editingCommodityId ? "Edit Asset" : "Add New Asset"}
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
                            familyMemberId: selectedFamilyMemberId,
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
                          const updatedCommodities = commodities[selectedMarket];
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
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
                        familyMemberId: selectedFamilyMemberId,
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
                        const updatedCommodities = commodities[selectedMarket];
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
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
                            familyMemberId: selectedFamilyMemberId,
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
                          const updatedCommodities = commodities[selectedMarket];
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
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
                            familyMemberId: selectedFamilyMemberId,
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
                        const updatedCommodities = commodities[selectedMarket];
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
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
                            familyMemberId: selectedFamilyMemberId,
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
                          const updatedCommodities = commodities[selectedMarket];
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
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
                        familyMemberId: selectedFamilyMemberId,
                      };
                      
                      // Save to database
                      const dbId = await saveMutualFundToDatabase({ ...newMutualFund, purchaseDate: mutualFundPurchaseDate, familyMemberId: selectedFamilyMemberId } as any, selectedMarket);
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
                        const updatedCommodities = commodities[selectedMarket];
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
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
                    // Do NOT calculate maturityAmount - use 0 (will be set by user if needed)
                    const maturityAmount = 0;
                    
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
                          const updatedCommodities = commodities[selectedMarket];
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
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
                        familyMemberId: selectedFamilyMemberId,
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
                        const updatedCommodities = commodities[selectedMarket];
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
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
                  } else if (selectedAssetType === "insurance_policy") {
                    const amountInsuredValue = parseFloat(amountInsured) || 0;
                    const premiumValue = parseFloat(premium) || 0;
                    
                    if (editingInsurancePolicyId) {
                      // Update existing insurance policy
                      setInsurancePolicies((prev) => {
                        const marketPolicies = prev[selectedMarket];
                        const policyIndex = marketPolicies.findIndex(p => p.id === editingInsurancePolicyId);
                        
                        if (policyIndex >= 0) {
                          // Update the policy
                          const updatedPolicies = [...marketPolicies];
                          updatedPolicies[policyIndex] = {
                            ...marketPolicies[policyIndex],
                            insuranceName: insuranceName,
                            policyNumber: policyNumber,
                            amountInsured: amountInsuredValue,
                            issueDate: issueDate,
                            dateOfMaturity: dateOfMaturity,
                            premium: premiumValue,
                            nominee: nominee || undefined,
                            premiumPaymentDate: premiumPaymentDate || undefined,
                          };
                          
                          // Save to database (async, but don't wait)
                          saveInsurancePolicyToDatabase({ ...updatedPolicies[policyIndex], familyMemberId: selectedFamilyMemberId } as any, selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated policies
                          const updatedStocks = stocks[selectedMarket];
                          const updatedBankAccounts = bankAccounts[selectedMarket];
                          const updatedMutualFunds = mutualFunds[selectedMarket];
                          const updatedFixedDeposits = fixedDeposits[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const updatedCommodities = commodities[selectedMarket];
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          // Insurance policies are NOT included in net worth calculation
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedPolicies,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingInsurancePolicyId(null);
                    } else {
                      // Add new insurance policy
                      const tempId = `insurance-policy-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                      const newInsurancePolicy: typeof insurancePolicies.india[0] = {
                        id: tempId,
                        insuranceName: insuranceName,
                        policyNumber: policyNumber,
                        amountInsured: amountInsuredValue,
                        issueDate: issueDate,
                        dateOfMaturity: dateOfMaturity,
                        premium: premiumValue,
                        nominee: nominee || undefined,
                        premiumPaymentDate: premiumPaymentDate || undefined,
                        familyMemberId: selectedFamilyMemberId,
                      };
                      
                      // Save to database
                      try {
                        const dbId = await saveInsurancePolicyToDatabase({ ...newInsurancePolicy, familyMemberId: selectedFamilyMemberId } as any, selectedMarket);
                        if (dbId && typeof dbId === 'string') {
                          newInsurancePolicy.dbId = dbId;
                          newInsurancePolicy.id = dbId; // Use database ID as the main ID
                        }
                      } catch (error) {
                        console.error("Error saving insurance policy:", error);
                        alert("Failed to save insurance policy. Please try again.");
                        return; // Don't add to state if save failed
                      }
                      
                      setInsurancePolicies((prev) => {
                        const updatedPolicies = [...prev[selectedMarket], newInsurancePolicy];
                        
                        // Calculate new net worth with updated policies
                        const updatedStocks = stocks[selectedMarket];
                        const updatedBankAccounts = bankAccounts[selectedMarket];
                        const updatedMutualFunds = mutualFunds[selectedMarket];
                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const updatedCommodities = commodities[selectedMarket];
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        // Insurance policies are NOT included in net worth calculation
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedPolicies,
                        };
                      });
                    }
                  } else if (selectedAssetType === "commodity") {
                    const quantityValue = parseFloat(commodityQuantity) || 0;
                    const purchasePriceValue = parseFloat(commodityPurchasePrice) || 0;
                    const currentValue = quantityValue * purchasePriceValue; // For now, use purchase price * quantity as current value
                    
                    if (editingCommodityId) {
                      // Update existing commodity
                      setCommodities((prev) => {
                        const marketCommodities = prev[selectedMarket];
                        const commodityIndex = marketCommodities.findIndex(c => c.id === editingCommodityId);
                        
                        if (commodityIndex >= 0) {
                          // Update the commodity
                          const updatedCommodities = [...marketCommodities];
                          updatedCommodities[commodityIndex] = {
                            ...marketCommodities[commodityIndex],
                            commodityName: commodityName,
                            form: commodityForm,
                            quantity: quantityValue,
                            units: commodityUnits,
                            purchaseDate: commodityPurchaseDate,
                            purchasePrice: purchasePriceValue,
                            currentValue: currentValue,
                            familyMemberId: selectedFamilyMemberId,
                          };
                          
                          // Save to database (async, but don't wait)
                          saveCommodityToDatabase(updatedCommodities[commodityIndex], selectedMarket).catch(console.error);
                          
                          // Calculate new net worth with updated commodities
                          const updatedStocks = stocks[selectedMarket];
                          const updatedBankAccounts = bankAccounts[selectedMarket];
                          const updatedMutualFunds = mutualFunds[selectedMarket];
                          const updatedFixedDeposits = fixedDeposits[selectedMarket];
                          const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                          const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                          const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                          const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                          const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                          const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                          
                          setNetWorth((prev) => ({
                            ...prev,
                            [selectedMarket]: newNetWorth,
                          }));
                          
                          return {
                            ...prev,
                            [selectedMarket]: updatedCommodities,
                          };
                        }
                        return prev;
                      });
                      
                      setEditingCommodityId(null);
                    } else {
                      // Add new commodity
                      const tempId = `commodity-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                      const newCommodity: typeof commodities.india[0] = {
                        id: tempId,
                        commodityName: commodityName,
                        form: commodityForm,
                        quantity: quantityValue,
                        units: commodityUnits,
                        purchaseDate: commodityPurchaseDate,
                        purchasePrice: purchasePriceValue,
                        currentValue: currentValue,
                        familyMemberId: selectedFamilyMemberId,
                      };
                      
                      // Save to database
                      try {
                        const dbId = await saveCommodityToDatabase({ ...newCommodity, familyMemberId: selectedFamilyMemberId } as any, selectedMarket);
                        if (dbId && typeof dbId === 'string') {
                          newCommodity.dbId = dbId;
                          newCommodity.id = dbId; // Use database ID as the main ID
                        }
                      } catch (error) {
                        console.error("Error saving commodity:", error);
                        alert("Failed to save commodity. Please try again.");
                        return; // Don't add to state if save failed
                      }
                      
                      setCommodities((prev) => {
                        const updatedCommodities = [...prev[selectedMarket], newCommodity];
                        
                        // Calculate new net worth with updated commodities
                        const updatedStocks = stocks[selectedMarket];
                        const updatedBankAccounts = bankAccounts[selectedMarket];
                        const updatedMutualFunds = mutualFunds[selectedMarket];
                        const updatedFixedDeposits = fixedDeposits[selectedMarket];
                        const stocksTotal = updatedStocks.reduce((sum, stock) => sum + stock.actualWorth, 0);
                        const bankAccountsTotal = updatedBankAccounts.reduce((sum, account) => sum + account.balance, 0);
                        const mutualFundsTotal = updatedMutualFunds.reduce((sum, fund) => sum + fund.currentWorth, 0);
                        const fixedDepositsTotal = updatedFixedDeposits.reduce((sum, fd) => sum + fd.amountInvested, 0);
                        const commoditiesTotal = updatedCommodities.reduce((sum, c) => sum + c.currentValue, 0);
                        const newNetWorth = stocksTotal + bankAccountsTotal + mutualFundsTotal + fixedDepositsTotal + commoditiesTotal;
                        
                        setNetWorth((prev) => ({
                          ...prev,
                          [selectedMarket]: newNetWorth,
                        }));
                        
                        return {
                          ...prev,
                          [selectedMarket]: updatedCommodities,
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
                  setInsuranceName("");
                  setPolicyNumber("");
                  setAmountInsured("");
                  setIssueDate(new Date().toISOString().split('T')[0]);
                  setDateOfMaturity("");
                  setPremium("");
                  setNominee("");
                  setPremiumPaymentDate("");
                  setEditingStockId(null);
                  setEditingBankAccountId(null);
                  setEditingMutualFundId(null);
                  setEditingFixedDepositId(null);
                  setEditingInsurancePolicyId(null);
                  setEditingCommodityId(null);
                  setCommodityName("");
                  setCommodityForm("");
                  setCommodityQuantity("");
                  setCommodityUnits("grams");
                  setCommodityPurchaseDate(new Date().toISOString().split('T')[0]);
                  setCommodityPurchasePrice("");
                  setSelectedFamilyMemberId(undefined);
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
                    
                    {/* Maturity Amount calculation removed - do not calculate */}
                  </div>
                )}

                {/* Insurance Policy-specific fields */}
                {selectedAssetType === "insurance_policy" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="insurance-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Insurance Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="insurance-name"
                        value={insuranceName}
                        onChange={(e) => setInsuranceName(e.target.value)}
                        required
                        placeholder="e.g., Life Insurance, Health Insurance"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="policy-number"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Policy Number <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="policy-number"
                        value={policyNumber}
                        onChange={(e) => setPolicyNumber(e.target.value)}
                        required
                        placeholder="Enter policy number"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="amount-insured"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Amount Insured ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="amount-insured"
                        value={amountInsured}
                        onChange={(e) => setAmountInsured(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter coverage amount"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="issue-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Issue Date <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="issue-date"
                        value={issueDate}
                        onChange={(e) => setIssueDate(e.target.value)}
                        required
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="date-of-maturity"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Date of Maturity <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="date-of-maturity"
                        value={dateOfMaturity}
                        onChange={(e) => setDateOfMaturity(e.target.value)}
                        required
                        min={issueDate}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="premium"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Premium ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="premium"
                        value={premium}
                        onChange={(e) => setPremium(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter premium amount"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="nominee"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Nominee
                      </label>
                      <input
                        type="text"
                        id="nominee"
                        value={nominee}
                        onChange={(e) => setNominee(e.target.value)}
                        placeholder="Enter nominee name (optional)"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="premium-payment-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Premium Payment Date
                      </label>
                      <input
                        type="date"
                        id="premium-payment-date"
                        value={premiumPaymentDate}
                        onChange={(e) => setPremiumPaymentDate(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                  </div>
                )}

                {/* Commodity-specific fields */}
                {selectedAssetType === "commodity" && (
                  <div className="space-y-4">
                    <div>
                      <label
                        htmlFor="commodity-name"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Commodity Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="commodity-name"
                        value={commodityName}
                        onChange={(e) => setCommodityName(e.target.value)}
                        required
                        placeholder="e.g., Gold, Silver"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="commodity-form"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Form <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        id="commodity-form"
                        value={commodityForm}
                        onChange={(e) => setCommodityForm(e.target.value)}
                        required
                        placeholder="e.g., ETF, Physical, Coin"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="commodity-quantity"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Quantity <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="commodity-quantity"
                        value={commodityQuantity}
                        onChange={(e) => setCommodityQuantity(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter quantity"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="commodity-units"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Units <span className="text-red-500">*</span>
                      </label>
                      <select
                        id="commodity-units"
                        value={commodityUnits}
                        onChange={(e) => setCommodityUnits(e.target.value)}
                        required
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      >
                        <option value="grams">Grams</option>
                        <option value="karat">Karat</option>
                        <option value="units">Units</option>
                      </select>
                    </div>
                    
                    <div>
                      <label
                        htmlFor="commodity-purchase-date"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Purchase Date <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="date"
                        id="commodity-purchase-date"
                        value={commodityPurchaseDate}
                        onChange={(e) => setCommodityPurchaseDate(e.target.value)}
                        required
                        max={new Date().toISOString().split('T')[0]}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                    
                    <div>
                      <label
                        htmlFor="commodity-purchase-price"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Purchase Price ({currentMarket.symbol}) <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        id="commodity-purchase-price"
                        value={commodityPurchasePrice}
                        onChange={(e) => setCommodityPurchasePrice(e.target.value)}
                        step="0.01"
                        min="0"
                        required
                        placeholder="Enter purchase price per unit"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                      />
                    </div>
                  </div>
                )}

                {/* Family Member Assignment (for all asset types) */}
                <div className="pt-4 border-t border-gray-200">
                  <label
                    htmlFor="asset-family-member"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Assign to Family Member <span className="text-gray-400 text-xs">(Optional)</span>
                  </label>
                  <select
                    id="asset-family-member"
                    value={selectedFamilyMemberId || ""}
                    onChange={(e) => setSelectedFamilyMemberId(e.target.value || undefined)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  >
                    {familyMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name} ({member.relationship})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Form Actions */}
                <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
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
                      setInsuranceName("");
                      setPolicyNumber("");
                      setAmountInsured("");
                      setIssueDate(new Date().toISOString().split('T')[0]);
                      setDateOfMaturity("");
                      setPremium("");
                      setNominee("");
                      setPremiumPaymentDate("");
                      setEditingStockId(null);
                      setEditingBankAccountId(null);
                      setEditingMutualFundId(null);
                      setEditingFixedDepositId(null);
                      setEditingInsurancePolicyId(null);
                      setSelectedFamilyMemberId(undefined);
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

