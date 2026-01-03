# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from schemas import ChatMessage, ChatResponse
from controllers.po_agent_controller import POAgent
import uuid

app = FastAPI(title="SupplierX AI PO Agent", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sessions (use Redis in production)
sessions = {}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage):
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        agent = POAgent()
        sessions[session_id] = {
            "agent": agent,
            "state": agent.get_initial_state()
        }

    session = sessions[session_id]
    response_text = session["agent"].process(request.message, session["state"])

    return ChatResponse(
        response=response_text,
        payload_preview=session["state"]["payload"],
        current_step=session["state"]["current_step"],
        completed=session["state"]["current_step"] == "DONE",
        po_number=session["state"]["payload"].get("po_number"),
        session_id=session_id
        
    )

@app.get("/")
async def root():
    return {"message": "SupplierX Conversational PO Agent is running!"}