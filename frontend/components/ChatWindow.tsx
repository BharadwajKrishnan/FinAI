"use client";

import { useState, useRef, useEffect } from "react";
import MarkdownRenderer from "./MarkdownRenderer";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatWindowProps {
  context?: "assets" | "expenses"; // Context to determine which system prompt to use
  onAssetCreated?: () => void; // Callback to refresh assets when an asset is created, updated, or deleted
}

interface PasswordModalProps {
  onConfirm: (isPasswordProtected: boolean, password?: string) => void;
  onCancel: () => void;
}

function PasswordModal({ onConfirm, onCancel }: PasswordModalProps) {
  const [isPasswordProtected, setIsPasswordProtected] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");

  const handleYes = () => {
    setIsPasswordProtected(true);
  };

  const handleNo = () => {
    onConfirm(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPasswordProtected && password.trim()) {
      onConfirm(true, password);
    }
  };

  if (isPasswordProtected === null) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Please let us know if this PDF requires a password to open.
        </p>
        <div className="flex space-x-3">
          <button
            onClick={handleYes}
            className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
          >
            Yes
          </button>
          <button
            onClick={handleNo}
            className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
          >
            No
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="pdf-password" className="block text-sm font-medium text-gray-700 mb-2">
          Enter PDF Password
        </label>
        <input
          type="password"
          id="pdf-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
          placeholder="Enter password"
          autoFocus
        />
      </div>
      <div className="flex space-x-3">
        <button
          type="submit"
          disabled={!password.trim()}
          className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Confirm
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function ChatWindow({ context = "assets", onAssetCreated }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState<string | null>(null);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'uploading' | 'success' | 'error' | null; message: string }>({ type: null, message: '' });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageIdCounterRef = useRef(0); // Counter for unique message IDs
  const usedIdsRef = useRef<Set<string>>(new Set()); // Track used IDs to prevent duplicates

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat history on mount
  useEffect(() => {
    const loadChatHistory = async () => {
      try {
        const accessToken = localStorage.getItem("access_token");
        if (!accessToken) {
          return; // User not authenticated, skip loading history
        }

        const response = await fetch(`/api/chat?context=${context}`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            // Convert database messages to frontend format
            const loadedMessages: Message[] = data.messages.map((msg: any) => ({
              id: msg.id,
              role: msg.role,
              content: msg.content,
              timestamp: new Date(msg.timestamp),
            }));
            
            setMessages(loadedMessages);
            
            // Track loaded message IDs to avoid duplicates
            loadedMessages.forEach((msg) => {
              usedIdsRef.current.add(msg.id);
            });
          }
        } else if (response.status === 404) {
          // Route not found - this is expected if the route hasn't been set up yet
          console.warn("Chat history endpoint not found. Make sure the API route is properly configured.");
        }
      } catch (error) {
        console.error("Error loading chat history:", error);
        // Don't show error to user, just continue with empty chat
      }
    };

    loadChatHistory();
  }, [context]); // Reload history when context changes

  const clearChat = async () => {
    try {
      const accessToken = localStorage.getItem("access_token");
      if (accessToken) {
        // Clear chat history from database for current context
        await fetch(`/api/chat?context=${context}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });
      }
    } catch (error) {
      console.error("Error clearing chat history from database:", error);
      // Continue with local clear even if database clear fails
    }
    
    // Clear all messages locally
    setMessages([]);
    // Clear input field
    setInput("");
    // Clear used IDs set
    usedIdsRef.current.clear();
    // Reset counter
    messageIdCounterRef.current = 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Allow submit if there's text OR a file selected
    if ((!input.trim() && !selectedFile) || isLoading) return;

    // Get access token from localStorage
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
      alert("Not authenticated. Please log in again.");
      return;
    }

    // Prepare conversation history for context
    const conversationHistory = messages.map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

    // Generate unique message ID - ensure it's never duplicated
    let messageId: string;
    do {
      messageId = `user_${Date.now()}_${performance.now()}_${++messageIdCounterRef.current}_${Math.random().toString(36).substr(2, 9)}`;
    } while (usedIdsRef.current.has(messageId));
    usedIdsRef.current.add(messageId);
    
    // Create user message content
    const userMessageContent = input.trim() || (selectedFile ? `Uploaded ${selectedFile.name}` : "");
    
    const userMessage: Message = {
      id: messageId,
      role: "user",
      content: userMessageContent,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input.trim();
    const currentFile = selectedFile;
    const currentPassword = pdfPassword;
    setInput("");
    setSelectedFile(null);
    setPdfPassword(null);
    setIsLoading(true);
    setUploadStatus({ type: 'uploading', message: currentFile ? `Uploading ${currentFile.name}...` : 'Processing...' });

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      let response: Response;
      let data: any;

      // If there's a file, use the upload endpoint
      if (currentFile) {
        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('context', context);
        formData.append('conversation_history', JSON.stringify(conversationHistory));
        
        // Add password if it's a PDF and password is provided
        if (currentPassword) {
          formData.append('pdf_password', currentPassword);
        }
        
        // If there's also text, prepend it to the conversation
        if (currentInput) {
          // Add the text as a user message in the conversation history
          const updatedHistory = [
            ...conversationHistory,
            { role: "user", content: currentInput }
          ];
          formData.set('conversation_history', JSON.stringify(updatedHistory));
        }

        setUploadStatus({ type: 'uploading', message: `Parsing ${currentFile.name}...` });
        response = await fetch("/api/chat/upload", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
          body: formData,
        }).catch((fetchError) => {
          console.error("Fetch error:", fetchError);
          if (fetchError.message?.includes("fetch failed") || fetchError.message?.includes("Failed to fetch")) {
            throw new Error(`Cannot connect to backend server. Please ensure both frontend and backend are running.`);
          }
          throw fetchError;
        });

        if (!response.ok) {
          let errorMessage = "Failed to upload file";
          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.message || errorMessage;
          } catch (e) {
            try {
              const errorText = await response.text();
              if (errorText) {
                errorMessage = errorText;
              }
            } catch (e2) {
              // Use default error message
            }
          }
          throw new Error(errorMessage);
        }

        data = await response.json();
        
        // Show success status
        const fileExtension = currentFile.name.split('.').pop()?.toLowerCase();
        const fileType = fileExtension === 'csv' ? 'CSV' : 'PDF';
        setUploadStatus({ 
          type: 'success', 
          message: `✅ Successfully uploaded and parsed ${currentFile.name}. ${fileType} data extracted and sent to AI for processing.` 
        });
        setTimeout(() => setUploadStatus({ type: null, message: '' }), 5000);
      } else {
        // No file, use regular chat endpoint
        response = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            message: currentInput,
            conversation_history: conversationHistory,
            context: context,
          }),
        }).catch((fetchError) => {
          console.error("Fetch error:", fetchError);
          if (fetchError.message?.includes("fetch failed") || fetchError.message?.includes("Failed to fetch")) {
            throw new Error(`Cannot connect to backend server. Please ensure both frontend and backend are running.`);
          }
          throw fetchError;
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || errorData.message || "Failed to get response");
        }

        data = await response.json();
      }

      // Always generate unique message ID on frontend to avoid duplicates
      let assistantMessageId: string;
      do {
        assistantMessageId = `assistant_${Date.now()}_${performance.now()}_${++messageIdCounterRef.current}_${Math.random().toString(36).substr(2, 9)}`;
      } while (usedIdsRef.current.has(assistantMessageId));
      usedIdsRef.current.add(assistantMessageId);
      
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Check if an asset was successfully created, updated, or deleted and trigger refresh
      if (context === "assets" && onAssetCreated) {
        const responseText = data.response?.toLowerCase() || "";
        // Check for success indicators in the response (create, update, delete)
        const successIndicators = [
          "successfully created",
          "successfully added",
          "successfully updated",
          "successfully deleted",
          "asset has been added",
          "asset has been created",
          "asset has been updated",
          "asset has been deleted",
          "added to your portfolio",
          "created asset",
          "added a new",
          "updated asset",
          "deleted asset",
        ];
        
        if (successIndicators.some(indicator => responseText.includes(indicator))) {
          // Small delay to ensure database is updated
          setTimeout(() => {
            onAssetCreated();
          }, 500);
        }
      }
    } catch (error) {
      console.error("Error sending message:", error);
      let errorMessage = "Sorry, I encountered an error. Please try again.";
      
      if (error instanceof Error) {
        errorMessage = error.message;
        // Provide more helpful error messages
        if (error.message.includes("Cannot connect") || error.message.includes("Failed to fetch")) {
          errorMessage = "Cannot connect to the backend server. Please ensure the backend is running on http://localhost:8000";
        } else if (error.message.includes("Not authenticated")) {
          errorMessage = "Your session has expired. Please log in again.";
        }
      }
      
      // Show error status
      setUploadStatus({ type: 'error', message: `Upload failed: ${errorMessage}` });
      setTimeout(() => setUploadStatus({ type: null, message: '' }), 5000);
      
      // Generate unique message ID for error message
      let errorMessageId: string;
      do {
        errorMessageId = `error_${Date.now()}_${performance.now()}_${++messageIdCounterRef.current}_${Math.random().toString(36).substr(2, 9)}`;
      } while (usedIdsRef.current.has(errorMessageId));
      usedIdsRef.current.add(errorMessageId);
      
      const errorMsg: Message = {
        id: errorMessageId,
        role: "assistant",
        content: errorMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    console.log("DEBUG: File selected:", file?.name, file?.size);
    if (file) {
      // Validate file type
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      if (fileExtension !== 'pdf' && fileExtension !== 'csv') {
        alert('Please select a PDF or CSV file');
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB');
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }
      
      // If it's a PDF, show password modal
      if (fileExtension === 'pdf') {
        setPendingFile(file);
        setShowPasswordModal(true);
      } else {
        // For CSV files, just store the file
        console.log("DEBUG: File validated, storing for upload on send");
        setSelectedFile(file);
        setPdfPassword(null);
      }
    }
  };

  const handlePasswordModalConfirm = (isPasswordProtected: boolean, password?: string) => {
    if (pendingFile) {
      setSelectedFile(pendingFile);
      setPdfPassword(isPasswordProtected ? (password || null) : null);
      setPendingFile(null);
    }
    setShowPasswordModal(false);
  };

  const handlePasswordModalCancel = () => {
    setPendingFile(null);
    setShowPasswordModal(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setPdfPassword(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [input]);

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Chat Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {context === "expenses" ? "Expense Tracker Assistant" : "Financial Assistant"}
            </h2>
            <p className="text-xs text-gray-500">Ask me anything about your finances</p>
          </div>
          <button
            onClick={clearChat}
            className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
            title="Clear chat history"
            disabled={isLoading}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 inline-block mr-1.5"
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
            Clear
          </button>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === "user"
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              {message.role === "assistant" ? (
                <div className="text-sm">
                  <MarkdownRenderer content={message.content} />
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              )}
              <p
                className={`text-xs mt-1 ${
                  message.role === "user" ? "text-primary-100" : "text-gray-500"
                }`}
              >
                {message.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-2">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0s" }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        {/* Upload Status Notification */}
        {uploadStatus.type && (
          <div className={`mb-3 p-3 rounded-lg flex items-center justify-between ${
            uploadStatus.type === 'uploading' ? 'bg-blue-50 border border-blue-200' :
            uploadStatus.type === 'success' ? 'bg-green-50 border border-green-200' :
            'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-center space-x-2">
              {uploadStatus.type === 'uploading' && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              )}
              {uploadStatus.type === 'success' && (
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              )}
              {uploadStatus.type === 'error' && (
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              <span className={`text-sm font-medium ${
                uploadStatus.type === 'uploading' ? 'text-blue-900' :
                uploadStatus.type === 'success' ? 'text-green-900' :
                'text-red-900'
              }`}>
                {uploadStatus.message}
              </span>
            </div>
            {uploadStatus.type !== 'uploading' && (
              <button
                onClick={() => setUploadStatus({ type: null, message: '' })}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        )}
        
        {/* Selected File Preview */}
        {selectedFile && (
          <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center space-x-2 flex-1 min-w-0">
              <svg className="w-5 h-5 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div className="flex flex-col min-w-0 flex-1">
                <span className="text-sm font-medium text-blue-900 truncate">{selectedFile.name}</span>
                <span className="text-xs text-blue-600">({(selectedFile.size / 1024).toFixed(1)} KB{pdfPassword ? ' • Password protected' : ''})</span>
              </div>
            </div>
            <button
              type="button"
              onClick={handleRemoveFile}
              className="ml-2 text-blue-600 hover:text-blue-800 flex-shrink-0"
              title="Remove file"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}
        
        {/* Password Modal */}
        {showPasswordModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Is this PDF password protected?
              </h3>
              <PasswordModal
                onConfirm={handlePasswordModalConfirm}
                onCancel={handlePasswordModalCancel}
              />
            </div>
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="flex items-end space-x-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.csv"
            onChange={handleFileSelect}
            className="hidden"
            disabled={isLoading}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="px-3 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Upload PDF or CSV file"
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
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          </button>
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                adjustTextareaHeight();
              }}
              onKeyDown={handleKeyDown}
              placeholder={selectedFile ? "Add a message (optional)..." : "Ask about your finances..."}
              rows={1}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none overflow-hidden"
              style={{ minHeight: "40px", maxHeight: "120px" }}
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={(!input.trim() && !selectedFile) || isLoading}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </form>
        <p className="text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line. Click the attachment icon to upload PDF or CSV files. You can add text along with the file.
        </p>
      </div>
    </div>
  );
}

