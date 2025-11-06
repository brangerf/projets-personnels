function initializeChat() {
    const newChatButton = document.getElementById('new-chat-button');
    const sendButton = document.getElementById('send-button');
    const messageInput = document.getElementById('message-input');

    newChatButton.addEventListener('click', startNewChat);
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = (messageInput.scrollHeight) + 'px';
        if (messageInput.value.trim()) { sendButton.disabled = false; sendButton.classList.add('enabled'); }
        else { sendButton.disabled = true; sendButton.classList.remove('enabled'); }
    });
    startNewChat();
}

async function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const workflowSelector = document.getElementById('workflow-selector');
    const sequenceSelector = document.getElementById('sequence-selector');

    const messageText = messageInput.value.trim();
    if (!messageText) return;

    const selectedWorkflow = workflowSelector.value;
    const selectedSequence = sequenceSelector.value;
    const selectedModel = modelSelector.value;

    appendMessageToUI(messageText, 'user');
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendButton.disabled = true;
    sendButton.classList.remove('enabled');
    messageInput.disabled = true;
    modelSelector.disabled = true;

    if (selectedWorkflow) {
        window.pywebview.api.run_workflow_from_chat_stream(selectedWorkflow, messageText, selectedModel);
        return;
    } else if (selectedSequence) {
        const resultElement = appendMessageToUI('', 'workflow-bot');
        const result = await window.pywebview.api.run_sequence_from_chat(selectedSequence, messageText, selectedModel);
        displayRichContent(resultElement, result);
    } else {
        messageHistory.push({ role: 'user', content: messageText });
        currentAiMessageElement = appendMessageToUI('', 'ai');
        window.pywebview.api.send_message_to_ollama(messageHistory, selectedModel);
        return;
    }
    enableControls();
}

function startNewChat() {
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    messageHistory = [];
    chatContainer.innerHTML = '';
    messageInput.value = '';
    currentStreamContent = '';
    currentWorkflowMessageElement = null;
    currentAiMessageElement = null;
    messageInput.focus();
}

function appendMessageToUI(content, role) {
    const chatContainer = document.getElementById('chat-container');
    const messageContainer = document.createElement('div');
    messageContainer.className = `${role}-message`;
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper';
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    if (role === 'user') {
        avatar.classList.add('user-avatar');
        avatar.innerHTML = '<i class="fa-solid fa-user"></i>';
    } else if (role === 'workflow-bot') {
        avatar.classList.add('workflow-bot-avatar');
        avatar.innerHTML = '<i class="fa-solid fa-cogs"></i>';
    } else {
        avatar.classList.add('ai-avatar');
        avatar.innerHTML = '<i class="fa-solid fa-brain"></i>';
    }
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = (role === 'user') ? '' : content || '<span class="thinking-indicator"></span>';
    if (role === 'user') messageContent.textContent = content;
    
    wrapper.appendChild(avatar);
    wrapper.appendChild(messageContent);
    messageContainer.appendChild(wrapper);
    chatContainer.appendChild(messageContainer);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return messageContent;
}

function appendErrorMessage(text) {
    const chatContainer = document.getElementById('chat-container');
    const errorDiv = document.createElement('div');
    errorDiv.style.textAlign = 'center';
    errorDiv.style.padding = '20px';
    errorDiv.style.color = '#ff8a8a';
    errorDiv.textContent = text;
    chatContainer.appendChild(errorDiv);
}

function initializeExecutionSelectors() {
    const workflowSelector = document.getElementById('workflow-selector');
    const sequenceSelector = document.getElementById('sequence-selector');
    workflowSelector.addEventListener('change', () => {
        if (workflowSelector.value) sequenceSelector.value = "";
    });
    sequenceSelector.addEventListener('change', () => {
        if (sequenceSelector.value) workflowSelector.value = "";
    });
    document.getElementById('clear-selectors-button').addEventListener('click', () => {
        workflowSelector.value = "";
        sequenceSelector.value = "";
    });
}

async function populateExecutionSelectors() {
    const workflowSelector = document.getElementById('workflow-selector');
    const sequenceSelector = document.getElementById('sequence-selector');
    const workflows = await window.pywebview.api.list_workflows();
    const sequences = await window.pywebview.api.list_sequences();
    const currentWf = workflowSelector.value;
    const currentSq = sequenceSelector.value;
    workflowSelector.innerHTML = '<option value="">Exécuter un Workflow...</option>' + workflows.map(f => `<option value="${f}">${f}</option>`).join('');
    sequenceSelector.innerHTML = '<option value="">Exécuter une Séquence...</option>' + sequences.map(f => `<option value="${f}">${f}</option>`).join('');
    workflowSelector.value = currentWf;
    sequenceSelector.value = currentSq;
}

