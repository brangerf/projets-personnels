function initializeWorkflow() {
    workflowGraph = new LGraph();
    workflowCanvas = new LGraphCanvas("#workflow-canvas", workflowGraph);
    
    document.getElementById('add-node-selector').addEventListener('change', (e) => {
        if (e.target.value) {
            const node = LiteGraph.createNode(e.target.value);
            if (node) {
                workflowCanvas.graph.add(node);
            }
            e.target.value = "";
        }
    });
    
    document.getElementById('add-node-selector').addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const selectedValue = e.target.value;
        if (selectedValue && selectedValue !== "") {
            showNodeInfo(selectedValue);
        }
    });
    
    document.getElementById('workflow-save-button').addEventListener('click', saveWorkflow);
    document.getElementById('workflow-load-button').addEventListener('click', loadWorkflow);
}

function resizeWorkflowCanvas() {
    const canvas = document.getElementById('workflow-canvas');
    if (canvas.offsetWidth > 0 && canvas.offsetHeight > 0 && workflowCanvas) {
        workflowCanvas.resize(canvas.offsetWidth, canvas.offsetHeight);
        workflowGraph.setDirty(true, true);
    }
}

async function defineWorkflowNodes() {
    const nodeTypes = Object.keys(nodeRegistry);
    const registrationPromises = nodeTypes.map(async (nodeType) => {
        try {
            const nodeDef = await window.pywebview.api.get_node_definition(nodeType);
            if (!nodeDef) return;

            const NodeClass = function() {
                nodeDef.inputs.forEach(input => this.addInput(input.name, input.type));
                nodeDef.outputs.forEach(output => this.addOutput(output.name, output.type));
                this.properties = {};
                nodeDef.properties.forEach(prop => {
                    this.properties[prop.name] = prop.default !== null ? prop.default : "";
                });
                this.title = nodeDef.title;
                this.color = nodeDef.color;
            };
            
            if (nodeType === 'workflow/llm_model') {
                NodeClass.prototype.onDblClick = function() { openLlmNodeModal(this); };
            } else if (nodeType === 'workflow/text_input') {
                NodeClass.prototype.onDblClick = function() { 
                    const v = prompt("Valeur:", this.properties.value); 
                    if (v !== null) this.properties.value = v; 
                };
            } else if (nodeType === 'workflow/iterative_llm') {
                NodeClass.prototype.onDblClick = function() { 
                    const v = prompt("Itérations:", this.properties.iterations); 
                    if (v !== null) this.properties.iterations = parseInt(v) || 1; 
                };
            }
            
            LiteGraph.registerNodeType(nodeType, NodeClass);
        } catch (error) {
            console.error(`Erreur lors de la définition du nœud ${nodeType}:`, error);
        }
    });
    await Promise.all(registrationPromises);
}

async function saveWorkflow() {
    const validation = await validateCurrentWorkflow();
    if (!validation.valid) {
        const proceed = confirm(`Le workflow contient des erreurs de validation:\n\n${validation.errors.join('\n')}\n\nVoulez-vous sauvegarder quand même ?`);
        if (!proceed) return;
    }
    
    const filename = prompt("Nom du fichier (ex: mon_workflow.json) :");
    if (!filename) return;
    
    const data = workflowGraph.serialize();
    const result = await window.pywebview.api.save_workflow(filename, data);
    
    alert(validation.valid ? `${result} - Workflow validé avec succès.` : `${result} - ATTENTION: Sauvegardé avec des erreurs.`);
}

async function loadWorkflow() {
    const modal = document.getElementById('load-workflow-modal');
    const list = document.getElementById('modal-workflow-list');
    
    list.innerHTML = '<li>Chargement...</li>';
    modal.style.display = 'flex';

    const files = await window.pywebview.api.list_workflows();
    list.innerHTML = files.length > 0 ? '' : '<li>Aucun workflow trouvé.</li>';
    files.forEach(filename => {
        const li = document.createElement('li');
        li.textContent = filename;
        li.dataset.filename = filename;
        list.appendChild(li);
    });
}

async function validateCurrentWorkflow() {
    if (!workflowGraph) return { valid: true, errors: [] };
    const workflowData = workflowGraph.serialize();
    try {
        return await window.pywebview.api.validate_workflow(workflowData);
    } catch (error) {
        return { valid: false, errors: ['Erreur de validation côté serveur'] };
    }
}

async function showNodeInfo(nodeType) {
    try {
        const nodeDef = await window.pywebview.api.get_node_definition(nodeType);
        if (!nodeDef) return;
        let info = `=== ${nodeDef.title} ===\n\n${nodeDef.description}\n\n`;
        if (nodeDef.inputs.length > 0) {
            info += `ENTRÉES:\n`;
            nodeDef.inputs.forEach(i => { info += `• ${i.name} (${i.type}): ${i.description}\n`; });
            info += `\n`;
        }
        if (nodeDef.outputs.length > 0) {
            info += `SORTIES:\n`;
            nodeDef.outputs.forEach(o => { info += `• ${o.name} (${o.type}): ${o.description}\n`; });
            info += `\n`;
        }
        if (nodeDef.properties.length > 0) {
            info += `PROPRIÉTÉS:\n`;
            nodeDef.properties.forEach(p => { info += `• ${p.name}: ${p.description}\n${p.default ? `  Défaut: ${p.default}\n` : ''}`; });
            info += `\n`;
        }
        alert(info);
    } catch (error) {
        console.error('Erreur lors de la récupération des informations du nœud:', error);
    }
}

function updateNodeSelector() {
    const selector = document.getElementById('add-node-selector');
    if (!selector) return;
    
    selector.innerHTML = '<option value="">Ajouter un nœud...</option>';
    
    const categoryOrder = ['input', 'processing', 'utility', 'visualization', 'output'];
    const categoryLabels = {
        'input': 'ENTRÉES',
        'processing': 'TRAITEMENT',
        'utility': 'UTILITAIRES',
        'visualization': 'VISUALISATION',
        'output': 'SORTIES'
    };
    
    categoryOrder.forEach(categoryKey => {
        const categoryNodes = nodeCategories[categoryKey];
        if (!categoryNodes || categoryNodes.length === 0) return;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = categoryLabels[categoryKey] || categoryKey.toUpperCase();
        
        categoryNodes.forEach(node => {
            const option = document.createElement('option');
            option.value = node.value;
            option.textContent = node.label;
            optgroup.appendChild(option);
        });
        
        selector.appendChild(optgroup);
    });
}