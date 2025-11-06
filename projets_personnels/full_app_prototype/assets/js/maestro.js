
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

    updateStatus: (message) => {
        const statusArea = document.getElementById('maestro-status-area');
        if (statusArea) statusArea.innerHTML = message;
    },

    startWorkflowMessage: () => {
        const resultsArea = document.getElementById('maestro-results-area');
        resultsArea.innerHTML = '';
        resultsArea.classList.remove('error');
        resultsArea.style.display = 'block';
        this._currentStepElement = null;
    },

    showWorkflowStepResult: (title, initialContent = '') => {
        const resultsArea = document.getElementById('maestro-results-area');
        const stepDiv = document.createElement('div');
        stepDiv.className = 'workflow-step';

        const titleEl = document.createElement('div');
        titleEl.className = 'workflow-step-title';
        titleEl.innerHTML = `<i class="fa-solid fa-microchip"></i> Agent : ${title}`;
        stepDiv.appendChild(titleEl);

        const contentEl = document.createElement('div');
        contentEl.className = 'workflow-step-content';
        contentEl.textContent = initialContent;
        stepDiv.appendChild(contentEl);

        resultsArea.appendChild(stepDiv);
        this._currentStepElement = contentEl;
        resultsArea.scrollTop = resultsArea.scrollHeight;
    },

    appendToWorkflowResponse: (textChunk) => {
        if (this._currentStepElement) {
            this._currentStepElement.textContent += textChunk;
            this._currentStepElement.parentElement.parentElement.scrollTop = this._currentStepElement.parentElement.parentElement.scrollHeight;
        }
    },

    showBeautifierLoading: (message) => {
        const resultsArea = document.getElementById('maestro-results-area');
        const loaderDiv = document.createElement('div');
        loaderDiv.className = 'maestro-finalizing-loader';
        loaderDiv.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>${message}</span>`;
        resultsArea.appendChild(loaderDiv);
        resultsArea.scrollTop = resultsArea.scrollHeight;
    },

    displayFinalBeautifiedResult: (htmlContent) => {
        const resultsArea = document.getElementById('maestro-results-area');
        const loader = resultsArea.querySelector('.maestro-finalizing-loader');
        if (loader) {
            loader.remove();
        }

        const finalResultDiv = document.createElement('div');
        finalResultDiv.className = 'maestro-final-report';
        resultsArea.appendChild(finalResultDiv);
        
        processFinalContent(finalResultDiv, htmlContent);
        
        resultsArea.scrollTop = resultsArea.scrollHeight;
        window.maestro_api.enableControls();
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