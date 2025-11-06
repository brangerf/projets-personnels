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
import logging 
import sys 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    stream=sys.stdout,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS_DIR = os.path.join(BASE_DIR, 'workflows')
MAESTRO_DIR = os.path.join(WORKFLOWS_DIR, 'maestro_generated')

os.makedirs(WORKFLOWS_DIR, exist_ok=True)
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
            logging.warning(f"Type de nœud non reconnu dans le registre: {node_type}")

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

        if node_type == 'workflow/text_input':
            outputs[0] = props.get('value', '')
        
        elif node_type == 'workflow/llm_model':
            window.evaluate_js(f"window.maestro_api.showWorkflowStepResult({escape_js(node_title)}, '')")
            
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
            
            logging.info(f"Appel LLM pour le nœud '{node_title}' avec le modèle '{model_to_use}'.")
            logging.debug(f"--- PROMPT COMPLET ---\n{final_prompt}\n--------------------")

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
                        window.evaluate_js(f"window.maestro_api.appendToWorkflowResponse({escape_js(content_part)})")
            
            window.evaluate_js(f"window.maestro_api.finalizeAgentStep({escape_js(node_title)}, {escape_js(full_response_text)})")
            outputs[0] = full_response_text

        elif node_type == 'workflow/iterative_llm':
            window.evaluate_js(f"window.maestro_api.showWorkflowStepResult({escape_js(node_title)}, '')")
            
            current_text = inputs.get(0, '')
            iterations = int(props.get('iterations', 1))
            for i in range(iterations):
                logging.info(f"Nœud '{node_title}', itération {i+1}/{iterations}")
                history = [{'role': 'user', 'content': current_text}]
                current_text = self._ollama_worker_blocking(history, global_model)
                step_text = f"--- Itération {i+1}/{iterations} ---\n{current_text}"
                window.evaluate_js(f"window.maestro_api.appendToWorkflowResponse({escape_js(step_text)})")
                time.sleep(0.5)
            
            window.evaluate_js(f"window.maestro_api.finalizeAgentStep({escape_js(node_title)}, {escape_js(current_text)})")
            outputs[0] = current_text

        return outputs

    def _run_workflow_stream_worker(self, filename, user_prompt, global_model):
        window = webview.windows[0]
        
        is_maestro_run = True
        api_target = 'maestro_api'

        try:
            logging.info(f"Début de l'exécution du workflow '{filename}' pour le prompt : '{user_prompt[:50]}...'")
            window.evaluate_js(f"window.{api_target}.startWorkflowMessage()")
            
            workflow_data = self.load_workflow(filename)
            
            nodes = {str(node['id']): node for node in workflow_data['nodes']}
            links = workflow_data.get('links', [])
            
            valid_node_ids = set(nodes.keys())
            sanitized_links = []
            for link in links:
                if len(link) < 5:
                    logging.warning(f"Suppression du lien malformé : {link}")
                    continue

                source_id = str(link[1])
                target_id = str(link[3])

                if source_id in valid_node_ids and target_id in valid_node_ids and source_id != target_id:
                    sanitized_links.append(link)
                else:
                    logging.warning(f"Suppression du lien invalide (nœud inexistant ou auto-référencé) : {link}")
            
            if len(sanitized_links) < len(links):
                logging.info(f"{len(links) - len(sanitized_links)} lien(s) invalide(s) ont été supprimés.")
                links = sanitized_links

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
                remaining_nodes = set(nodes.keys()) - set(execution_order)
                logging.warning(f"Échec du tri topologique. {len(remaining_nodes)} nœud(s) non traité(s): {remaining_nodes}")
                
                cycles_detected = any(in_degree[node_id] > 0 for node_id in remaining_nodes)
                
                if cycles_detected:
                    logging.error("Cycles détectés dans le workflow. Tentative de réparation automatique...")
                    for node_id in remaining_nodes:
                        if in_degree[node_id] > 0:
                            links = [link for link in links if str(link[3]) != node_id]
                            in_degree[node_id] = 0
                            queue.append(node_id)
                    
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
                    isolated_nodes = set(nodes.keys()) - set(execution_order)
                    logging.warning(f"Ajout des nœuds isolés à la fin de l'ordre d'exécution: {isolated_nodes}")
                    execution_order.extend(isolated_nodes)
            
            logging.info(f"Ordre d'exécution des nœuds déterminé : {execution_order}")

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
                node_title = node.get('title', node.get('type'))
                logging.info(f"--- Exécution du nœud ID:{node_id} ('{node_title}') ---")
                
                input_values = {}
                for target_slot, (origin_id, origin_slot) in node_inputs_map.get(node_id, {}).items():
                    if origin_id in node_outputs and origin_slot in node_outputs[origin_id]:
                        input_values[target_slot] = node_outputs[origin_id][origin_slot]
                    else:
                        logging.warning(f"Entrée manquante pour le nœud {node_id}, slot {target_slot}: origine {origin_id}[{origin_slot}] non disponible")
                
                logging.info(f"Entrées pour le nœud {node_id}: { {k: str(v)[:100] + '...' if len(str(v)) > 100 else v for k, v in input_values.items()} }")

                if node['type'] != 'workflow/text_output':
                    outputs = self._execute_node_stream(node, input_values, global_model, window, is_maestro_run)
                    node_outputs[node_id] = outputs
                    logging.info(f"Sorties du nœud {node_id}: { {k: str(v)[:100] + '...' if len(str(v)) > 100 else v for k, v in outputs.items()} }")

            logging.info("Exécution du workflow terminée.")
            window.evaluate_js(f"window.{api_target}.updateStatus('Composition terminée.')")
            window.evaluate_js(f"window.{api_target}.enableControls()")

        except Exception as e:
            import traceback
            error_message = f"Erreur lors de l'exécution du workflow '{filename}': {e}"
            logging.error(f"{error_message}\n{traceback.format_exc()}")
            escaped_error = json.dumps(error_message)
            window.evaluate_js(f"window.{api_target}.displayError({escaped_error})")

    def invoke_maestro(self, user_prompt, global_model, complexity):
        logging.info(f"Invocation de Maestro avec le modèle '{global_model}' et la complexité '{complexity}'.")
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

    def _ollama_worker_blocking(self, history, model):
        try:
            url = "http://localhost:11434/api/chat"
            payload = {"model": model, "messages": history, "stream": False}
            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            return response_data['message']['content']
        except Exception as e:
            logging.error(f"Erreur lors de l'appel bloquant à Ollama : {e}")
            return f"Erreur (bloquant): {e}"

    def save_workflow(self, filename, data):
        if not filename.endswith('.json'):
            filename += '.json'
        
        target_dir = MAESTRO_DIR if filename.startswith('maestro_') else WORKFLOWS_DIR
        
        filepath = os.path.join(target_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Workflow sauvegardé avec succès dans '{filepath}'")
            return f"Workflow '{filename}' sauvegardé."
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde du workflow '{filename}': {e}")
            return f"Erreur lors de la sauvegarde: {e}"

    def list_workflows(self):
        try:
            standard_files = [f for f in os.listdir(WORKFLOWS_DIR) if f.endswith('.json')]
            maestro_files = [f for f in os.listdir(MAESTRO_DIR) if f.endswith('.json')]
            return sorted(standard_files + maestro_files)
        except Exception as e:
            logging.error(f"Erreur lors du listage des workflows: {e}")
            return []

    def load_workflow(self, filename):
        standard_path = os.path.join(WORKFLOWS_DIR, filename)
        maestro_path = os.path.join(MAESTRO_DIR, filename)
        
        filepath = standard_path if os.path.exists(standard_path) else maestro_path
        
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