import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
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

    // Get FormData from request
    const formData = await request.formData();
    
    // Get file and other form fields
    const file = formData.get("file") as File;
    const assetType = formData.get("asset_type") as string;
    const market = formData.get("market") as string | null;
    const pdfPassword = formData.get("pdf_password") as string | null;

    if (!file) {
      return NextResponse.json(
        { message: "File is required" },
        { status: 400 }
      );
    }

    if (!assetType) {
      return NextResponse.json(
        { message: "asset_type is required" },
        { status: 400 }
      );
    }

    // Call Python backend API
    const backendUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    // Create new FormData for backend
    const backendFormData = new FormData();
    backendFormData.append("file", file);
    backendFormData.append("asset_type", assetType);
    if (market) {
      backendFormData.append("market", market);
    }
    if (pdfPassword) {
      backendFormData.append("pdf_password", pdfPassword);
    }

    try {
      console.log("DEBUG: Proxying PDF upload to backend:", backendUrl + "/api/assets/upload-pdf");
      console.log("DEBUG: File name:", file.name, "Size:", file.size, "Asset type:", assetType);
      
      const backendResponse = await fetch(`${backendUrl}/api/assets/upload-pdf`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          // Don't set Content-Type header - let fetch set it with boundary for FormData
        },
        body: backendFormData,
      });

      // Check if response is ok before trying to parse JSON
      const contentType = backendResponse.headers.get("content-type");
      let data;
      
      if (contentType && contentType.includes("application/json")) {
        data = await backendResponse.json();
      } else {
        const text = await backendResponse.text();
        console.error("DEBUG: Backend returned non-JSON:", text);
        return NextResponse.json(
          { message: `Backend error: ${text || "Unknown error"}` },
          { status: backendResponse.status || 500 }
        );
      }

      if (!backendResponse.ok) {
        console.error("DEBUG: Backend error response:", data);
        return NextResponse.json(
          { message: data.detail || data.message || "PDF upload failed" },
          { status: backendResponse.status }
        );
      }

      console.log("DEBUG: PDF upload successful");
      return NextResponse.json(data, { status: 200 });
    } catch (fetchError: any) {
      // Handle connection errors (backend not running, network issues, etc.)
      console.error("DEBUG: Backend connection error:", fetchError);
      return NextResponse.json(
        { 
          message: `Cannot connect to backend server at ${backendUrl}. Please ensure the backend is running.`,
          error: fetchError.message 
        },
        { status: 503 }
      );
    }
  } catch (error: any) {
    console.error("DEBUG: PDF upload API route error:", error);
    return NextResponse.json(
      { message: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

