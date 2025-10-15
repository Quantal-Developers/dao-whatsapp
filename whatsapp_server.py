# whatsapp_server.py
import os
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

# Import the database agent directly
from app.agents.database_agent.agent import DatabaseAgent

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="DaoOS WhatsApp API", version="1.0.0")

# WhatsApp Cloud API configuration
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "your_verify_token_here")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "your_access_token_here")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "your_phone_number_id_here")
WHATSAPP_API_URL = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

# Templates for web UI
templates = Jinja2Templates(directory="templates")

# Pydantic models
class WhatsAppMessage(BaseModel):
    to: str
    message: str

class ChatMessage(BaseModel):
    message: str
    thread_id: Optional[str] = None

class WebhookData(BaseModel):
    object: str
    entry: list

# Global storage for conversation threads (in production, use Redis or database)
conversation_threads: Dict[str, Dict] = {}

# Initialize the database agent
database_agent = DatabaseAgent()

async def send_whatsapp_message(to: str, message: str, message_id: Optional[str] = None) -> Dict[str, Any]:
    """Send a message via WhatsApp Cloud API"""
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": message
        }
    }
    
    # Add read receipt if message_id is provided
    if message_id:
        payload["context"] = {"message_id": message_id}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WHATSAPP_API_URL, headers=headers, json=payload) as response:
                result = await response.json()
                if response.status == 200:
                    print(f"Message sent successfully to {to}")
                    return result
                else:
                    print(f"Error sending message: {result}")
                    return {"error": result}
        except Exception as e:
            print(f"Exception sending message: {e}")
            return {"error": str(e)}

async def send_typing_indicator(to: str, message_id: str) -> None:
    """Send typing indicator to WhatsApp"""
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WHATSAPP_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    print(f"Typing indicator sent to {to}")
        except Exception as e:
            print(f"Error sending typing indicator: {e}")

def get_or_create_thread(phone_number: str) -> str:
    """Get or create a conversation thread for a phone number"""
    if phone_number not in conversation_threads:
        import uuid
        thread_id = str(uuid.uuid4())
        conversation_threads[phone_number] = {
            "thread_id": thread_id,
            "state": {"messages": []}
        }
    return conversation_threads[phone_number]["thread_id"]

async def process_whatsapp_message(from_number: str, message_text: str, message_id: str) -> None:
    """Process incoming WhatsApp message through the database agent"""
    try:
        # Get or create thread for this conversation
        thread_id = get_or_create_thread(from_number)
        thread_data = conversation_threads[from_number]
        
        # Send typing indicator
        await send_typing_indicator(from_number, message_id)
        
        # Add user message to state
        thread_data["state"]["messages"].append({"content": message_text, "type": "human"})
        
        # Process through database agent
        ai_response = database_agent.process_message(message_text)
        
        # Add AI response to state
        thread_data["state"]["messages"].append({"content": ai_response, "type": "ai"})
        
        # Send response back to WhatsApp
        await send_whatsapp_message(from_number, ai_response, message_id)
        
    except Exception as e:
        print(f"Error processing message: {e}")
        error_message = "I encountered an error processing your message. Please try again."
        await send_whatsapp_message(from_number, error_message, message_id)

# Routes
@app.get("/", response_class=HTMLResponse)
async def chat_ui(request: Request):
    """Serve the chat UI"""
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat")
async def chat_endpoint(chat_data: ChatMessage):
    """API endpoint for web chat"""
    try:
        # Use provided thread_id or create new one
        thread_id = chat_data.thread_id or get_or_create_thread("web_user")
        thread_data = conversation_threads.get("web_user", {"state": {"messages": []}})
        
        # Add user message
        thread_data["state"]["messages"].append({"content": chat_data.message, "type": "human"})
        
        # Process through database agent
        ai_response = database_agent.process_message(chat_data.message)
        
        # Add AI response to state
        thread_data["state"]["messages"].append({"content": ai_response, "type": "ai"})
        
        # Update state
        conversation_threads["web_user"] = thread_data
        
        return JSONResponse({
            "response": ai_response,
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/stream")
async def chat_stream_endpoint(chat_data: ChatMessage):
    """API endpoint for streaming chat responses"""
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate_stream():
        try:
            # Use provided thread_id or create new one
            thread_id = chat_data.thread_id or get_or_create_thread("web_user")
            thread_data = conversation_threads.get("web_user", {"state": {"messages": []}})
            
            # Add user message
            thread_data["state"]["messages"].append({"content": chat_data.message, "type": "human"})
            
            # Process through database agent
            ai_response = database_agent.process_message(chat_data.message)
            
            # Add AI response to state
            thread_data["state"]["messages"].append({"content": ai_response, "type": "ai"})
            
            # Update state
            conversation_threads["web_user"] = thread_data
            
            # Stream the response
            yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
            
            # Split response into chunks for streaming effect
            words = ai_response.split()
            for i, word in enumerate(words):
                chunk = word + " "
                yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.05)  # Small delay for streaming effect
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            print(f"Error in streaming chat endpoint: {e}")
            yield f"data: {json.dumps({'content': 'Sorry, I encountered an error. Please try again.'})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/plain")

@app.post("/api/whatsapp/send")
async def send_whatsapp_endpoint(message_data: WhatsAppMessage):
    """Send a message via WhatsApp"""
    try:
        result = await send_whatsapp_message(message_data.to, message_data.message)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """WhatsApp webhook verification"""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("Webhook verified successfully")
        return int(hub_challenge)
    else:
        print("Webhook verification failed")
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receive WhatsApp webhook events"""
    try:
        body = await request.json()
        print(f"Webhook received: {json.dumps(body, indent=2)}")
        
        if body.get("object") == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        messages = change.get("value", {}).get("messages", [])
                        for message in messages:
                            from_number = message.get("from")
                            message_text = message.get("text", {}).get("body", "")
                            message_id = message.get("id")
                            
                            if from_number and message_text and message_id:
                                # Process message asynchronously
                                asyncio.create_task(
                                    process_whatsapp_message(from_number, message_text, message_id)
                                )
        
        return JSONResponse({"status": "success"})
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "service": "DaoOS WhatsApp API"
    })

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    print("Starting DaoOS WhatsApp API Server...")
    print(f"WhatsApp API URL: {WHATSAPP_API_URL}")
    print(f"Webhook URL: http://localhost:8000/webhook")
    print(f"Chat UI: http://localhost:8000")
    print(f"Health Check: http://localhost:8000/health")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
