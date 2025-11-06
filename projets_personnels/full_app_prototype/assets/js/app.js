let messageHistory = [];
let currentAiMessageElement = null;
let currentStreamContent = '';
let workflowGraph, workflowCanvas;
let currentNodeBeingConfigured = null;
let currentWorkflowMessageElement = null;
let nodeRegistry = {};
let nodeCategories = {};

const modelSelector = document.getElementById('model-selector');

window.addEventListener('pywebviewready', async () => {
    const models = await window.pywebview.api.get_installed_models();
    updateModelSelector(models);
    const modalSelect = document.getElementById('modal-model-select');
    const maestroSelect = document.getElementById('maestro-model-selector');
    if (models && models[0] !== 'OLLAMA_OFFLINE') {
        const options = models.map(m => `<option value="${m}">${m}</option>`).join('');
        modalSelect.innerHTML = options;
        if (maestroSelect) maestroSelect.innerHTML = options;
    }

    const options = await window.pywebview.api.get_node_options();
    options.forEach(option => {
        nodeRegistry[option.value] = option;
        if (!nodeCategories[option.category]) {
            nodeCategories[option.category] = [];
        }
        nodeCategories[option.category].push(option);
    });
    updateNodeSelector();

    await defineWorkflowNodes();
});

document.addEventListener('DOMContentLoaded', () => {
    initializeNavigation();
    initializeChat();
    initializeWorkflow();
    initializeSequences();
    initializeExecutionSelectors();
    initializeModal();
    initializeLoadWorkflowModal();
    initializeMaestro();
    initializeArtifactViewer();
    window.addEventListener('resize', resizeWorkflowCanvas);
});

function updateModelSelector(models) {
    if (!models || models.length === 0) {
        modelSelector.innerHTML = '<option>Aucun modèle trouvé</option>';
        return;
    }
    if (models[0] === 'OLLAMA_OFFLINE') {
        modelSelector.innerHTML = '<option>Ollama non démarré</option>';
        if (document.getElementById('chat-view').classList.contains('active')) {
            appendErrorMessage('Erreur: Ollama ne semble pas être en cours d\'exécution.');
        }
        return;
    }
    modelSelector.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
}

function enableControls() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    messageInput.disabled = false;
    modelSelector.disabled = false;
    messageInput.focus();
    if (messageInput.value.trim() !== '') {
        sendButton.disabled = false;
        sendButton.classList.add('enabled');
    }
}