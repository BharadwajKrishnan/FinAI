"""
File upload helper functions for chat router
"""
import csv
import io
from typing import Dict, Any, Optional
from fastapi import HTTPException


def parse_csv_file(file_content: bytes) -> Optional[Dict[str, Any]]:
    """Parse CSV file and extract asset information"""
    try:
        # Decode bytes to string
        content = file_content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        # Extract rows
        rows = list(csv_reader)
        if not rows:
            return None
        
        # Return structured data
        return {
            "type": "csv",
            "rows": rows,
            "columns": list(rows[0].keys()) if rows else []
        }
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return None


def parse_pdf_file(file_content: bytes) -> Optional[Dict[str, Any]]:
    """Parse PDF file and extract text"""
    try:
        # Try pdfplumber first (better text extraction)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if text.strip():
                    return {
                        "type": "pdf",
                        "text": text
                    }
        except ImportError:
            pass
        except Exception as e:
            print(f"Error with pdfplumber: {e}")
        
        # Fallback to PyPDF2
        try:
            import PyPDF2
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            if text.strip():
                return {
                    "type": "pdf",
                    "text": text
                }
        except ImportError:
            raise HTTPException(status_code=500, detail="PDF parsing library not installed. Please install PyPDF2 or pdfplumber.")
        except Exception as e:
            print(f"Error with PyPDF2: {e}")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None


def format_extracted_data(extracted_data: Dict[str, Any]) -> str:
    """Format extracted data into a message for LLM processing"""
    if extracted_data["type"] == "csv":
        # Format CSV data
        rows = extracted_data.get("rows", [])
        if not rows:
            return "I have uploaded a CSV file but it appears to be empty."
        
        # Create a readable format
        formatted = "I have uploaded a CSV file with the following data:\n\n"
        for i, row in enumerate(rows[:10], 1):  # Limit to first 10 rows
            formatted += f"Row {i}:\n"
            for key, value in row.items():
                formatted += f"  {key}: {value}\n"
            formatted += "\n"
        
        if len(rows) > 10:
            formatted += f"... and {len(rows) - 10} more rows.\n"
        
        formatted += "\nPlease extract asset information from this data and add it to my portfolio."
        return formatted
    
    elif extracted_data["type"] == "pdf":
        # Format PDF text
        text = extracted_data.get("text", "")
        if not text.strip():
            return "I have uploaded a PDF file but could not extract any text from it."
        
        # Limit text length to avoid token limits
        if len(text) > 8000:
            text = text[:8000] + "... (truncated)"
        
        formatted = f"I have uploaded a PDF file with the following content:\n\n{text}\n\nPlease extract asset information from this content and add it to my portfolio."
        return formatted
    
    return "I have uploaded a file. Please extract asset information from it."

