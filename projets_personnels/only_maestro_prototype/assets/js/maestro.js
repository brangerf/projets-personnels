function initializeMaestro() {
    const runButton = document.getElementById('maestro-run-button');
    const input = document.getElementById('maestro-input');
    const statusArea = document.getElementById('maestro-status-area');
    const resultsArea = document.getElementById('maestro-results-area');
    const maestroModelSelector = document.getElementById('maestro-model-selector');
    const complexitySlider = document.getElementById('maestro-complexity-slider');
    const complexityLabel = document.getElementById('maestro-complexity-label');

    complexitySlider.addEventListener('input', () => {
        complexityLabel.textContent = complexitySlider.value === '0' ? 'Simple' : 'Complexe';
    });

    runButton.addEventListener('click', () => {
        const prompt = input.value.trim();
        if (!prompt) {
            alert("Veuillez entrer une demande pour Maestro.");
            return;
        }

        runButton.disabled = true;
        input.disabled = true;
        statusArea.textContent = '';
        resultsArea.innerHTML = '';
        resultsArea.classList.remove('error');
        resultsArea.style.display = 'none';

        const selectedModel = maestroModelSelector.value;
        if (!selectedModel || selectedModel === 'OLLAMA_OFFLINE') {
            maestro_api.displayError("Veuillez sélectionner un modèle valide pour Maestro.");
            return;
        }

        const complexity = complexitySlider.value === '0' ? 'simple' : 'complexe';
        window.pywebview.api.invoke_maestro(prompt, selectedModel, complexity);
    });
}

window.maestro_api = {
    _currentStepElement: null,
    _currentStepDiv: null,

    updateStatus: (message) => {
        const statusArea = document.getElementById('maestro-status-area');
        if (statusArea) statusArea.innerHTML = message;
    },

    startWorkflowMessage: () => {
        const resultsArea = document.getElementById('maestro-results-area');
        resultsArea.innerHTML = '';
        resultsArea.classList.remove('error');
        resultsArea.style.display = 'block';
        window.maestro_api._currentStepElement = null;
        window.maestro_api._currentStepDiv = null;
    },

    showWorkflowStepResult: (title, initialContent = '') => {
        const resultsArea = document.getElementById('maestro-results-area');
        const stepDiv = document.createElement('div');
        stepDiv.className = 'workflow-step';
        stepDiv.dataset.agentTitle = title;

        const titleEl = document.createElement('div');
        titleEl.className = 'workflow-step-title';
        titleEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Agent en cours : ${title}`;
        stepDiv.appendChild(titleEl);

        const contentEl = document.createElement('div');
        contentEl.className = 'workflow-step-content';
        contentEl.textContent = initialContent;
        stepDiv.appendChild(contentEl);

        resultsArea.appendChild(stepDiv);
        window.maestro_api._currentStepElement = contentEl;
        window.maestro_api._currentStepDiv = stepDiv;
        resultsArea.scrollTop = resultsArea.scrollHeight;
    },

    appendToWorkflowResponse: (textChunk) => {
        if (window.maestro_api._currentStepElement) {
            window.maestro_api._currentStepElement.textContent += textChunk;
            const resultsArea = document.getElementById('maestro-results-area');
            if (resultsArea) resultsArea.scrollTop = resultsArea.scrollHeight;
        }
    },
    
    finalizeAgentStep: (title, finalContent) => {
        const resultsArea = document.getElementById('maestro-results-area');
        
        const escapedTitle = title.replace(/'/g, "\\'");
        
        const stepToFinalize = resultsArea.querySelector(`.workflow-step[data-agent-title='${escapedTitle}']:not(.finalized)`);
        
        if (stepToFinalize) {
            stepToFinalize.classList.add('finalized');

            const titleEl = stepToFinalize.querySelector('.workflow-step-title');
            const contentEl = stepToFinalize.querySelector('.workflow-step-content');

            if (titleEl) {
                titleEl.innerHTML = `<i class="fa-solid fa-check-circle" style="color: #28a745;"></i> ${title}`;
            }
            
            if (contentEl) {
                processFinalContent(contentEl, finalContent);
            }
            
            resultsArea.scrollTop = resultsArea.scrollHeight;
        } else {
            console.warn(`Impossible de trouver une étape non finalisée pour l'agent : "${title}"`);
        }
    },

    displayError: (errorMessage) => {
        const resultsArea = document.getElementById('maestro-results-area');
        const statusArea = document.getElementById('maestro-status-area');

        if (resultsArea) {
            resultsArea.innerHTML = '';
            resultsArea.textContent = errorMessage;
            resultsArea.classList.add('error');
            resultsArea.style.display = 'block';
        }
        if (statusArea) statusArea.textContent = 'Une erreur est survenue.';
        window.maestro_api.enableControls();
    },

    enableControls: () => {
        const runButton = document.getElementById('maestro-run-button');
        const input = document.getElementById('maestro-input');
        if (runButton) runButton.disabled = false;
        if (input) input.disabled = false;
    }
};