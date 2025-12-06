"use client";

import { useState, useRef, useEffect } from "react";
import MarkdownRenderer from "./MarkdownRenderer";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messageIdCounterRef = useRef(0); // Counter for unique message IDs
  const usedIdsRef = useRef<Set<string>>(new Set()); // Track used IDs to prevent duplicates

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const clearChat = () => {
    // Clear all messages
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
    if (!input.trim() || isLoading) return;

    // Generate unique message ID - ensure it's never duplicated
    let messageId: string;
    do {
      messageId = `user_${Date.now()}_${performance.now()}_${++messageIdCounterRef.current}_${Math.random().toString(36).substr(2, 9)}`;
    } while (usedIdsRef.current.has(messageId));
    usedIdsRef.current.add(messageId);
    
    const userMessage: Message = {
      id: messageId,
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      // Get access token from localStorage
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Not authenticated. Please log in again.");
      }

      // Prepare conversation history for context
      const conversationHistory = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      // Call backend LLM API via Next.js API route (avoids CORS issues)
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          message: userMessage.content,
          conversation_history: conversationHistory,
        }),
      }).catch((fetchError) => {
        // Handle network errors
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

      const data = await response.json();

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

  useEffect(() => {
    adjustTextareaHeight();
  }, [input]);

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Chat Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Finance Assistant</h2>
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
        <form onSubmit={handleSubmit} className="flex items-end space-x-2">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                adjustTextareaHeight();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your finances..."
              rows={1}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none overflow-hidden"
              style={{ minHeight: "40px", maxHeight: "120px" }}
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
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
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

