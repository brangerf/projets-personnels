window.addEventListener('pywebviewready', async () => {
    const models = await window.pywebview.api.get_installed_models();
    updateModelSelector(models);
});

document.addEventListener('DOMContentLoaded', () => {
    initializeMaestro();
});

function updateModelSelector(models) {
    const maestroSelect = document.getElementById('maestro-model-selector');
    if (!maestroSelect) return;

    if (!models || models.length === 0) {
        maestroSelect.innerHTML = '<option>Aucun modèle trouvé</option>';
        return;
    }
    if (models[0] === 'OLLAMA_OFFLINE') {
        maestroSelect.innerHTML = '<option>Ollama non démarré</option>';
        window.maestro_api.displayError('Erreur: Ollama ne semble pas être en cours d\'exécution. Veuillez démarrer Ollama et rafraîchir l\'application.');
        return;
    }
    maestroSelect.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
}