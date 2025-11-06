import webview
import threading
import requests
import json
import os
import time
import maestro
import re
from collections import deque
from node_registry import NODE_REGISTRY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS_DIR = os.path.join(BASE_DIR, 'workflows')
SEQUENCES_DIR = os.path.join(BASE_DIR, 'sequences')
MAESTRO_DIR = os.path.join(WORKFLOWS_DIR, 'maestro_generated')

os.makedirs(WORKFLOWS_DIR, exist_ok=True)
os.makedirs(SEQUENCES_DIR, exist_ok=True)
os.makedirs(MAESTRO_DIR, exist_ok=True)

class Api:
    def __init__(self):
        self.node_registry = NODE_REGISTRY
    
    def get_node_options(self):
        return self.node_registry.generate_interface_options()
    
    def get_node_definition(self, node_type):
        node_def = self.node_registry.get_node_definition(node_type)
        if node_def:
            return {
                "node_type": node_def.node_type,
                "title": node_def.title,
                "description": node_def.description,
                "category": node_def.category.value,
                "color": node_def.color,
                "inputs": [
                    {
                        "name": slot.name,
                        "type": slot.type,
                        "description": slot.description,
                        "required": slot.required
                    } for slot in node_def.inputs
                ],
                "outputs": [
                    {
                        "name": slot.name,
                        "type": slot.type, 
                        "description": slot.description,
                        "required": slot.required
                    } for slot in node_def.outputs
                ],
                "properties": [
                    {
                        "name": prop.name,
                        "type": prop.type,
                        "description": prop.description,
                        "default": prop.default,
                        "options": prop.options,
                        "placeholder": prop.placeholder
                    } for prop in node_def.properties
                ],
                "examples": node_def.examples,
                "maestro_usage_hint": node_def.maestro_usage_hint
            }
        return None
    
    def validate_workflow(self, workflow_data):
        errors = self.node_registry.validate_workflow_structure(workflow_data)
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def get_maestro_node_documentation(self):
        return self.node_registry.generate_maestro_documentation()

    def _execute_node(self, node, inputs, global_model):
        node_type = node['type']
        props = node.get('properties', {})
        outputs = {}

        node_def = self.node_registry.get_node_definition(node_type)
        if not node_def:
            print(f"AVERTISSEMENT: Type de nœud non reconnu dans le registre: {node_type}")

        if node_type == 'workflow/text_input':
            outputs[0] = props.get('value', '')
        
        elif node_type == 'workflow/llm_model':
            custom_prompt_template = props.get('prompt', '{{in_1}}')
            final_prompt = custom_prompt_template

            for i in range(4):
                placeholder = f"{{{{in_{i+1}}}}}"
                input_text = str(inputs.get(i, ''))
                final_prompt = final_prompt.replace(placeholder, input_text)
            
            final_prompt = re.sub(r'\{\{in_\d\}\}', '', final_prompt)

            model_in_node = props.get('model')
            if model_in_node and model_in_node != "{{SELECTED_MODEL}}":
                model_to_use = model_in_node
            else:
                model_to_use = global_model

            history = [{'role': 'user', 'content': final_prompt}]
            outputs[0] = self._ollama_worker_blocking(history, model_to_use)

        elif node_type == 'workflow/iterative_llm':
            current_text = inputs.get(0, '')
            iterations = int(props.get('iterations', 1))
            for i in range(iterations):
                history = [{'role': 'user', 'content': current_text}]
                current_text = self._ollama_worker_blocking(history, global_model)
            outputs[0] = current_text

        return outputs

    def _execute_node_stream(self, node, inputs, global_model, window, is_maestro_run):
        node_type = node['type']
        props = node.get('properties', {})
        outputs = {}
        
        node_def = self.node_registry.get_node_definition(node_type)
        node_title = node.get('title', node_def.title if node_def else node_type)

        def escape_js(text):
            return json.dumps(str(text))

        if not is_maestro_run and node_type != 'workflow/text_output':
            window.evaluate_js(f"window.api.showWorkflowStepResult({escape_js(node_title)}, '')")

        if node_type == 'workflow/text_input':
            outputs[0] = props.get('value', '')
            if not is_maestro_run:
                window.evaluate_js(f"window.api.updateLastStepResult({escape_js(outputs[0])})")
        
        elif node_type == 'workflow/llm_model':
            custom_prompt_template = props.get('prompt', '{{in_1}}')
            final_prompt = custom_prompt_template

            for i in range(4):
                placeholder = f"{{{{in_{i+1}}}}}"
                input_text = str(inputs.get(i, ''))
                final_prompt = final_prompt.replace(placeholder, input_text)
            
            final_prompt = re.sub(r'\{\{in_\d\}\}', '', final_prompt)
            
            model_in_node = props.get('model')
            
            if model_in_node and model_in_node != "{{SELECTED_MODEL}}":
                model_to_use = model_in_node
            else:
                model_to_use = global_model

            full_response_text = ""
            url = "http://localhost:11434/api/chat"
            history = [{'role': 'user', 'content': final_prompt}]
            payload = {"model": model_to_use, "messages": history, "stream": True}

            with requests.post(url, json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        content_part = chunk['message']['content']
                        full_response_text += content_part
                        if not is_maestro_run:
                            window.evaluate_js(f"window.api.appendToWorkflowResponse({escape_js(content_part)})")
            
            outputs[0] = full_response_text

        elif node_type == 'workflow/iterative_llm':
            current_text = inputs.get(0, '')
            iterations = int(props.get('iterations', 1))
            for i in range(iterations):
                history = [{'role': 'user', 'content': current_text}]
                current_text = self._ollama_worker_blocking(history, global_model)
                if not is_maestro_run:
                    step_text = f"--- Itération {i+1}/{iterations} ---\n{current_text}"
                    window.evaluate_js(f"window.api.updateLastStepResult({escape_js(step_text)})")
                    time.sleep(0.5)
            outputs[0] = current_text

        if node_type == 'workflow/text_output' and not is_maestro_run:
             window.evaluate_js("window.api.hideLastStep()")

        return outputs

    def _run_workflow_stream_worker(self, filename, user_prompt, global_model):
        window = webview.windows[0]
        
        is_maestro_run = False
        try:
            is_maestro_run = window.evaluate_js("document.getElementById('maestro-view').classList.contains('active')")
        except Exception:
            pass

        api_target = 'maestro_api' if is_maestro_run else 'api'

        try:
            if not is_maestro_run:
                window.evaluate_js(f"window.{api_target}.startWorkflowMessage()")
            
            workflow_data = self.load_workflow(filename)
            
            nodes = {str(node['id']): node for node in workflow_data['nodes']}
            links = workflow_data.get('links', [])
            
            adj = {node_id: [] for node_id in nodes}
            in_degree = {node_id: 0 for node_id in nodes}
            
            for link in links:
                if len(link) >= 5:
                    source_id = str(link[1])
                    target_id = str(link[3])
                    if source_id in adj and target_id in in_degree:
                        adj[source_id].append(target_id)
                        in_degree[target_id] += 1

            queue = deque([node_id for node_id in nodes if in_degree[node_id] == 0])
            execution_order = []
            
            while queue:
                u = queue.popleft()
                execution_order.append(u)
                for v in adj.get(u, []):
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        queue.append(v)

            if len(execution_order) != len(nodes):
                raise Exception("Le workflow contient un cycle ou des nœuds déconnectés.")

            node_inputs_map = {node_id: {} for node_id in nodes}
            for link in links:
                if len(link) >= 5:
                    source_id, source_slot, target_id, target_slot = str(link[1]), link[2], str(link[3]), link[4]
                    if target_id in node_inputs_map:
                        node_inputs_map[target_id][target_slot] = (source_id, source_slot)

            if user_prompt is not None:
                for node_id, node in nodes.items():
                    if node['type'] == 'workflow/text_input':
                        node.setdefault('properties', {})['value'] = user_prompt

            node_outputs = {}
            for node_id in execution_order:
                node = nodes[node_id]
                input_values = {}
                for target_slot, (origin_id, origin_slot) in node_inputs_map.get(node_id, {}).items():
                    if origin_id in node_outputs and origin_slot in node_outputs[origin_id]:
                        input_values[target_slot] = node_outputs[origin_id][origin_slot]
                
                if is_maestro_run and node['type'] == 'workflow/text_output':
                    pass
                else:
                    outputs = self._execute_node_stream(node, input_values, global_model, window, is_maestro_run)
                    node_outputs[node_id] = outputs

            final_outputs = []
            final_outputs_with_titles = []
            for node_id, node in nodes.items():
                if node['type'] == 'workflow/text_output':
                    for target_slot, (origin_id, origin_slot) in node_inputs_map.get(node_id, {}).items():
                        if origin_id in node_outputs and origin_slot in node_outputs[origin_id]:
                            output_content = str(node_outputs[origin_id][origin_slot])
                            final_outputs.append(output_content)
                            
                            source_node = nodes.get(origin_id, {})
                            source_title = source_node.get('title', f'Agent ID {origin_id}')
                            final_outputs_with_titles.append({"title": source_title, "content": output_content})

            if not is_maestro_run:
                if final_outputs:
                    final_text = "\n\n---\n\n".join(final_outputs)
                else:
                    final_text = "Aucun résultat final produit par les nœuds de sortie."
                escaped_final_text = json.dumps(final_text)
                window.evaluate_js(f"window.api.finalizeWorkflowResponseWithData({escaped_final_text})")
            else:
                window.evaluate_js(f"window.{api_target}.showBeautifierLoading('Optimisation et présentation des résultats...')")
                
                raw_outputs_str = ""
                for i, item in enumerate(final_outputs_with_titles):
                    raw_outputs_str += f"--- DÉBUT BLOC DE SORTIE DE L'AGENT #{i+1} ---\n"
                    raw_outputs_str += f"Titre/Rôle de l'agent: {item['title']}\n"
                    raw_outputs_str += f"Contenu brut produit:\n{item['content']}\n"
                    raw_outputs_str += f"--- FIN BLOC DE SORTIE DE L'AGENT #{i+1} ---\n\n"

                beautifier_prompt = (
                    "Tu es un expert en présentation de rapports. Ta mission est de prendre une série de sorties brutes provenant de différents agents IA et de les formater en un seul document cohérent, clair et agréable à lire pour l'utilisateur final.\n\n"
                    f"La demande originale de l'utilisateur était : \"{user_prompt}\"\n\n"
                    "Voici les sorties brutes que tu dois synthétiser et embellir :\n\n"
                    f"{raw_outputs_str}"
                    "Instructions pour la mise en forme :\n"
                    "1.  Crée un titre principal pour le rapport global.\n"
                    "2.  Pour CHAQUE bloc de sortie d'agent, crée une section distincte.\n"
                    "3.  Chaque section doit avoir un titre clair et concis basé sur le rôle de l'agent (par exemple, 'Analyse Initiale', 'Rédaction du Poème', etc.).\n"
                    "4.  Présente le contenu de chaque section de manière propre en utilisant la syntaxe Markdown (listes à puces, gras, italique, etc.) pour améliorer la lisibilité.\n"
                    "5.  N'ajoute PAS de commentaires du type 'Voici le rapport' ou de dialogue. Produis uniquement le rapport formaté en Markdown.\n"
                    "6.  Assure-toi que la transition entre les sections est logique."
                )

                history = [{'role': 'user', 'content': beautifier_prompt}]
                beautified_result = self._ollama_worker_blocking(history, global_model)
                
                escaped_final_text = json.dumps(beautified_result)
                window.evaluate_js(f"window.{api_target}.displayFinalBeautifiedResult({escaped_final_text})")


        except Exception as e:
            import traceback
            error_message = f"Erreur lors de l'exécution du workflow '{filename}': {e}"
            print(f"DEBUG: {error_message}\n{traceback.format_exc()}")
            escaped_error = json.dumps(error_message)
            window.evaluate_js(f"window.{api_target}.displayError({escaped_error})")

    def run_workflow_from_chat(self, filename, user_prompt, global_model):
        try:
            workflow_data = self.load_workflow(filename)
            return self._run_workflow_logic(workflow_data, global_model, initial_input=user_prompt)
        except Exception as e:
            return f"Erreur lors de l'exécution du workflow '{filename}': {e}"

    def run_workflow_from_chat_stream(self, filename, user_prompt, global_model):
        thread = threading.Thread(target=self._run_workflow_stream_worker, args=(filename, user_prompt, global_model))
        thread.start()

    def run_sequence_from_chat(self, filename, user_prompt, global_model):
        try:
            sequence_files = self.load_sequence(filename)
            last_output = user_prompt
            for i, wf_filename in enumerate(sequence_files):
                workflow_data = self.load_workflow(wf_filename)
                last_output = self._run_workflow_logic(workflow_data, global_model, initial_input=last_output)
            return last_output
        except Exception as e:
            return f"Erreur lors de l'exécution de la séquence '{filename}': {e}"
    
    def invoke_maestro(self, user_prompt, global_model, complexity):
        thread = threading.Thread(target=maestro.create_and_run_workflow, args=(self, user_prompt, global_model, complexity))
        thread.start()

    def get_installed_models(self):
        try:
            response = requests.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            models_data = response.json()
            return [model['name'] for model in models_data.get('models', [])]
        except requests.exceptions.RequestException:
            return ["OLLAMA_OFFLINE"]

    def send_message_to_ollama(self, history, model):
        thread = threading.Thread(target=self._ollama_worker_stream, args=(history, model))
        thread.start()

    def _ollama_worker_stream(self, history, model):
        window = webview.windows[0]
        try:
            url = "http://localhost:11434/api/chat"
            payload = {"model": model, "messages": history, "stream": True}
            with requests.post(url, json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        content_part = chunk['message']['content']
                        escaped_chunk = json.dumps(content_part)
                        window.evaluate_js(f"window.api.appendToResponse({escaped_chunk})")
            window.evaluate_js("window.api.finalizeResponse()")
        except Exception as e:
            error_message = f"Erreur de communication avec Ollama: {e}"
            escaped_error = json.dumps(error_message)
            window.evaluate_js(f"window.api.showError({escaped_error})")
    
    def _ollama_worker_blocking(self, history, model):
        try:
            url = "http://localhost:11434/api/chat"
            payload = {"model": model, "messages": history, "stream": False}
            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            return response_data['message']['content']
        except Exception as e:
            return f"Erreur (bloquant): {e}"

    def save_workflow(self, filename, data):
        if not filename.endswith('.json'):
            filename += '.json'
        
        target_dir = MAESTRO_DIR if filename.startswith('maestro_') else WORKFLOWS_DIR
        
        filepath = os.path.join(target_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return f"Workflow '{filename}' sauvegardé."
        except Exception as e:
            return f"Erreur lors de la sauvegarde: {e}"

    def list_workflows(self):
        try:
            standard_files = [f for f in os.listdir(WORKFLOWS_DIR) if f.endswith('.json')]
            maestro_files = [f for f in os.listdir(MAESTRO_DIR) if f.endswith('.json')]
            return sorted(standard_files + maestro_files)
        except Exception as e:
            print(f"Erreur list_workflows: {e}")
            return []

    def load_workflow(self, filename):
        standard_path = os.path.join(WORKFLOWS_DIR, filename)
        maestro_path = os.path.join(MAESTRO_DIR, filename)
        
        filepath = standard_path if os.path.exists(standard_path) else maestro_path
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_sequence(self, filename, data):
        if not filename.endswith('.json'):
            filename += '.json'
        filepath = os.path.join(SEQUENCES_DIR, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return f"Séquence '{filename}' sauvegardée."
        except Exception as e:
            return f"Erreur: {e}"

    def list_sequences(self):
        try:
            return sorted([f for f in os.listdir(SEQUENCES_DIR) if f.endswith('.json')])
        except Exception:
            return []

    def load_sequence(self, filename):
        filepath = os.path.join(SEQUENCES_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

if __name__ == '__main__':
    api = Api()
    html_file = os.path.join(BASE_DIR, 'interface.html')
    window = webview.create_window(
        'Maestro',
        url=html_file,
        js_api=api,
        width=1500,
        height=900,
        min_size=(1000, 700)
    )
    webview.start(debug=False)