function updateProgress(data) {
    const loaderText = document.getElementById('loader-text');
    const progressBar = document.getElementById('progress-bar');
    const progressBarContainer = document.querySelector('.progress-bar-container');

    if (loaderText) {
        loaderText.textContent = data.text || 'Progression...';
    }
    if (progressBar) {
        progressBar.style.width = `${data.percent || 0}%`;
    }
    if (progressBarContainer) {
        progressBarContainer.style.display = (data.percent > 0) ? 'block' : 'none';
    }
}

function updateProcessingStatus(message) {
    const loaderText = document.getElementById('processing-loader-text');
    if (loaderText) {
        loaderText.textContent = message;
    }
}

function updateTranscriptionResult(result) {
    const statusText = document.getElementById('status-text');
    const loaderContainer = document.querySelector('#transcription-view .loader-container');
    const resultContainer = document.getElementById('result-container');
    const transcriptionOutput = document.getElementById('transcription-output');
    const transcriptionInfo = document.getElementById('transcription-info');
    const importButton = document.getElementById('import-button');
    const modelSelect = document.getElementById('model-select');
    const sendToProcessingButton = document.getElementById('send-to-processing-button');

    loaderContainer.style.display = 'none';
    importButton.disabled = false;
    modelSelect.disabled = false;
    statusText.style.display = 'block';

    if (result.status === 'success') {
        statusText.innerHTML = `<i class="fa-solid fa-check-circle" style="color: var(--success-color);"></i> Transcription terminée avec succès !`;
        transcriptionOutput.textContent = result.transcript.trim();
        
        let infoHtml = '';
        if (result.duration_minutes) {
            infoHtml += `<span><i class="fa-solid fa-clock"></i> Durée: <strong>${result.duration_minutes.toFixed(1)} min</strong></span>`;
        }
        if (result.language) {
            infoHtml += `<span><i class="fa-solid fa-language"></i> Langue: <strong>${result.language.toUpperCase()}</strong></span>`;
        }
        if (result.device_used) {
            const icon = result.device_used === 'CUDA' ? 'fa-microchip' : 'fa-server';
            infoHtml += `<span><i class="fa-solid ${icon}"></i> Matériel: <strong>${result.device_used}</strong></span>`;
        }
        if (result.was_split) {
            infoHtml += `<span><i class="fa-solid fa-scissors"></i> <strong>Découpage auto activé</strong></span>`;
        }
        transcriptionInfo.innerHTML = infoHtml;

        resultContainer.style.display = 'block';
        sendToProcessingButton.disabled = false;
    } else {
        statusText.innerHTML = `<i class="fa-solid fa-times-circle" style="color: var(--error-color);"></i> Erreur : ${result.message}`;
        resultContainer.style.display = 'none';
        sendToProcessingButton.disabled = true;
    }
}

// --- MODIFICATION: Simplification de la fonction de mise à jour ---
function updateProcessingResult(result) {
    const statusText = document.getElementById('processing-status-text');
    const loaderContainer = document.querySelector('#processing-view .loader-container');
    const resultContainer = document.getElementById('processing-result-container');
    const processingOutput = document.getElementById('processing-output'); // La seule zone d'affichage restante
    const processButton = document.getElementById('process-button');
    const exportTxtButton = document.getElementById('export-txt-button');
    const exportPdfButton = document.getElementById('export-pdf-button');

    loaderContainer.style.display = 'none';
    processButton.disabled = false;
    statusText.style.display = 'block';

    if (result.status === 'success') {
        statusText.textContent = 'Traitement terminé avec succès !';
        
        // On affiche directement le code LaTeX brut. Plus besoin de marked.js
        processingOutput.textContent = result.processed_text.trim();
        
        resultContainer.style.display = 'block';
        exportTxtButton.disabled = false;
        exportPdfButton.disabled = false;
        
    } else {
        statusText.textContent = `Erreur : ${result.message}`;
        resultContainer.style.display = 'none';
        exportTxtButton.disabled = true;
        exportPdfButton.disabled = true;
    }
}

