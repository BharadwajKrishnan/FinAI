import { NextRequest, NextResponse } from "next/server";

// Increase timeout to maximum (300 seconds) - LLM processing may take a long time
// Note: Vercel has a maximum of 300 seconds for serverless functions
export const maxDuration = 300;

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
      console.log("DEBUG: No timeout - LLM may take a long time to process large PDFs");
      
      // No timeout - LLM may take a long time to process large PDFs
      // The fetch will wait indefinitely for the backend response
      const backendResponse = await fetch(`${backendUrl}/api/assets/upload-pdf`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          // Don't set Content-Type header - let fetch set it with boundary for FormData
        },
        body: backendFormData,
        // No signal/abort controller - wait indefinitely
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
      // Don't show connection errors - backend may still be processing
      // Log to console but don't return error message about backend not running
      console.error("DEBUG: Backend connection error (may still be processing):", fetchError);
      console.log("DEBUG: This may be a temporary network issue. Backend may still be processing the PDF.");
      
      // Return a generic error that doesn't mention backend connection
      // This prevents false "backend not running" messages during long LLM processing
      return NextResponse.json(
        { 
          message: `PDF processing is taking longer than expected. Please wait - the backend may still be processing your request.`,
          error: "Processing timeout" 
        },
        { status: 504 } // Gateway Timeout - but with a message that doesn't say backend is down
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