window.api = {
    appendToResponse: (chunk) => {
        const chatContainer = document.getElementById('chat-container');
        if (!currentAiMessageElement) return;
        if (currentAiMessageElement.querySelector('.thinking-indicator')) {
            currentAiMessageElement.innerHTML = '';
        }
        currentStreamContent += chunk;
        const streamDiv = document.createElement('div');
        streamDiv.className = 'streaming-text';
        streamDiv.textContent = currentStreamContent;
        currentAiMessageElement.innerHTML = '';
        currentAiMessageElement.appendChild(streamDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    },
    finalizeResponse: () => {
        if (!currentAiMessageElement || !currentStreamContent) {
            enableControls();
            return;
        }
        messageHistory.push({ role: 'assistant', content: currentStreamContent });
        displayRichContent(currentAiMessageElement, currentStreamContent);
        currentStreamContent = '';
        currentAiMessageElement = null;
        enableControls();
    },
    showError: (errorMessage) => {
        if (currentAiMessageElement) {
            currentAiMessageElement.parentElement.parentElement.remove();
        }
        appendErrorMessage(errorMessage);
        currentStreamContent = '';
        currentAiMessageElement = null;
        enableControls();
    },
    startWorkflowMessage: () => {
        currentWorkflowMessageElement = appendMessageToUI('', 'workflow-bot');
    },
    showWorkflowStepResult: (title, initialContent) => {
        const chatContainer = document.getElementById('chat-container');
        if (document.getElementById('maestro-view').classList.contains('active')) return;
        if (!currentWorkflowMessageElement) return;
        
        const stepDiv = document.createElement('div');
        stepDiv.className = 'workflow-step';
        const titleDiv = document.createElement('div');
        titleDiv.className = 'workflow-step-title';
        titleDiv.textContent = title;
        const contentDiv = document.createElement('div');
        contentDiv.className = 'workflow-step-content';
        
        stepDiv.appendChild(titleDiv);
        stepDiv.appendChild(contentDiv);
        currentWorkflowMessageElement.appendChild(stepDiv);
        
        if (initialContent) {
            processFinalContent(contentDiv, initialContent);
        } else {
            contentDiv.innerHTML = '<span class="thinking-indicator"></span>';
        }
        chatContainer.scrollTop = chatContainer.scrollHeight;
    },
    updateLastStepResult: (content) => {
        const chatContainer = document.getElementById('chat-container');
        if (document.getElementById('maestro-view').classList.contains('active')) return;
        if (!currentWorkflowMessageElement) return;
        const lastStep = currentWorkflowMessageElement.querySelector('.workflow-step:last-child .workflow-step-content');
        if (lastStep) {
            processFinalContent(lastStep, content);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    },
    appendToWorkflowResponse: (chunk) => {
        const chatContainer = document.getElementById('chat-container');
        if (document.getElementById('maestro-view').classList.contains('active')) return;
        if (!currentWorkflowMessageElement) return;
        const lastStep = currentWorkflowMessageElement.querySelector('.workflow-step:last-child .workflow-step-content');
        if (lastStep) {
            if (lastStep.querySelector('.thinking-indicator')) {
                lastStep.innerHTML = '';
            }
            lastStep.textContent += chunk;
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    },
    hideLastStep: () => {
        if (document.getElementById('maestro-view').classList.contains('active')) return;
        if (!currentWorkflowMessageElement) return;
        const lastStep = currentWorkflowMessageElement.querySelector('.workflow-step:last-child');
        if (lastStep) {
            lastStep.style.display = 'none';
        }
    },
    finalizeWorkflowResponseWithData: (rawContent) => {
        if (document.getElementById('maestro-view').classList.contains('active')) {
            const resultsArea = document.getElementById('maestro-results-area');
            const runButton = document.getElementById('maestro-run-button');
            const input = document.getElementById('maestro-input');
            const statusArea = document.getElementById('maestro-status-area');

            if (resultsArea) {
                displayRichContent(resultsArea, rawContent);
                resultsArea.style.display = 'block';
            }
            if (runButton) runButton.disabled = false;
            if (input) input.disabled = false;
            if (statusArea) statusArea.textContent = 'Composition terminée.';
        } else {
            if (!currentWorkflowMessageElement) {
                enableControls();
                return;
            }
            
            let contentToDisplay = rawContent;
            const trimmedContent = rawContent.trim().toLowerCase();
            const isHtmlOutput = trimmedContent.startsWith('<!doctype html>') || (trimmedContent.startsWith('<html') && trimmedContent.endsWith('</html>'));

            if (isHtmlOutput) {
                contentToDisplay = '```html\n' + rawContent + '\n```';
            }
            
            displayRichContent(currentWorkflowMessageElement, contentToDisplay);
            currentWorkflowMessageElement = null;
            enableControls();
        }
    }
};