function switchView(viewId) {
    document.querySelectorAll('.view-container').forEach(view => {
        view.classList.remove('active');
    });
    document.querySelectorAll('.nav-button').forEach(button => {
        button.classList.remove('active');
    });
    document.getElementById(viewId)?.classList.add('active');
    document.querySelector(`.nav-button[data-view="${viewId}"]`)?.classList.add('active');
}

function startTranscription(filePath) {
    const modelSelect = document.getElementById('model-select');
    const statusText = document.getElementById('status-text');
    const loaderContainer = document.querySelector('#transcription-view .loader-container');
    const resultContainer = document.getElementById('result-container');
    const importButton = document.getElementById('import-button');
    const progressBar = document.getElementById('progress-bar');
    const progressBarContainer = document.querySelector('.progress-bar-container');

    if (filePath) {
        const selectedModel = modelSelect.value;
        statusText.style.display = 'none';
        loaderContainer.style.display = 'flex';
        resultContainer.style.display = 'none';
        progressBar.style.width = '0%';
        progressBarContainer.style.display = 'none';
        updateProgress({ text: 'Préparation de la transcription...' });
        importButton.disabled = true;
        modelSelect.disabled = true;
        window.pywebview.api.transcribe_file(filePath, selectedModel);
    } else {
        statusText.textContent = 'Aucun fichier sélectionné.';
        statusText.style.display = 'block';
    }
}

