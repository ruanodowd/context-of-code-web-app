// Command Relay JavaScript Functions

// API Key - This should be securely managed in a production environment
const API_KEY = localStorage.getItem('apiKey') || '';

// DOM Elements
let clientsContainer;
let clientSelect;
let commandsTableBody;
let sendCommandForm;
let refreshClientsBtn;
let refreshCommandsBtn;
let commandDetailsModal;

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM elements
    clientsContainer = document.getElementById('clientsContainer');
    clientSelect = document.getElementById('clientSelect');
    commandsTableBody = document.getElementById('commandsTableBody');
    sendCommandForm = document.getElementById('sendCommandForm');
    refreshClientsBtn = document.getElementById('refreshClientsBtn');
    refreshCommandsBtn = document.getElementById('refreshCommandsBtn');
    
    // Initialize Bootstrap modal
    commandDetailsModal = new bootstrap.Modal(document.getElementById('commandDetailsModal'));
    
    // Add event listeners
    if (sendCommandForm) {
        sendCommandForm.addEventListener('submit', handleSendCommand);
    }
    
    if (refreshClientsBtn) {
        refreshClientsBtn.addEventListener('click', loadClients);
    }
    
    if (refreshCommandsBtn) {
        refreshCommandsBtn.addEventListener('click', loadCommands);
    }
    
    // Initialize data
    loadClients();
    loadCommands();
    
    // Check for API key
    if (!API_KEY) {
        const key = prompt('Please enter your API key:');
        if (key) {
            localStorage.setItem('apiKey', key);
            location.reload();
        }
    }
    
    // Set up auto-refresh
    setInterval(loadClients, 30000); // Refresh clients every 30 seconds
    setInterval(loadCommands, 60000); // Refresh commands every 60 seconds
});

