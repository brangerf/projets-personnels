function initializeNavigation() {
    const navButtons = document.querySelectorAll('.nav-button');
    const views = document.querySelectorAll('.view-container');
    const chatControls = document.getElementById('chat-controls');

    navButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetViewId = button.dataset.view;
            navButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            views.forEach(view => view.classList.toggle('active', view.id === targetViewId));
            chatControls.style.display = (targetViewId === 'chat-view' || targetViewId === 'maestro-view') ? 'block' : 'none';
            if (targetViewId === 'workflow-view') {
                resizeWorkflowCanvas();
            } else if (targetViewId === 'sequences-view') {
                loadAvailableWorkflows();
            } else if (targetViewId === 'chat-view') {
                populateExecutionSelectors();
            }
        });
    });
}

function initializeModal() {
    const llmModal = document.getElementById('llm-node-modal');
    document.getElementById('modal-save-button').addEventListener('click', () => {
        if (currentNodeBeingConfigured) {
            const model = document.getElementById('modal-model-select').value;
            const promptText = document.getElementById('modal-prompt-textarea').value;
            currentNodeBeingConfigured.properties.model = model;
            currentNodeBeingConfigured.properties.prompt = promptText;
        }
        closeLlmNodeModal();
    });
    document.getElementById('modal-cancel-button').addEventListener('click', closeLlmNodeModal);
    llmModal.addEventListener('click', (e) => {
        if (e.target === llmModal) closeLlmNodeModal();
    });
}

function initializeLoadWorkflowModal() {
    const modal = document.getElementById('load-workflow-modal');
    const list = document.getElementById('modal-workflow-list');
    const closeModal = () => modal.style.display = 'none';
    modal.querySelector('.modal-close-button').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    list.addEventListener('click', async (e) => {
        const targetLi = e.target.closest('li');
        if (targetLi && targetLi.dataset.filename) {
            const filename = targetLi.dataset.filename;
            try {
                const data = await window.pywebview.api.load_workflow(filename);
                workflowGraph.configure(data);
                document.getElementById('workflow-status').textContent = `Workflow '${filename}' chargé.`;
            } catch (error) {
                alert(`Erreur lors du chargement du workflow : ${error}`);
            } finally {
                closeModal();
            }
        }
    });
}

function initializeArtifactViewer() {
    document.getElementById('artifact-close-button').addEventListener('click', () => {
        document.getElementById('artifact-viewer').classList.remove('visible');
        document.getElementById('artifact-iframe').srcdoc = '';
    });

    const artifactViewer = document.getElementById('artifact-viewer');
    const resizer = document.getElementById('artifact-resizer');
    const iframe = document.getElementById('artifact-iframe');
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isResizing = true;
        iframe.style.pointerEvents = 'none';
        document.body.classList.add('resizing');
        artifactViewer.classList.add('resizing');
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', stopResizing);
    });

    let latestWidth;
    let animationFrameRequested = false;

    function updateWidth() {
        artifactViewer.style.width = latestWidth + 'px';
        animationFrameRequested = false;
    }

    function handleMouseMove(e) {
        if (!isResizing) return;
        const newWidth = window.innerWidth - e.clientX;
        if (newWidth > 300 && newWidth < (window.innerWidth - 100)) {
            latestWidth = newWidth;
            if (!animationFrameRequested) {
                animationFrameRequested = true;
                window.requestAnimationFrame(updateWidth);
            }
        }
    }

    function stopResizing() {
        isResizing = false;
        iframe.style.pointerEvents = 'auto';
        document.body.classList.remove('resizing');
        artifactViewer.classList.remove('resizing');
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', stopResizing);
    }
}


function openLlmNodeModal(node) {
    currentNodeBeingConfigured = node;
    document.getElementById('modal-model-select').value = node.properties.model || modelSelector.value;
    document.getElementById('modal-prompt-textarea').value = node.properties.prompt || '{{input}}';
    document.getElementById('llm-node-modal').style.display = 'flex';
}

function closeLlmNodeModal() {
    document.getElementById('llm-node-modal').style.display = 'none';
    currentNodeBeingConfigured = null;
}

function parseThinkingContent(text) {
    const result = { thinkingSections: [], mainContent: text };
    const patterns = [
        { start: '<thinking>', end: '</thinking>', startLen: 10, endLen: 11 },
        { start: '<think>', end: '</think>', startLen: 7, endLen: 8 }
    ];
    for (const pattern of patterns) {
        let workingText = result.mainContent;
        let startIndex = 0;
        while (true) {
            const thinkingStart = workingText.indexOf(pattern.start, startIndex);
            if (thinkingStart === -1) break;
            const thinkingEnd = workingText.indexOf(pattern.end, thinkingStart);
            if (thinkingEnd === -1) break;
            const fullMatch = workingText.substring(thinkingStart, thinkingEnd + pattern.endLen);
            const content = workingText.substring(thinkingStart + pattern.startLen, thinkingEnd);
            result.thinkingSections.push({ fullMatch: fullMatch, content: content.trim() });
            startIndex = thinkingEnd + pattern.endLen;
        }
        result.thinkingSections.forEach(section => {
            result.mainContent = result.mainContent.replace(section.fullMatch, '');
        });
    }
    result.mainContent = result.mainContent.trim();
    return result;
}

