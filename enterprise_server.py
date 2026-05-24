"""
Enterprise LLM Suite - Web Server
Host inference locally and expose access via shareable links
With Solana token gating and liquid staking
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import uvicorn
import json
import secrets
from datetime import datetime, timedelta
from enterprise_suite import (
    EnterpriseLLMSuite,
    create_enterprise_suite,
    ModelProvider,
    UserRole
)
from solana_integration import (
    SolanaManager,
    TokenGating,
    create_solana_manager
)
from liquid_endpoints import router as liquid_endpoints_router
from decentralized_routes import router as decentralized_router
from domain_folder_routes import router as domain_folder_router

# Prometheus metrics
inference_requests = Counter('llm_inference_requests_total', 'Total inference requests')
inference_duration = Histogram('llm_inference_duration_seconds', 'Inference duration in seconds')
conversations_created = Counter('llm_conversations_created_total', 'Total conversations created')


# Pydantic models for API
class UserCreate(BaseModel):
    username: str
    email: str
    role: str = "user"


class ModelRegister(BaseModel):
    name: str
    provider: str
    path: str
    size_mb: float
    quantization: str = "16-bit"
    parameters: Optional[Dict] = None


class MessageSend(BaseModel):
    conversation_id: str
    message: str
    use_rag: bool = False
    rag_top_k: int = 3


class ConversationCreate(BaseModel):
    user_id: str
    model_id: str
    title: str


class DocumentIngest(BaseModel):
    file_path: str
    chunk_size: int = 1000
    chunk_overlap: int = 200


class ShareLinkCreate(BaseModel):
    conversation_id: str
    expires_in_hours: int = 24


class SolanaPayment(BaseModel):
    wallet_address: str
    conversation_id: str


class StakeTokens(BaseModel):
    wallet_address: str
    amount: int
    pool_address: str


class UnstakeTokens(BaseModel):
    wallet_address: str
    amount: int
    pool_address: str


# Initialize FastAPI app
app = FastAPI(
    title="Enterprise LLM Suite API",
    description="Hosted inference API with shareable links",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Include liquid staked endpoints router
app.include_router(liquid_endpoints_router)

# Include decentralized inference node router
app.include_router(decentralized_router)

# Include domain folder router
app.include_router(domain_folder_router)

# Initialize enterprise suite
suite = create_enterprise_suite()

# Initialize Solana integration
try:
    solana_manager = create_solana_manager()
    token_gating = TokenGating(solana_manager)
except Exception as e:
    print(f"Solana integration not available: {e}")
    solana_manager = None
    token_gating = None

# Shareable links storage
share_links: Dict[str, Dict] = {}


# Authentication dependency
async def get_api_key(x_api_key: str = Header(...)):
    """Verify API key for authentication."""
    user = suite.authenticate_user(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "users": len(suite.users),
        "models": len(suite.models),
        "conversations": len(suite.conversations)
    }


# User endpoints
@app.post("/api/users")
async def create_user(user_data: UserCreate):
    """Create a new user."""
    role = UserRole(user_data.role)
    user = suite.create_user(user_data.username, user_data.email, role)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "api_key": user.api_key
    }


@app.get("/api/users/me")
async def get_current_user(current_user = Depends(get_api_key)):
    """Get current user info."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value
    }


# Model endpoints
@app.post("/api/models")
async def register_model(model_data: ModelRegister, current_user = Depends(get_api_key)):
    """Register a new model."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    provider = ModelProvider(model_data.provider)
    model = suite.register_model(
        model_data.name,
        provider,
        model_data.path,
        model_data.size_mb,
        model_data.quantization,
        model_data.parameters
    )
    return {
        "id": model.id,
        "name": model.name,
        "provider": model.provider.value,
        "size_mb": model.size_mb,
        "quantization": model.quantization
    }


@app.get("/api/models")
async def list_models(current_user = Depends(get_api_key)):
    """List all models."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "provider": m.provider.value,
            "size_mb": m.size_mb,
            "quantization": m.quantization,
            "loaded": m.loaded
        }
        for m in suite.models.values()
    ]


@app.post("/api/models/{model_id}/load")
async def load_model(model_id: str, current_user = Depends(get_api_key)):
    """Load a model into memory."""
    success = suite.load_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "loaded", "model_id": model_id}


# Conversation endpoints
@app.post("/api/conversations")
async def create_conversation(conv_data: ConversationCreate, current_user = Depends(get_api_key)):
    """Create a new conversation."""
    conv = suite.create_conversation(
        conv_data.user_id,
        conv_data.model_id,
        conv_data.title
    )
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "model_id": conv.model_id,
        "title": conv.title,
        "created_at": conv.created_at
    }


