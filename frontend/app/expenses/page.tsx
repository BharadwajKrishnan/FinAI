"use client";

import { useState, useEffect } from "react";
import ResizablePanel from "@/components/ResizablePanel";
import ChatWindow from "@/components/ChatWindow";

type Expense = {
  id: string;
  description: string;
  amount: number;
  currency: string;
  category?: string;
  expense_date: string;
  notes?: string;
  family_member_id?: string;
  created_at: string;
  updated_at: string;
};

type MonthlySummary = {
  month: number;
  month_name: string;
  total: number;
  count: number;
  expenses: Expense[];
};

type ExpenseSummary = {
  year: number;
  total: number;
  monthly_summary: MonthlySummary[];
};

const categoryOptions = [
  "Food",
  "Transport",
  "Shopping",
  "Bills",
  "Entertainment",
  "Healthcare",
  "Education",
  "Travel",
  "Other",
];

const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

type Currency = "EUR" | "INR";

export default function ExpensesPage() {
  const currentDate = new Date();
  const [selectedYear, setSelectedYear] = useState<number>(currentDate.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number>(currentDate.getMonth() + 1);
  const [selectedCurrency, setSelectedCurrency] = useState<Currency>("EUR");
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [isAddExpenseModalOpen, setIsAddExpenseModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null);
  const [monthTotal, setMonthTotal] = useState<number>(0);
  
  // Family members state (for expense assignment and filtering)
  const [familyMembers, setFamilyMembers] = useState<Array<{
    id: string;
    name: string;
    relationship: string;
    notes?: string;
  }>>([]);
  
  // Family member filter for expenses
  const [selectedFamilyMemberFilter, setSelectedFamilyMemberFilter] = useState<string | "all">("all");
  
  // Selected family member for expense form
  const [selectedFamilyMemberId, setSelectedFamilyMemberId] = useState<string | undefined>(undefined);

  // Helper function to format date as YYYY-MM-DD without timezone issues
  const formatDateString = (year: number, month: number, day: number) => {
    const monthStr = String(month).padStart(2, '0');
    const dayStr = String(day).padStart(2, '0');
    return `${year}-${monthStr}-${dayStr}`;
  };

  // Helper function to get default date (defined before useState to avoid issues)
  const getInitialDate = () => {
    const today = new Date();
    const todayYear = today.getFullYear();
    const todayMonth = today.getMonth() + 1;
    const todayDay = today.getDate();
    
    if (selectedYear === todayYear && selectedMonth === todayMonth) {
      return formatDateString(todayYear, todayMonth, todayDay);
    } else {
      return formatDateString(selectedYear, selectedMonth, 1);
    }
  };

  // Form state - initialize with default date based on selected month/year
  const [formData, setFormData] = useState(() => {
    return {
      description: "",
      amount: "",
      currency: "EUR",
      category: "",
      expense_date: getInitialDate(),
      notes: "",
    };
  });
  
  // Fetch family members from database
  const fetchFamilyMembers = async () => {
    try {
      const accessToken = getAuthToken();
      if (!accessToken) return;

      const response = await fetch("/api/family-members", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const members = await response.json();
        setFamilyMembers(members || []);
      } else if (response.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/";
      }
    } catch (error) {
      console.error("Error fetching family members:", error);
    }
  };
  
  // Filter expenses based on selected family member
  const filterExpensesByFamilyMember = (expensesList: Expense[]): Expense[] => {
    if (selectedFamilyMemberFilter === "all") {
      return expensesList;
    }
    if (selectedFamilyMemberFilter === "") {
      // Show only unassigned expenses (Self) - expenses with no family_member_id
      return expensesList.filter(expense => {
        const memberId = expense.family_member_id;
        // Expense belongs to Self if family_member_id is null, undefined, or empty string
        return !memberId || memberId === null || memberId === undefined || memberId === "";
      });
    }
    // Show only expenses assigned to the selected family member
    // Use strict comparison to ensure exact match
    return expensesList.filter(expense => {
      const memberId = expense.family_member_id;
      // Only include if memberId exists and matches exactly
      if (!memberId || memberId === null || memberId === undefined || memberId === "") {
        return false;
      }
      return String(memberId).trim() === String(selectedFamilyMemberFilter).trim();
    });
  };
  
  // Helper function to get family member name from familyMemberId
  const getFamilyMemberName = (familyMemberId?: string): string => {
    if (!familyMemberId || familyMemberId === null || familyMemberId === undefined || familyMemberId === "") {
      return "Self";
    }
    const member = familyMembers.find(m => m.id === familyMemberId);
    return member ? `${member.name} (${member.relationship})` : "Unknown";
  };
  
  // Get filtered expenses for display
  const getFilteredExpenses = (): Expense[] => {
    return filterExpensesByFamilyMember(expenses);
  };

  const getAuthToken = () => {
    return localStorage.getItem("access_token");
  };

  // Helper function to get default date for the selected month/year
  const getDefaultDate = () => {
    // Use the first day of the selected month/year, or today if today is in that month
    const today = new Date();
    const todayYear = today.getFullYear();
    const todayMonth = today.getMonth() + 1;
    const todayDay = today.getDate();
    
    // If the selected month/year is the current month/year, use today's date
    if (selectedYear === todayYear && selectedMonth === todayMonth) {
      return formatDateString(todayYear, todayMonth, todayDay);
    } else {
      // Use the first day of the selected month
      return formatDateString(selectedYear, selectedMonth, 1);
    }
  };

  const fetchExpenses = async () => {
    const token = getAuthToken();
    if (!token) {
      console.error("No auth token found");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/expenses?year=${selectedYear}&month=${selectedMonth}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Failed to fetch expenses");
      }

      const data = await response.json();
      
      // Debug: Log fetched data
      console.log(`Fetched expenses for ${selectedMonth}/${selectedYear}:`, data);
      console.log(`Number of expenses fetched: ${data.length}`);
      if (data.length > 0) {
        console.log("Sample expense:", data[0]);
        console.log("Sample expense date:", data[0].expense_date);
        console.log("Sample expense family_member_id:", data[0].family_member_id);
      }
      
      // Ensure family_member_id is properly parsed (convert null to undefined for consistency)
      const parsedExpenses = data.map((expense: any) => ({
        ...expense,
        family_member_id: expense.family_member_id ? String(expense.family_member_id) : undefined,
      }));
      
      // Show all expenses (don't filter by currency)
      setExpenses(parsedExpenses);
      
      // Calculate total for all expenses in the selected currency (filtering by family member happens in display)
      const total = parsedExpenses
        .filter((expense: Expense) => expense.currency === selectedCurrency)
        .reduce((sum: number, expense: Expense) => sum + parseFloat(expense.amount.toString()), 0);
      setMonthTotal(total);
      
      console.log(`Total expenses in ${selectedCurrency}: ${total}`);
    } catch (error) {
      console.error("Error fetching expenses:", error);
      setExpenses([]);
      setMonthTotal(0);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch expenses when filters change
  useEffect(() => {
    fetchExpenses();
  }, [selectedYear, selectedMonth, selectedCurrency]);

  // Fetch family members on initial mount (only once)
  useEffect(() => {
    fetchFamilyMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Update form currency and date when selectedCurrency/month/year changes (only if not editing)
  useEffect(() => {
    if (!editingExpense) {
      setFormData(prev => ({ 
        ...prev, 
        currency: selectedCurrency,
        expense_date: getDefaultDate()
      }));
    }
  }, [selectedCurrency, selectedMonth, selectedYear, editingExpense]);

  const handleAddExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAuthToken();
    if (!token) {
      alert("Please login to add expenses");
      return;
    }

    setIsLoading(true);
    try {
      // Ensure the date is in the correct format (YYYY-MM-DD) and matches selected month/year
      let expenseDate = formData.expense_date;
      
      // For new expenses, always ensure the date is in the selected month/year
      if (!editingExpense) {
        const dateParts = expenseDate.split('-');
        if (dateParts.length === 3) {
          const dateYear = parseInt(dateParts[0]);
          const dateMonth = parseInt(dateParts[1]);
          const dateDay = parseInt(dateParts[2]);
          
          // If the date is not in the selected month/year, correct it
          if (dateYear !== selectedYear || dateMonth !== selectedMonth) {
            // Use the first day of the selected month, or today if it's the current month
            const today = new Date();
            if (selectedYear === today.getFullYear() && selectedMonth === today.getMonth() + 1) {
              expenseDate = formatDateString(today.getFullYear(), today.getMonth() + 1, today.getDate());
            } else {
              expenseDate = formatDateString(selectedYear, selectedMonth, 1);
            }
            console.log("Date corrected from", formData.expense_date, "to", expenseDate, "to match selected month/year:", selectedMonth, selectedYear);
          }
        } else {
          // Invalid date format, use default
          expenseDate = getDefaultDate();
          console.log("Invalid date format, using default:", expenseDate);
        }
      }
      
      const expenseData: any = {
        ...formData,
        amount: parseFloat(formData.amount),
        currency: editingExpense ? formData.currency : selectedCurrency, // Use selectedCurrency for new expenses, keep original for edits
        expense_date: expenseDate, // Use corrected date
      };
      
      // Always set family_member_id - null for Self, or the family member ID
      expenseData.family_member_id = selectedFamilyMemberId || null;

      // Debug: Log expense data being sent
      console.log("Saving expense:", expenseData);
      console.log("Selected month/year:", selectedMonth, selectedYear);

      const url = editingExpense
        ? `/api/expenses/${editingExpense.id}`
        : "/api/expenses";
      const method = editingExpense ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(expenseData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Failed to save expense");
      }

      const savedExpense = await response.json();
      console.log("Expense saved successfully:", savedExpense);
      console.log("Saved expense date:", savedExpense.expense_date);
      console.log("Saved expense currency:", savedExpense.currency);
      console.log("Expected month/year:", selectedMonth, selectedYear);
      console.log("Selected currency:", selectedCurrency);
      
      // Parse the saved expense date to verify it's in the correct month
      if (savedExpense.expense_date) {
        const savedDate = new Date(savedExpense.expense_date);
        const savedMonth = savedDate.getMonth() + 1;
        const savedYear = savedDate.getFullYear();
        console.log("Parsed saved date - Month:", savedMonth, "Year:", savedYear);
        console.log("Date matches selected month/year:", savedMonth === selectedMonth && savedYear === selectedYear);
      }

      // Reset form
      setFormData({
        description: "",
        amount: "",
        currency: selectedCurrency,
        category: "",
        expense_date: getDefaultDate(),
        notes: "",
      });
      setSelectedFamilyMemberId(undefined);
      setEditingExpense(null);
      setIsAddExpenseModalOpen(false);
      
      // Refresh expenses list immediately after adding/updating
      console.log("Refreshing expenses list...");
      await fetchExpenses();
      console.log("Expenses list refreshed");
    } catch (error: any) {
      console.error("Error saving expense:", error);
      alert(error.message || "Failed to save expense");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteExpense = async (expenseId: string) => {
    if (!confirm("Are you sure you want to delete this expense?")) {
      return;
    }

    const token = getAuthToken();
    if (!token) {
      alert("Please login to delete expenses");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`/api/expenses/${expenseId}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to delete expense");
      }

      // Refresh expenses list after deletion
      await fetchExpenses();
    } catch (error) {
      console.error("Error deleting expense:", error);
      alert("Failed to delete expense");
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditExpense = (expense: Expense) => {
    setEditingExpense(expense);
    setFormData({
      description: expense.description,
      amount: expense.amount.toString(),
      currency: expense.currency, // Keep original currency when editing
      category: expense.category || "",
      expense_date: expense.expense_date,
      notes: expense.notes || "",
    });
    setSelectedFamilyMemberId(expense.family_member_id);
    setIsAddExpenseModalOpen(true);
  };

  const formatCurrency = (amount: number | string, currency?: string) => {
    const currencyToUse = currency || selectedCurrency;
    const symbols: Record<string, string> = {
      INR: "₹",
      EUR: "€",
    };
    const symbol = symbols[currencyToUse] || currencyToUse;
    // Convert to number if it's a string
    const numAmount = typeof amount === "string" ? parseFloat(amount) : amount;
    return `${symbol}${numAmount.toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getYears = () => {
    const currentYear = new Date().getFullYear();
    const years = [];
    for (let i = currentYear; i >= currentYear - 5; i--) {
      years.push(i);
    }
    return years;
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Expense Tracker</h1>
            <p className="text-sm text-gray-600">Track and manage your daily expenses</p>
          </div>
          <div className="flex items-center space-x-4">
            {/* Month Selection */}
            <div className="flex items-center space-x-2">
              <label htmlFor="month-select" className="text-sm font-medium text-gray-700">
                Month:
              </label>
              <select
                id="month-select"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(parseInt(e.target.value))}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              >
                {monthNames.map((month, index) => (
                  <option key={index + 1} value={index + 1}>
                    {month}
                  </option>
                ))}
              </select>
            </div>
            {/* Year Selection */}
            <div className="flex items-center space-x-2">
              <label htmlFor="year-select" className="text-sm font-medium text-gray-700">
                Year:
              </label>
              <select
                id="year-select"
                value={selectedYear}
                onChange={(e) => setSelectedYear(parseInt(e.target.value))}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              >
                {getYears().map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
            {/* Currency Selection */}
            <div className="flex items-center space-x-2">
              <label htmlFor="currency-select" className="text-sm font-medium text-gray-700">
                Currency:
              </label>
              <select
                id="currency-select"
                value={selectedCurrency}
                onChange={(e) => setSelectedCurrency(e.target.value as Currency)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
              >
                <option value="EUR">Euro (€)</option>
                <option value="INR">Indian Rupee (₹)</option>
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
                  onChange={(e) => {
                    setSelectedFamilyMemberFilter(e.target.value as string | "all");
                  }}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                >
                  <option value="all">All Family Members</option>
                  <option value="">Self</option>
                  {familyMembers.map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.name} ({member.relationship})
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button
              onClick={() => (window.location.href = "/assets")}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            >
              Financial Assets
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

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <ResizablePanel
          left={
            <div className="h-full bg-gray-50 p-8 overflow-y-auto">
              <div className="max-w-6xl mx-auto">
                {/* Summary Card */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-gray-900">
                      {selectedFamilyMemberFilter === "all"
                        ? `${monthNames[selectedMonth - 1]} ${selectedYear} - All Family`
                        : selectedFamilyMemberFilter === ""
                        ? `${monthNames[selectedMonth - 1]} ${selectedYear} - Self`
                        : familyMembers.find(m => m.id === selectedFamilyMemberFilter)
                          ? `${monthNames[selectedMonth - 1]} ${selectedYear} - ${familyMembers.find(m => m.id === selectedFamilyMemberFilter)?.name}`
                          : `${monthNames[selectedMonth - 1]} ${selectedYear}`}
                    </h2>
                    <div className="text-2xl font-bold text-primary-600">
                      {formatCurrency(
                        getFilteredExpenses()
                          .filter((e: Expense) => e.currency === selectedCurrency)
                          .reduce((sum: number, expense: Expense) => sum + parseFloat(expense.amount.toString()), 0)
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">
                    {getFilteredExpenses().length} expense{getFilteredExpenses().length !== 1 ? "s" : ""} for this month
                    {getFilteredExpenses().filter((e: Expense) => e.currency === selectedCurrency).length !== getFilteredExpenses().length && (
                      <span className="ml-2 text-gray-500">
                        ({getFilteredExpenses().filter((e: Expense) => e.currency === selectedCurrency).length} in {selectedCurrency === "EUR" ? "€" : "₹"})
                      </span>
                    )}
                  </p>
                </div>

                {/* Expenses List */}
                {isLoading ? (
                  <div className="text-center py-12">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                    <p className="mt-2 text-gray-600">Loading expenses...</p>
                  </div>
                ) : getFilteredExpenses().length > 0 ? (
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                    <div className="p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-medium text-gray-900">
                          Expenses
                        </h3>
                        <button
                          onClick={() => {
                            setEditingExpense(null);
                            setSelectedFamilyMemberId(undefined);
                            setFormData({
                              description: "",
                              amount: "",
                              currency: selectedCurrency,
                              category: "",
                              expense_date: getDefaultDate(),
                              notes: "",
                            });
                            setIsAddExpenseModalOpen(true);
                          }}
                          className="px-4 py-2 text-sm font-medium bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                        >
                          + Add Expense
                        </button>
                      </div>
                      <div className="space-y-3">
                        {getFilteredExpenses().map((expense) => (
                          <div
                            key={expense.id}
                            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                          >
                            <div className="flex-1">
                              <div className="flex items-center space-x-3">
                                <h4 className="font-medium text-gray-900">
                                  {expense.description}
                                </h4>
                                {expense.category && (
                                  <span className="px-2 py-1 text-xs font-medium bg-primary-100 text-primary-800 rounded-full">
                                    {expense.category}
                                  </span>
                                )}
                                {selectedFamilyMemberFilter === "all" && (
                                  <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-full">
                                    {getFamilyMemberName(expense.family_member_id)}
                                  </span>
                                )}
                              </div>
                              <div className="mt-1 flex items-center space-x-4 text-sm text-gray-600">
                                <span>{formatDate(expense.expense_date)}</span>
                                {expense.notes && (
                                  <span className="text-gray-500">
                                    {expense.notes}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center space-x-4">
                              <div className="text-right">
                                <div className="font-semibold text-gray-900">
                                  {formatCurrency(expense.amount, expense.currency)}
                                </div>
                              </div>
                              <button
                                onClick={() => handleEditExpense(expense)}
                                className="p-2 text-gray-600 hover:text-primary-600 transition-colors"
                                title="Edit expense"
                              >
                                <svg
                                  className="w-5 h-5"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
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
                                onClick={() => handleDeleteExpense(expense.id)}
                                className="p-2 text-gray-600 hover:text-red-600 transition-colors"
                                title="Delete expense"
                              >
                                <svg
                                  className="w-5 h-5"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
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
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
                    <svg
                      className="mx-auto h-12 w-12 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <h3 className="mt-4 text-lg font-medium text-gray-900">No expenses for this month</h3>
                    <p className="mt-2 text-sm text-gray-500">
                      Start tracking your expenses by adding your first expense for {monthNames[selectedMonth - 1]} {selectedYear}.
                    </p>
                    <button
                      onClick={() => {
                        setEditingExpense(null);
                        setSelectedFamilyMemberId(undefined);
                        setFormData({
                          description: "",
                          amount: "",
                          currency: selectedCurrency,
                          category: "",
                          expense_date: getDefaultDate(),
                          notes: "",
                        });
                        setIsAddExpenseModalOpen(true);
                      }}
                      className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
                    >
                      + Add Expense
                    </button>
                  </div>
                )}
              </div>
            </div>
          }
          right={<ChatWindow context="expenses" />}
        />
      </div>

      {/* Add/Edit Expense Modal */}
      {isAddExpenseModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {editingExpense ? "Edit Expense" : "Add New Expense"}
                </h2>
                <button
                  onClick={() => {
                    setIsAddExpenseModalOpen(false);
                    setEditingExpense(null);
                    setSelectedFamilyMemberId(undefined);
                    setFormData({
                      description: "",
                      amount: "",
                      currency: selectedCurrency,
                      category: "",
                      expense_date: getDefaultDate(),
                      notes: "",
                    });
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              <form onSubmit={handleAddExpense} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({ ...formData, description: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="e.g., Lunch at restaurant"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Amount ({selectedCurrency === "EUR" ? "€" : "₹"}) *
                  </label>
                  <input
                    type="number"
                    required
                    step="0.01"
                    min="0"
                    value={formData.amount}
                    onChange={(e) =>
                      setFormData({ ...formData, amount: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="0.00"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Currency: {selectedCurrency === "EUR" ? "Euro (€)" : "Indian Rupee (₹)"}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Category
                    </label>
                    <select
                      value={formData.category}
                      onChange={(e) =>
                        setFormData({ ...formData, category: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="">Select category</option>
                      {categoryOptions.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Date *
                    </label>
                    <input
                      type="date"
                      required
                      value={formData.expense_date}
                      onChange={(e) =>
                        setFormData({ ...formData, expense_date: e.target.value })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="Additional notes (optional)"
                  />
                </div>

                {/* Family Member Assignment (Optional) */}
                <div className="pt-4 border-t border-gray-200">
                  <label
                    htmlFor="expense-family-member"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Assign to Family Member <span className="text-gray-400 text-xs">(Optional)</span>
                  </label>
                  <select
                    id="expense-family-member"
                    value={selectedFamilyMemberId || ""}
                    onChange={(e) => setSelectedFamilyMemberId(e.target.value || undefined)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                  >
                    <option value="">Self</option>
                    {familyMembers.map((member) => (
                      <option key={member.id} value={member.id}>
                        {member.name} ({member.relationship})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddExpenseModalOpen(false);
                      setEditingExpense(null);
                      setSelectedFamilyMemberId(undefined);
                      setFormData({
                        description: "",
                        amount: "",
                        currency: selectedCurrency,
                        category: "",
                        expense_date: getDefaultDate(),
                        notes: "",
                      });
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? "Saving..." : editingExpense ? "Update" : "Add"} Expense
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
