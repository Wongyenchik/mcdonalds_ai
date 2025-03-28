from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uvicorn
from llm_train import process_query  

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://*.vercel.app",  # Allow Vercel deployment URLs
    "https://*.render.com"   # Allow Render deployment URLs
]
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Database connection parameters
DB_PARAMS = {
    "dbname": os.getenv("POSTGRES_DB", "mcdonalds_ai"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432")
}

# Pydantic model for outlet data
class Outlet(BaseModel):
    id: int
    name: str
    address: str
    telephone: str
    latitude: float
    longitude: float
    waze_link: str

    class Config:
        from_attributes = True
        

def get_db_connection():
    """Create and return a database connection"""
    return psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to McDonald's Outlets API"}

@app.get("/outlets", response_model=List[Outlet])
async def get_all_outlets():
    """Get all McDonald's outlets"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM mcdonalds_outlets")
            outlets = cur.fetchall()
        return outlets
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

class LLMData(BaseModel):
    llmresponse: str

# Change from list to single string
memory_db = {"llmresponse": ""}

@app.get("/llmresponses", response_model=LLMData)
def get_llmresponses():
    return LLMData(llmresponse=memory_db["llmresponse"])

@app.post("/llmresponses")
def add_llmresponse(llmresponse: LLMData):
    # Process the query using the LLM chain
    processed_response = process_query(llmresponse.llmresponse)
    # Store the processed response in memory_db
    memory_db["llmresponse"] = processed_response
    return LLMData(llmresponse=processed_response)
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 