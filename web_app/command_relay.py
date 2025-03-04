from fastapi import Depends, HTTPException, Header, Request, APIRouter
from typing import Dict, List, Any, Optional
import uuid
import time
import logging
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models
class ClientRegistration(BaseModel):
    client_id: Optional[str] = None
    client_type: str
    hostname: Optional[str] = "unknown"
    ip_address: Optional[str] = None
    timestamp: Optional[float] = None

class ClientHeartbeat(BaseModel):
    client_id: str
    timestamp: Optional[float] = None
    status: str = "active"
    last_command_id: Optional[str] = None

class CommandResult(BaseModel):
    command_id: str
    client_id: str
    result: Dict[str, Any]
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    timestamp: Optional[float] = None

class CommandRequest(BaseModel):
    client_id: str
    command: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timeout: Optional[int] = 60  # Timeout in seconds

class CommandStatus(BaseModel):
    command_id: str
    client_id: str
    command: str
    params: Dict[str, Any]
    status: str  # pending, running, completed, failed, timeout
    created_at: float
    updated_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None

class ClientInfo(BaseModel):
    client_id: str
    client_type: str
    hostname: str
    ip_address: Optional[str] = None
    last_seen: float
    status: str
    last_command_id: Optional[str] = None

# In-memory storage
clients: Dict[str, ClientInfo] = {}
commands: List[CommandStatus] = []

# Create router
router = APIRouter(prefix="/api", tags=["command-relay"])

# Authentication dependency
async def get_api_key(x_api_key: str = Header(..., description="API Key for authentication")):
    """Validate API key."""
    from .config import get_settings
    settings = get_settings()
    
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

# Utility functions
def cleanup_old_data():
    """Remove old commands and inactive clients."""
    global clients, commands
    current_time = time.time()
    
    # Remove commands older than 7 days
    commands = [cmd for cmd in commands if current_time - cmd.created_at < 7 * 24 * 60 * 60]
    
    # Remove clients inactive for more than 1 hour
    inactive_clients = []
    for client_id, client in clients.items():
        if current_time - client.last_seen > 60 * 60:  # 1 hour
            inactive_clients.append(client_id)
    
    for client_id in inactive_clients:
        del clients[client_id]
    
    if inactive_clients:
        logger.info(f"Removed {len(inactive_clients)} inactive clients")

# Endpoints
@router.post("/clients/register", response_model=ClientInfo)
async def register_client(
    registration: ClientRegistration,
    request: Request,
    api_key: str = Depends(get_api_key)
):
    """Register a new client or update existing client information."""
    current_time = time.time()
    
    # Generate client_id if not provided
    client_id = registration.client_id or str(uuid.uuid4())
    
    # Get client IP address if not provided
    client_ip = registration.ip_address or request.client.host
    
    # Create or update client info
    clients[client_id] = ClientInfo(
        client_id=client_id,
        client_type=registration.client_type,
        hostname=registration.hostname,
        ip_address=client_ip,
        last_seen=current_time,
        status="active"
    )
    
    logger.info(f"Client registered: {client_id} ({registration.hostname})")
    return clients[client_id]

@router.post("/clients/heartbeat", response_model=ClientInfo)
async def update_heartbeat(
    heartbeat: ClientHeartbeat,
    api_key: str = Depends(get_api_key)
):
    """Update client heartbeat."""
    current_time = heartbeat.timestamp or time.time()
    client_id = heartbeat.client_id
    
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update client info
    client = clients[client_id]
    client.last_seen = current_time
    client.status = heartbeat.status
    
    if heartbeat.last_command_id:
        client.last_command_id = heartbeat.last_command_id
    
    logger.debug(f"Heartbeat received from client: {client_id}")
    return client

@router.get("/clients", response_model=List[ClientInfo])
async def list_clients(
    api_key: str = Depends(get_api_key)
):
    """List all registered clients."""
    # Run cleanup before listing clients
    cleanup_old_data()
    
    return list(clients.values())