@app.get("/api/conversations")
async def list_conversations(current_user = Depends(get_api_key)):
    """List user's conversations."""
    user_convs = [c for c in suite.conversations.values() if c.user_id == current_user.id]
    return [
        {
            "id": c.id,
            "title": c.title,
            "model_id": c.model_id,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "message_count": len(c.messages)
        }
        for c in user_convs
    ]


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str, current_user = Depends(get_api_key)):
    """Get conversation details."""
    if conv_id not in suite.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv = suite.conversations[conv_id]
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": conv.id,
        "title": conv.title,
        "model_id": conv.model_id,
        "messages": conv.messages,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at
    }


@app.post("/api/conversations/message")
async def send_message(msg_data: MessageSend, current_user = Depends(get_api_key)):
    """Send a message in a conversation."""
    if msg_data.conversation_id not in suite.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv = suite.conversations[msg_data.conversation_id]
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = suite.send_message(
        msg_data.conversation_id,
        msg_data.message,
        msg_data.use_rag,
        msg_data.rag_top_k
    )
    
    return {
        "response": result["response"],
        "context_used": result["context_used"],
        "context_docs": result["context_docs"]
    }


# Document endpoints
@app.post("/api/documents")
async def ingest_document(doc_data: DocumentIngest, current_user = Depends(get_api_key)):
    """Ingest a document for RAG."""
    doc = suite.ingest_document(
        doc_data.file_path,
        doc_data.chunk_size,
        doc_data.chunk_overlap
    )
    return {
        "id": doc.id,
        "name": doc.name,
        "size_bytes": doc.size_bytes,
        "chunk_count": doc.chunk_count,
        "uploaded_at": doc.uploaded_at
    }


@app.get("/api/documents")
async def list_documents(current_user = Depends(get_api_key)):
    """List all documents."""
    return [
        {
            "id": d.id,
            "name": d.name,
            "size_bytes": d.size_bytes,
            "chunk_count": d.chunk_count,
            "uploaded_at": d.uploaded_at
        }
        for d in suite.documents.values()
    ]


@app.get("/api/documents/search")
async def search_documents(query: str, top_k: int = 5, current_user = Depends(get_api_key)):
    """Search documents using RAG."""
    results = suite.search_documents(query, top_k)
    return {"query": query, "results": results}


# Shareable link endpoints
@app.post("/api/share")
async def create_share_link(link_data: ShareLinkCreate, current_user = Depends(get_api_key)):
    """Create a shareable link for a conversation."""
    if link_data.conversation_id not in suite.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conv = suite.conversations[link_data.conversation_id]
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Generate share token
    share_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=link_data.expires_in_hours)
    
    share_links[share_token] = {
        "conversation_id": link_data.conversation_id,
        "created_by": current_user.id,
        "expires_at": expires_at.isoformat()
    }
    
    return {
        "share_token": share_token,
        "share_url": f"/share/{share_token}",
        "expires_at": expires_at.isoformat()
    }


@app.get("/api/share/{share_token}")
async def access_shared_conversation(share_token: str):
    """Access a shared conversation via link."""
    if share_token not in share_links:
        raise HTTPException(status_code=404, detail="Invalid share link")
    
    link_data = share_links[share_token]
    
    # Check expiration
    if datetime.now() > datetime.fromisoformat(link_data["expires_at"]):
        del share_links[share_token]
        raise HTTPException(status_code=410, detail="Share link expired")
    
    conv_id = link_data["conversation_id"]
    conv = suite.conversations[conv_id]
    
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": conv.messages,
        "is_shared": True
    }


@app.post("/api/share/{share_token}/message")
async def send_shared_message(share_token: str, message: str):
    """Send a message to a shared conversation."""
    if share_token not in share_links:
        raise HTTPException(status_code=404, detail="Invalid share link")
    
    link_data = share_links[share_token]
    
    # Check expiration
    if datetime.now() > datetime.fromisoformat(link_data["expires_at"]):
        del share_links[share_token]
        raise HTTPException(status_code=410, detail="Share link expired")
    
    conv_id = link_data["conversation_id"]
    result = suite.send_message(conv_id, message, use_rag=True)
    
    return {
        "response": result["response"],
        "context_used": result["context_used"]
    }