window.addEventListener('DOMContentLoaded', () => {
    // --- SÉLECTION DES ÉLÉMENTS ---
    const importButton = document.getElementById('import-button');
    const copyButton = document.getElementById('copy-button');
    const processButton = document.getElementById('process-button');
    const copyProcessedButton = document.getElementById('copy-processed-button');
    const modelSelect = document.getElementById('model-select');
    const textInput = document.getElementById('text-input');
    const navButtons = document.querySelectorAll('.nav-button');
    const sendToProcessingButton = document.getElementById('send-to-processing-button');
    const dropZone = document.getElementById('drop-zone');
    const ollamaProfileSelect = document.getElementById('ollama-profile-select');
    const exportTxtButton = document.getElementById('export-txt-button');
    const exportPdfButton = document.getElementById('export-pdf-button');
    const statusText = document.getElementById('status-text');
    const processingStatusText = document.getElementById('processing-status-text');
    const loaderContainer = document.querySelector('#transcription-view .loader-container');
    const processingLoaderContainer = document.querySelector('#processing-view .loader-container');
    const resultContainer = document.getElementById('result-container');
    const processingResultContainer = document.getElementById('processing-result-container');
    const transcriptionOutput = document.getElementById('transcription-output');
    const processingOutput = document.getElementById('processing-output');
    // SUPPRESSION des éléments de toggle de vue
    
    // --- NAVIGATION ---
    navButtons.forEach(button => {
        button.addEventListener('click', () => switchView(button.getAttribute('data-view')));
    });

    // --- VUE TRANSCRIPTION ---
    importButton.addEventListener('click', async () => {
        try {
            const filePath = await window.pywebview.api.open_file_dialog();
            startTranscription(filePath);
        } catch (error) {
            console.error('Erreur lors de la sélection du fichier :', error);
            statusText.textContent = `Erreur inattendue : ${error}`;
            loaderContainer.style.display = 'none';
            importButton.disabled = false;
            modelSelect.disabled = false;
        }
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
    
    const items = e.dataTransfer.items;
    if (items && items.length > 0) {
        for (let i = 0; i < items.length; i++) {
            if (items[i].kind === 'file') {
                const file = items[i].getAsFile();
                if (file) {
                    statusText.innerHTML = `<i class="fa-solid fa-info-circle"></i> Fichier détecté: ${file.name} - Préparation...`;
                    statusText.style.display = 'block';
                    
                    const reader = new FileReader();
                    reader.onload = async function(event) {
                        try {
                            const arrayBuffer = event.target.result;
                            const uint8Array = new Uint8Array(arrayBuffer);
                            
                            let base64 = '';
                            const chunkSize = 50000;
                            for (let i = 0; i < uint8Array.length; i += chunkSize) {
                                const chunk = uint8Array.subarray(i, i + chunkSize);
                                base64 += String.fromCharCode.apply(null, chunk);
                            }
                            base64 = btoa(base64);
                            
                            const tempPath = await window.pywebview.api.handle_dropped_file(base64, file.name);
                            if (tempPath) {
                                startTranscription(tempPath);
                            } else {
                                statusText.innerHTML = `<i class="fa-solid fa-times-circle" style="color: var(--error-color);"></i> Erreur lors du traitement du fichier`;
                            }
                        } catch (error) {
                            console.error('Erreur lors du traitement du fichier déposé:', error);
                            statusText.innerHTML = `<i class="fa-solid fa-times-circle" style="color: var(--error-color);"></i> Erreur: ${error.message}`;
                        }
                    };
                    reader.onerror = function() {
                        statusText.innerHTML = `<i class="fa-solid fa-times-circle" style="color: var(--error-color);"></i> Erreur de lecture du fichier`;
                    };
                    reader.readAsArrayBuffer(file);
                    break;
                }
            }
        }
    }
});

    sendToProcessingButton.addEventListener('click', () => {
        const transcriptText = transcriptionOutput.textContent;
        if (transcriptText) {
            textInput.value = transcriptText;
            switchView('processing-view');
        }
    });

    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(transcriptionOutput.textContent).then(() => {
            const originalText = copyButton.innerHTML;
            copyButton.innerHTML = `<i class="fa-solid fa-check"></i> Copié !`;
            setTimeout(() => { copyButton.innerHTML = originalText; }, 2000);
        });
    });

    // --- VUE TRAITEMENT ---
    processButton.addEventListener('click', async () => {
        try {
            const text = textInput.value.trim();
            const selectedProfile = ollamaProfileSelect.value;
            if (text) {
                processingStatusText.style.display = 'none';
                processingLoaderContainer.style.display = 'flex';
                processingResultContainer.style.display = 'none';
                updateProcessingStatus('Préparation du traitement...');
                processButton.disabled = true;
                window.pywebview.api.process_transcription(text, selectedProfile);
            } else {
                processingStatusText.textContent = 'Veuillez entrer un texte à traiter.';
            }
        } catch (error) {
            console.error('Erreur de traitement :', error);
            processingStatusText.textContent = `Erreur inattendue : ${error}`;
            processingLoaderContainer.style.display = 'none';
            processButton.disabled = false;
        }
    });

    // SUPPRESSION des listeners pour le toggle de vue

    copyProcessedButton.addEventListener('click', () => {
        navigator.clipboard.writeText(processingOutput.textContent).then(() => {
            const originalText = copyProcessedButton.innerHTML;
            copyProcessedButton.innerHTML = `<i class="fa-solid fa-check"></i> Copié !`;
            setTimeout(() => { copyProcessedButton.innerHTML = originalText; }, 2000);
        });
    });

    async function handleExport(fileType) {
        const content = processingOutput.textContent;
        if (!content) return;
        try {
            // On passe 'txt' pour un fichier .tex
            const result = await window.pywebview.api.save_file(content, fileType);
            if (result.status === 'error') {
                alert(`Erreur lors de la sauvegarde : ${result.message}`);
            }
        } catch (e) {
            alert(`Une erreur est survenue : ${e}`);
        }
    }

    exportTxtButton.addEventListener('click', () => handleExport('txt'));
    exportPdfButton.addEventListener('click', () => handleExport('pdf'));
});