import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  try {
    // Get access token from Authorization header
    const authHeader = request.headers.get("authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return NextResponse.json(
        { message: "Authorization token required" },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7);

    // Call Python backend API
    const backendUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    try {
      const backendResponse = await fetch(`${backendUrl}/api/chat/history`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      // Check if response is ok before trying to parse JSON
      const contentType = backendResponse.headers.get("content-type");
      let data;
      
      if (contentType && contentType.includes("application/json")) {
        data = await backendResponse.json();
      } else {
        const text = await backendResponse.text();
        return NextResponse.json(
          { message: `Backend error: ${text || "Unknown error"}` },
          { status: backendResponse.status || 500 }
        );
      }

      if (!backendResponse.ok) {
        return NextResponse.json(
          { message: data.detail || data.message || "Failed to fetch chat history" },
          { status: backendResponse.status }
        );
      }

      return NextResponse.json(data, { status: 200 });
    } catch (fetchError: any) {
      // Handle connection errors (backend not running, network issues, etc.)
      console.error("Backend connection error:", fetchError);
      return NextResponse.json(
        { 
          message: `Cannot connect to backend server at ${backendUrl}. Please ensure the backend is running.`,
          error: fetchError.message 
        },
        { status: 503 }
      );
    }
  } catch (error: any) {
    console.error("Chat history API route error:", error);
    return NextResponse.json(
      { message: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    // Get access token from Authorization header
    const authHeader = request.headers.get("authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return NextResponse.json(
        { message: "Authorization token required" },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7);

    // Call Python backend API
    const backendUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    try {
      const backendResponse = await fetch(`${backendUrl}/api/chat/history`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!backendResponse.ok) {
        const contentType = backendResponse.headers.get("content-type");
        let data;
        if (contentType && contentType.includes("application/json")) {
          data = await backendResponse.json();
        } else {
          const text = await backendResponse.text();
          return NextResponse.json(
            { message: `Backend error: ${text || "Unknown error"}` },
            { status: backendResponse.status || 500 }
          );
        }
        return NextResponse.json(
          { message: data.detail || data.message || "Failed to clear chat history" },
          { status: backendResponse.status }
        );
      }

      return new NextResponse(null, { status: 204 });
    } catch (fetchError: any) {
      // Handle connection errors (backend not running, network issues, etc.)
      console.error("Backend connection error:", fetchError);
      return NextResponse.json(
        { 
          message: `Cannot connect to backend server at ${backendUrl}. Please ensure the backend is running.`,
          error: fetchError.message 
        },
        { status: 503 }
      );
    }
  } catch (error: any) {
    console.error("Clear chat history API route error:", error);
    return NextResponse.json(
      { message: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, conversation_history } = body;

    // Validate input
    if (!message) {
      return NextResponse.json(
        { message: "Message is required" },
        { status: 400 }
      );
    }

    // Get access token from Authorization header
    const authHeader = request.headers.get("authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return NextResponse.json(
        { message: "Authorization token required" },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7);

    // Call Python backend API
    const backendUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    try {
      const backendResponse = await fetch(`${backendUrl}/api/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          conversation_history: conversation_history || [],
        }),
      });

      // Check if response is ok before trying to parse JSON
      const contentType = backendResponse.headers.get("content-type");
      let data;
      
      if (contentType && contentType.includes("application/json")) {
        data = await backendResponse.json();
      } else {
        const text = await backendResponse.text();
        return NextResponse.json(
          { message: `Backend error: ${text || "Unknown error"}` },
          { status: backendResponse.status || 500 }
        );
      }

      if (!backendResponse.ok) {
        return NextResponse.json(
          { message: data.detail || data.message || "Chat request failed" },
          { status: backendResponse.status }
        );
      }

      return NextResponse.json(data, { status: 200 });
    } catch (fetchError: any) {
      // Handle connection errors (backend not running, network issues, etc.)
      console.error("Backend connection error:", fetchError);
      return NextResponse.json(
        { 
          message: `Cannot connect to backend server at ${backendUrl}. Please ensure the backend is running.`,
          error: fetchError.message 
        },
        { status: 503 }
      );
    }
  } catch (error: any) {
    console.error("Chat API route error:", error);
    return NextResponse.json(
      { message: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