function createThinkingSection(content, index) {
    const section = document.createElement('div');
    section.className = 'thinking-section collapsed';
    section.innerHTML = `
        <div class="thinking-header" onclick="toggleThinking(this)">
            <i class="fa-solid fa-chevron-down thinking-icon"></i>
            <i class="fa-solid fa-brain"></i>
            <span>Raisonnement du modèle ${index > 0 ? `(${index + 1})` : ''}</span>
        </div>
        <div class="thinking-content"></div>
    `;
    section.querySelector('.thinking-content').textContent = content;
    return section;
}

window.toggleThinking = function(header) {
    const section = header.parentElement;
    section.classList.toggle('collapsed');
}

function processFinalContent(element, content) {
    try {
        let processedContent = content;
        if (typeof katex !== 'undefined') {
            processedContent = processedContent.replace(/\$\$([\s\S]*?)\$\$/g, (match, latex) => {
                try { return katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false }); }
                catch (e) { return match; }
            });
            processedContent = processedContent.replace(/(^|[^\\])\$([^$]+)\$/g, (match, preceding, latex) => {
                try { return preceding + katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false }); }
                catch (e) { return match; }
            });
        }
        element.innerHTML = marked.parse(processedContent, { gfm: true, breaks: true });

        element.querySelectorAll('pre').forEach(pre => {
            const code = pre.querySelector('code');
            if (!code) return;

            const buttonContainer = document.createElement('div');
            buttonContainer.style.position = 'absolute';
            buttonContainer.style.top = '8px';
            buttonContainer.style.right = '8px';
            buttonContainer.style.display = 'flex';
            buttonContainer.style.gap = '8px';
            pre.style.position = 'relative';
            pre.appendChild(buttonContainer);

            const copyButton = document.createElement('button');
            copyButton.className = 'copy-code-button';
            copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copier';
            copyButton.style.position = 'static';
            buttonContainer.appendChild(copyButton);

            copyButton.addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(code.textContent).then(() => {
                    copyButton.innerHTML = '<i class="fa-solid fa-check"></i> Copié !';
                    setTimeout(() => { copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copier'; }, 2000);
                });
            });

            if (code.classList.contains('language-html')) {
                const renderButton = document.createElement('button');
                renderButton.className = 'copy-code-button';
                renderButton.innerHTML = '<i class="fa-solid fa-play"></i> Visualiser';
                renderButton.style.position = 'static';
                buttonContainer.insertBefore(renderButton, copyButton);

                renderButton.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const artifactViewer = document.getElementById('artifact-viewer');
                    const iframe = document.getElementById('artifact-iframe');
                    iframe.srcdoc = code.textContent;
                    artifactViewer.classList.add('visible');
                });
            }
        });
        
        element.querySelectorAll('pre code').forEach(block => {
            if (typeof hljs !== 'undefined') hljs.highlightElement(block);
        });
    } catch (e) {
        console.error('Erreur lors du traitement du contenu final:', e);
        element.textContent = content;
    }
}

function displayRichContent(targetElement, rawContent) {
    const chatContainer = document.getElementById('chat-container');
    if (!targetElement) return;

    if (typeof rawContent === 'string' && rawContent.trim().startsWith('data:image/png;base64,')) {
        targetElement.innerHTML = '';
        const img = document.createElement('img');
        img.src = rawContent.trim();
        img.style.maxWidth = '100%';
        img.style.height = 'auto';
        img.style.backgroundColor = 'white';
        img.style.borderRadius = '8px';
        targetElement.appendChild(img);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return;
    }
    
    const parsed = parseThinkingContent(rawContent);
    
    targetElement.innerHTML = '';
    
    if (parsed.thinkingSections.length > 0) {
        parsed.thinkingSections.forEach((section, index) => {
            targetElement.appendChild(createThinkingSection(section.content, index));
        });
    }
    
    if (parsed.mainContent) {
        const contentDiv = document.createElement('div');
        targetElement.appendChild(contentDiv);
        setTimeout(() => {
            processFinalContent(contentDiv, parsed.mainContent);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }, 0);
    } else if (parsed.thinkingSections.length === 0) {
        targetElement.textContent = "(Aucune sortie de texte)";
    }
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}