# Analytics endpoint
@app.get("/api/analytics")
async def get_analytics(days: int = 30, current_user = Depends(get_api_key)):
    """Get analytics report."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    report = suite.get_analytics_report(days)
    return report


# Solana token endpoints
@app.get("/api/solana/balance/{wallet_address}")
async def get_token_balance(wallet_address: str):
    """Get token balance for a wallet."""
    if not solana_manager:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    balance = await solana_manager.get_token_balance(wallet_address)
    return {"wallet": wallet_address, "balance": balance}


@app.get("/api/solana/access/{wallet_address}")
async def check_solana_access(wallet_address: str):
    """Check if wallet has access to inference."""
    if not token_gating:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    access = await token_gating.check_access(wallet_address)
    return access


@app.post("/api/solana/pay")
async def process_solana_payment(payment: SolanaPayment):
    """Process Solana token payment for inference."""
    if not token_gating:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    result = await token_gating.process_payment(
        payment.wallet_address,
        payment.conversation_id
    )
    return result


@app.post("/api/solana/stake")
async def stake_tokens(stake_data: StakeTokens):
    """Stake tokens in the liquid staking pool."""
    if not solana_manager:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    signature = await solana_manager.stake_tokens(
        stake_data.amount,
        stake_data.pool_address
    )
    return {"success": True, "signature": signature}


@app.post("/api/solana/unstake")
async def unstake_tokens(unstake_data: UnstakeTokens):
    """Unstake tokens from the pool."""
    if not solana_manager:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    signature = await solana_manager.unstake_tokens(
        unstake_data.amount,
        unstake_data.pool_address
    )
    return {"success": True, "signature": signature}


@app.get("/api/solana/stake/{wallet_address}")
async def get_stake_info(wallet_address: str):
    """Get staking information for a wallet."""
    if not solana_manager:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    info = await solana_manager.get_stake_info(wallet_address)
    return info


@app.post("/api/solana/claim")
async def claim_rewards(wallet_address: str, pool_address: str):
    """Claim staking rewards."""
    if not solana_manager:
        raise HTTPException(status_code=503, detail="Solana integration not available")
    
    signature = await solana_manager.claim_rewards(pool_address)
    return {"success": True, "signature": signature}


# Web UI
@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Serve web UI for inference access."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Enterprise LLM Suite</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
        .card { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card h2 { margin-bottom: 15px; color: #333; }
        .input-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 500; color: #555; }
        input, textarea, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        textarea { min-height: 100px; resize: vertical; }
        button { background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        button:hover { background: #5568d3; }
        .chat-messages { max-height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; background: #fafafa; }
        .message { margin-bottom: 15px; padding: 10px; border-radius: 5px; }
        .message.user { background: #e3f2fd; }
        .message.assistant { background: #f3e5f5; }
        .message .role { font-weight: bold; margin-bottom: 5px; font-size: 12px; color: #666; }
        .api-info { background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107; margin-bottom: 20px; }
        .api-info code { background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Enterprise LLM Suite</h1>
            <p>Hosted Inference with Shareable Links</p>
        </div>
        
        <div class="api-info">
            <strong>API Access:</strong> Use your API key in the <code>X-API-Key</code> header to access the API.
            <br>Base URL: <code>http://localhost:8000</code>
        </div>
        
        <div class="card">
            <h2>Quick Chat</h2>
            <div class="input-group">
                <label>API Key</label>
                <input type="password" id="apiKey" placeholder="Enter your API key">
            </div>
            <div class="input-group">
                <label>Message</label>
                <textarea id="message" placeholder="Type your message..."></textarea>
            </div>
            <button onclick="sendMessage()">Send Message</button>
            <div id="chatMessages" class="chat-messages"></div>
        </div>
        
        <div class="card">
            <h2>Create Shareable Link</h2>
            <div class="input-group">
                <label>Conversation ID</label>
                <input type="text" id="convId" placeholder="Enter conversation ID">
            </div>
            <div class="input-group">
                <label>Expires In (hours)</label>
                <input type="number" id="expiresIn" value="24">
            </div>
            <button onclick="createShareLink()">Create Link</button>
            <div id="shareResult" style="margin-top: 15px;"></div>
        </div>
    </div>
    
    <script>
        async function sendMessage() {
            const apiKey = document.getElementById('apiKey').value;
            const message = document.getElementById('message').value;
            const chatDiv = document.getElementById('chatMessages');
            
            if (!apiKey || !message) {
                alert('Please enter API key and message');
                return;
            }
            
            // Add user message
            chatDiv.innerHTML += `<div class="message user"><div class="role">You</div>${message}</div>`;
            
            try {
                const response = await fetch('/api/conversations/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': apiKey
                    },
                    body: JSON.stringify({
                        conversation_id: 'demo',
                        message: message,
                        use_rag: true
                    })
                });
                
                const data = await response.json();
                chatDiv.innerHTML += `<div class="message assistant"><div class="role">Assistant</div>${data.response}</div>`;
            } catch (error) {
                chatDiv.innerHTML += `<div class="message assistant"><div class="role">Error</div>${error.message}</div>`;
            }
            
            document.getElementById('message').value = '';
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }
        
        async function createShareLink() {
            const apiKey = document.getElementById('apiKey').value;
            const convId = document.getElementById('convId').value;
            const expiresIn = document.getElementById('expiresIn').value;
            const resultDiv = document.getElementById('shareResult');
            
            try {
                const response = await fetch('/api/share', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': apiKey
                    },
                    body: JSON.stringify({
                        conversation_id: convId,
                        expires_in_hours: parseInt(expiresIn)
                    })
                });
                
                const data = await response.json();
                const shareUrl = window.location.origin + data.share_url;
                resultDiv.innerHTML = `<strong>Share Link:</strong> <a href="${shareUrl}" target="_blank">${shareUrl}</a><br><small>Expires: ${data.expires_at}</small>`;
            } catch (error) {
                resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
            }
        }
    </script>
</body>
</html>
    """
    return html