// Load clients
async function loadClients() {
    if (!clientsContainer || !clientSelect) return;
    
    try {
        clientsContainer.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading clients...</p>
            </div>
        `;
        
        const response = await fetch('/api/clients', {
            headers: {
                'X-API-Key': API_KEY
            }
        });
        
        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        
        const clients = await response.json();
        
        // Update clients container
        clientsContainer.innerHTML = '';
        clientSelect.innerHTML = '<option value="" selected disabled>Choose a client...</option>';
        
        if (clients.length === 0) {
            clientsContainer.innerHTML = '<div class="col-12 text-center py-5"><p>No clients connected</p></div>';
            return;
        }
        
        clients.forEach(client => {
            // Create client card
            const clientCard = document.createElement('div');
            clientCard.className = 'col-md-4 mb-4';
            clientCard.innerHTML = `
                <div class="card client-card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="card-title mb-0">${client.hostname}</h5>
                            <span class="badge ${client.status === 'active' ? 'bg-success' : 'bg-danger'}">${client.status}</span>
                        </div>
                        <h6 class="card-subtitle mb-2 text-muted">${client.client_type}</h6>
                        <p class="card-text">
                            <small>
                                <strong>ID:</strong> ${client.client_id.substring(0, 8)}...<br>
                                <strong>IP:</strong> ${client.ip_address || 'Unknown'}<br>
                                <strong>Last seen:</strong> ${formatTimestamp(client.last_seen)}
                            </small>
                        </p>
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-sm btn-primary send-command-btn" data-client-id="${client.client_id}">
                            Send Command
                        </button>
                    </div>
                </div>
            `;
            
            clientsContainer.appendChild(clientCard);
            
            // Add to select dropdown
            const option = document.createElement('option');
            option.value = client.client_id;
            option.textContent = `${client.hostname} (${client.client_type})`;
            clientSelect.appendChild(option);
        });
        
        // Add event listeners to send command buttons
        document.querySelectorAll('.send-command-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const clientId = btn.dataset.clientId;
                clientSelect.value = clientId;
                document.getElementById('commandInput').focus();
            });
        });
        
    } catch (error) {
        console.error('Error loading clients:', error);
        clientsContainer.innerHTML = `
            <div class="col-12 text-center py-5">
                <p class="text-danger">Error loading clients: ${error.message}</p>
                <button id="retryClientsBtn" class="btn btn-outline-primary mt-2">Retry</button>
            </div>
        `;
        
        document.getElementById('retryClientsBtn').addEventListener('click', loadClients);
    }
}

// Load commands
async function loadCommands() {
    if (!commandsTableBody) return;
    
    try {
        commandsTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Loading commands...</p>
                </td>
            </tr>
        `;
        
        const response = await fetch('/api/commands', {
            headers: {
                'X-API-Key': API_KEY
            }
        });
        
        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        
        const commands = await response.json();
        
        // Update commands table
        commandsTableBody.innerHTML = '';
        
        if (commands.length === 0) {
            commandsTableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">No commands found</td></tr>';
            return;
        }
        
        commands.forEach(command => {
            const row = document.createElement('tr');
            row.className = 'command-row';
            row.dataset.commandId = command.command_id;
            
            const statusClass = {
                'pending': 'badge-pending',
                'running': 'badge-running',
                'completed': 'badge-completed',
                'failed': 'badge-failed',
                'timeout': 'badge-timeout'
            }[command.status] || 'bg-secondary';
            
            row.innerHTML = `
                <td>${command.command_id.substring(0, 8)}...</td>
                <td>${command.client_id.substring(0, 8)}...</td>
                <td>${command.command.length > 30 ? command.command.substring(0, 30) + '...' : command.command}</td>
                <td><span class="badge ${statusClass}">${command.status}</span></td>
                <td>${formatTimestamp(command.created_at)}</td>
                <td>${formatTimestamp(command.updated_at)}</td>
            `;
            
            commandsTableBody.appendChild(row);
        });
        
        // Add event listeners to command rows
        document.querySelectorAll('.command-row').forEach(row => {
            row.addEventListener('click', () => {
                const commandId = row.dataset.commandId;
                showCommandDetails(commandId);
            });
        });
        
    } catch (error) {
        console.error('Error loading commands:', error);
        commandsTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-4">
                    <p class="text-danger">Error loading commands: ${error.message}</p>
                    <button id="retryCommandsBtn" class="btn btn-outline-primary mt-2">Retry</button>
                </td>
            </tr>
        `;
        
        document.getElementById('retryCommandsBtn').addEventListener('click', loadCommands);
    }
}

// Show command details
async function showCommandDetails(commandId) {
    try {
        const response = await fetch(`/api/commands/${commandId}`, {
            headers: {
                'X-API-Key': API_KEY
            }
        });
        
        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        
        const command = await response.json();
        
        // Update modal content
        document.getElementById('modalCommandId').textContent = command.command_id;
        document.getElementById('modalClientId').textContent = command.client_id;
        document.getElementById('modalStatus').textContent = command.status;
        document.getElementById('modalCreated').textContent = formatTimestamp(command.created_at);
        document.getElementById('modalUpdated').textContent = formatTimestamp(command.updated_at);
        document.getElementById('modalExitCode').textContent = command.exit_code !== null ? command.exit_code : 'N/A';
        
        document.getElementById('modalCommand').textContent = command.command;
        document.getElementById('modalParams').textContent = JSON.stringify(command.params, null, 2);
        document.getElementById('modalResult').textContent = command.result ? JSON.stringify(command.result, null, 2) : 'No result';
        document.getElementById('modalStdout').textContent = command.stdout || 'No output';
        document.getElementById('modalStderr').textContent = command.stderr || 'No errors';
        
        // Show modal
        commandDetailsModal.show();
        
    } catch (error) {
        console.error('Error loading command details:', error);
        alert(`Error loading command details: ${error.message}`);
    }
}

// Handle send command form submission
function handleSendCommand(event) {
    event.preventDefault();
    
    const clientId = clientSelect.value;
    const command = document.getElementById('commandInput').value;
    let params = {};
    
    const paramsText = document.getElementById('paramsInput').value.trim();
    if (paramsText) {
        try {
            params = JSON.parse(paramsText);
        } catch (error) {
            alert('Invalid JSON in parameters field');
            return;
        }
    }
    
    sendCommand(clientId, command, params);
}

// Send command
async function sendCommand(clientId, command, params) {
    try {
        const response = await fetch('/api/commands/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({
                client_id: clientId,
                command: command,
                params: params
            })
        });
        
        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        alert(`Command sent successfully! Command ID: ${result.command_id}`);
        
        // Reset form
        document.getElementById('commandInput').value = '';
        document.getElementById('paramsInput').value = '';
        
        // Reload commands
        loadCommands();
        
    } catch (error) {
        console.error('Error sending command:', error);
        alert(`Error sending command: ${error.message}`);
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}