@router.get("/commands/pending", response_model=List[CommandStatus])
async def get_pending_commands(
    client_id: str,
    api_key: str = Depends(get_api_key)
):
    """Get pending commands for a specific client."""
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update client's last seen timestamp
    clients[client_id].last_seen = time.time()
    
    # Find pending commands for this client
    pending_commands = [
        cmd for cmd in commands 
        if cmd.client_id == client_id and cmd.status == "pending"
    ]
    
    # Mark commands as "running"
    for cmd in pending_commands:
        cmd.status = "running"
        cmd.updated_at = time.time()
    
    return pending_commands

@router.post("/commands/results", response_model=CommandStatus)
async def submit_command_results(
    result: CommandResult,
    api_key: str = Depends(get_api_key)
):
    """Submit command execution results."""
    command_id = result.command_id
    client_id = result.client_id
    
    # Find the command
    command = next((cmd for cmd in commands if cmd.command_id == command_id), None)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    
    # Update command status
    command.status = "completed"
    command.updated_at = result.timestamp or time.time()
    command.result = result.result
    command.exit_code = result.exit_code
    command.stdout = result.stdout
    command.stderr = result.stderr
    
    # Update client's last command
    if client_id in clients:
        clients[client_id].last_command_id = command_id
        clients[client_id].last_seen = command.updated_at
    
    logger.info(f"Command {command_id} completed by client {client_id}")
    return command

@router.post("/commands/send", response_model=CommandStatus)
async def send_command(
    command_request: CommandRequest,
    api_key: str = Depends(get_api_key)
):
    """Send a command to a specific client."""
    client_id = command_request.client_id
    
    if client_id not in clients:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Create a new command
    command_id = str(uuid.uuid4())
    current_time = time.time()
    
    new_command = CommandStatus(
        command_id=command_id,
        client_id=client_id,
        command=command_request.command,
        params=command_request.params or {},
        status="pending",
        created_at=current_time,
        updated_at=current_time
    )
    
    commands.append(new_command)
    
    logger.info(f"Command {command_id} sent to client {client_id}")
    return new_command

@router.get("/commands/{command_id}", response_model=CommandStatus)
async def get_command_status(
    command_id: str,
    api_key: str = Depends(get_api_key)
):
    """Get the status of a specific command."""
    command = next((cmd for cmd in commands if cmd.command_id == command_id), None)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    
    # Check for timeout
    if command.status == "running":
        current_time = time.time()
        if current_time - command.updated_at > 60:  # Default timeout of 60 seconds
            command.status = "timeout"
            command.updated_at = current_time
    
    return command

@router.get("/commands", response_model=List[CommandStatus])
async def list_commands(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    api_key: str = Depends(get_api_key)
):
    """List all commands with optional filtering."""
    # Run cleanup before listing commands
    cleanup_old_data()
    
    # Filter commands
    filtered_commands = commands
    
    if client_id:
        filtered_commands = [cmd for cmd in filtered_commands if cmd.client_id == client_id]
    
    if status:
        filtered_commands = [cmd for cmd in filtered_commands if cmd.status == status]
    
    # Sort by created_at (newest first)
    filtered_commands = sorted(filtered_commands, key=lambda cmd: cmd.created_at, reverse=True)
    
    # Apply limit
    filtered_commands = filtered_commands[:limit]
    
    return filtered_commands

# Scheduled task for cleanup
def start_cleanup_task():
    """Start a background task to periodically clean up old data."""
    import asyncio
    
    async def cleanup_task():
        while True:
            cleanup_old_data()
            await asyncio.sleep(60 * 15)  # Run every 15 minutes
    
    asyncio.create_task(cleanup_task())

# Start cleanup task when the module is imported
from fastapi.routing import APIRouter

@router.on_event("startup")
async def startup_event():
    """Start the cleanup task when the application starts."""
    logger.info("Starting command relay cleanup task")
    start_cleanup_task()