# Staking UI
@app.get("/staking", response_class=HTMLResponse)
async def staking_ui():
    """Serve staking interface."""
    staking_html_path = Path(__file__).parent / "staking_ui.html"
    if staking_html_path.exists():
        with open(staking_html_path, 'r') as f:
            return f.read()
    return HTMLResponse(content="Staking UI not found", status_code=404)


# Liquid Endpoints UI
@app.get("/liquid-endpoints", response_class=HTMLResponse)
async def liquid_endpoints_ui():
    """Serve liquid staked endpoints interface."""
    liquid_html_path = Path(__file__).parent / "liquid_endpoints_ui.html"
    if liquid_html_path.exists():
        with open(liquid_html_path, 'r') as f:
            return f.read()
    return HTMLResponse(content="Liquid Endpoints UI not found", status_code=404)


# Decentralized Node UI
@app.get("/decentralized-node", response_class=HTMLResponse)
async def decentralized_node_ui():
    """Serve decentralized inference node interface."""
    decentralized_html_path = Path(__file__).parent / "decentralized_node_ui.html"
    if decentralized_html_path.exists():
        with open(decentralized_html_path, 'r') as f:
            return f.read()
    return HTMLResponse(content="Decentralized Node UI not found", status_code=404)


# Domain Folder UI
@app.get("/domain-folder", response_class=HTMLResponse)
async def domain_folder_ui():
    """Serve sovereign domain folder interface."""
    domain_html_path = Path(__file__).parent / "domain_folder_ui.html"
    if domain_html_path.exists():
        with open(domain_html_path, 'r') as f:
            return f.read()
    return HTMLResponse(content="Domain Folder UI not found - see DOMAIN_NODE_PRODUCT.md for setup", status_code=404)


# Shared conversation web UI
@app.get("/share/{share_token}", response_class=HTMLResponse)
async def shared_conversation_ui(share_token: str):
    """Web UI for shared conversations."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Shared Conversation</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .chat-messages {{ max-height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; background: #fafafa; }}
        .message {{ margin-bottom: 15px; padding: 10px; border-radius: 5px; }}
        .message.user {{ background: #e3f2fd; }}
        .message.assistant {{ background: #f3e5f5; }}
        .message .role {{ font-weight: bold; margin-bottom: 5px; font-size: 12px; color: #666; }}
        input, textarea {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; margin-bottom: 10px; }}
        button {{ background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Shared Conversation</h1>
            <p>Share Token: {share_token}</p>
        </div>
        
        <div class="card">
            <div id="chatMessages" class="chat-messages"></div>
            <textarea id="message" placeholder="Type your message..."></textarea>
            <button onclick="sendMessage()">Send Message</button>
        </div>
    </div>
    
    <script>
        const shareToken = '{share_token}';
        
        async function loadConversation() {{
            try {{
                const response = await fetch(`/api/share/${{shareToken}}`);
                const data = await response.json();
                const chatDiv = document.getElementById('chatMessages');
                data.messages.forEach(msg => {{
                    chatDiv.innerHTML += `<div class="message ${{msg.role}}"><div class="role">${{msg.role}}</div>${{msg.content}}</div>`;
                }});
            }} catch (error) {{
                console.error('Failed to load conversation:', error);
            }}
        }}
        
        async function sendMessage() {{
            const message = document.getElementById('message').value;
            if (!message) return;
            
            const chatDiv = document.getElementById('chatMessages');
            chatDiv.innerHTML += `<div class="message user"><div class="role">You</div>${{message}}</div>`;
            
            try {{
                const response = await fetch(`/api/share/${{shareToken}}/message`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ message }})
                }});
                const data = await response.json();
                chatDiv.innerHTML += `<div class="message assistant"><div class="role">Assistant</div>${{data.response}}</div>`;
            }} catch (error) {{
                chatDiv.innerHTML += `<div class="message assistant"><div class="role">Error</div>${{error.message}}</div>`;
            }}
            
            document.getElementById('message').value = '';
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }}
        
        loadConversation();
    </script>
</body>
</html>
    """
    return html


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the web server."""
    print(f"🚀 Starting Enterprise LLM Suite Server on http://{host}:{port}")
    print(f"📡 API available at http://{host}:{port}/api")
    print(f"🌐 Web UI available at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
