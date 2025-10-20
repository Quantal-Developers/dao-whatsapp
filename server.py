# server.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import uuid
from app.agents.database_agent.agent import DatabaseAgent
app = FastAPI(title="Minh's Personal AI Copilot")

# Initialize a single copilot (database agent) instance
agent = DatabaseAgent()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the chat interface"""
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Minh's Personal AI Copilot is running"}

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Handle chat messages"""
    try:
        data = await request.json()
        message = data.get("message", "")
        thread_id = data.get("thread_id") or str(uuid.uuid4())

        if not message:
            return {"error": "No message provided"}

        # Directly process via the copilot (database agent)
        response_text = agent.process_message(message)

        return {"response": response_text, "thread_id": thread_id, "status": "success"}

    except Exception as e:
        return {
            "error": f"Error processing message: {str(e)}",
            "status": "error"
        }

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: Request):
    """Handle streaming chat messages"""
    from fastapi.responses import StreamingResponse
    import asyncio
    import json
    
    try:
        data = await request.json()
        message = data.get("message", "")
        thread_id = data.get("thread_id") or str(uuid.uuid4())

        if not message:
            return {"error": "No message provided"}

        async def generate_stream():
            # Send thread_id first
            yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
            
            # Process message and stream response
            response_text = agent.process_message(message)
            
            # Simulate streaming by sending chunks
            words = response_text.split()
            current_text = ""
            
            for i, word in enumerate(words):
                current_text += word + " "
                
                # Send chunk every few words
                if i % 3 == 0 or i == len(words) - 1:
                    # Emit as SSE chunk
                    yield f"data: {json.dumps({'content': current_text})}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for streaming effect
            
            # Send completion signal
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        return {
            "error": f"Error processing message: {str(e)}",
            "status": "error"
        }

if __name__ == "__main__":
    print("🚀 Starting Minh's Personal AI Copilot Server...")
    print("📱 Web Interface: http://localhost:8000")
    print("🔧 API Health: http://localhost:8000/health")
    print("=" * 50)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
