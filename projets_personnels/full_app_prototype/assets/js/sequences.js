function initializeSequences() {
    document.getElementById('sequence-save-button').addEventListener('click', saveSequence);
    document.getElementById('sequence-load-button').addEventListener('click', loadSequence);
    document.getElementById('sequence-available-list').addEventListener('click', (e) => {
        if (e.target.tagName === 'LI') addWorkflowToSequence(e.target.dataset.filename);
    });
}

async function loadAvailableWorkflows() {
    const listEl = document.getElementById('sequence-available-list');
    listEl.innerHTML = 'Chargement...';
    const files = await window.pywebview.api.list_workflows();
    listEl.innerHTML = files.length > 0 ? '' : '<li>Aucun workflow trouvé.</li>';
    files.forEach(file => { const li = document.createElement('li'); li.textContent = file; li.dataset.filename = file; listEl.appendChild(li); });
}

function addWorkflowToSequence(filename) {
    const listEl = document.getElementById('sequence-active-list');
    const li = document.createElement('li');
    li.dataset.filename = filename;
    li.innerHTML = `<span>${filename}</span><span class="sequence-item-controls"><button onclick="moveSequenceItem(this, -1)"><i class="fa-solid fa-arrow-up"></i></button><button onclick="moveSequenceItem(this, 1)"><i class="fa-solid fa-arrow-down"></i></button><button onclick="this.parentElement.parentElement.remove()"><i class="fa-solid fa-trash"></i></button></span>`;
    listEl.appendChild(li);
}

window.moveSequenceItem = function(button, direction) {
    const item = button.closest('li');
    if (direction === -1 && item.previousElementSibling) { item.parentNode.insertBefore(item, item.previousElementSibling); }
    else if (direction === 1 && item.nextElementSibling) { item.parentNode.insertBefore(item.nextElementSibling, item); }
}

async function saveSequence() {
    const filename = prompt("Nom du fichier (ex: ma_sequence.json) :");
    if (!filename) return;
    const sequence = Array.from(document.querySelectorAll('#sequence-active-list li')).map(li => li.dataset.filename);
    const result = await window.pywebview.api.save_sequence(filename, sequence);
    alert(result);
}

async function loadSequence() {
    const files = await window.pywebview.api.list_sequences();
    if (files.length === 0) { alert("Aucune séquence trouvée."); return; }
    const filename = prompt("Charger quelle séquence ?\n\n" + files.join("\n"));
    if (!filename || !files.includes(filename)) { if(filename) alert("Fichier non trouvé."); return; }
    const sequence = await window.pywebview.api.load_sequence(filename);
    const listEl = document.getElementById('sequence-active-list');
    listEl.innerHTML = '';
    sequence.forEach(wf => addWorkflowToSequence(wf));
}