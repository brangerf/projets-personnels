import json
import os
import time
import threading
import webview
import re
import traceback
import requests
from node_registry import NODE_REGISTRY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAESTRO_DIR = os.path.join(BASE_DIR, 'workflows', 'maestro_generated')

def load_system_prompt():
    """Charge le system prompt depuis un fichier externe avec documentation dynamique."""
    prompt_file = os.path.join(BASE_DIR, 'maestro_system_prompt.txt')
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            base_prompt = f.read().strip()
        
        dynamic_nodes_doc = NODE_REGISTRY.generate_maestro_documentation()
        
        if "**NŒUDS DISPONIBLES :**" in base_prompt:
            start_marker = "**NŒUDS DISPONIBLES :**"
            end_marker = "**EXEMPLE SIMPLE ET PARFAIT :**"
            
            start_index = base_prompt.find(start_marker)
            end_index = base_prompt.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                before_section = base_prompt[:start_index]
                after_section = base_prompt[end_index:]
                updated_prompt = before_section + dynamic_nodes_doc + "\n" + after_section
                return updated_prompt
        
        return base_prompt + "\n\n" + dynamic_nodes_doc
        
    except FileNotFoundError:
        base_fallback = "Tu es un générateur de workflow JSON au format LiteGraph.js.\nTa seule sortie doit être un objet JSON avec les clés `nodes` et `links`.\n\n"
        dynamic_nodes_doc = NODE_REGISTRY.generate_maestro_documentation()
        fallback_rules = "\n\nRÈGLES FINALES :\n- Ne fournis AUCUN texte explicatif, AUCUNE balise <think>.\n- Ta réponse doit commencer par { et se terminer par }.\n- Format des liens : [link_id, source_node_id, source_output_slot, target_node_id, target_input_slot, \"string\"]\n- Les slots de sortie/entrée commencent à 0\n- IMPORTANT : Utilise {{SELECTED_MODEL}} comme valeur pour la propriété \"model\" de tous les nœuds workflow/llm_model\n\nMaintenant, analyse la demande de l'utilisateur et génère le JSON."
        return base_fallback + dynamic_nodes_doc + fallback_rules

def validate_generated_workflow(workflow_data):
    """Valide le workflow généré contre le registre"""
    validation_result = NODE_REGISTRY.validate_workflow_structure(workflow_data)
    return validation_result

def enhance_workflow_with_registry_data(workflow_data):
    """Enrichit le workflow avec les données du registre (couleurs, titres, etc.)"""
    if not isinstance(workflow_data, dict) or 'nodes' not in workflow_data:
        return workflow_data
    
    for node in workflow_data['nodes']:
        node_type = node.get('type')
        if not node_type:
            continue
            
        node_def = NODE_REGISTRY.get_node_definition(node_type)
        if not node_def:
            continue
        
        if 'color' not in node or not node['color']:
            node['color'] = node_def.color
            
        if 'title' not in node or not node['title']:
            node['title'] = node_def.title
            
        if 'properties' not in node:
            node['properties'] = {}
            
        for prop_def in node_def.properties:
            if prop_def.name not in node['properties'] and prop_def.default is not None:
                node['properties'][prop_def.name] = prop_def.default

    return workflow_data

def auto_correct_and_ensure_links(workflow_data):
    """
    Analyse et corrige un workflow généré.
    1. Ajoute des nœuds de sortie pour les nœuds de traitement "orphelins".
    2. Reconstruit les références de liens dans les nœuds pour un affichage visuel correct.
    """
    if 'nodes' not in workflow_data or 'links' not in workflow_data:
        return workflow_data

    nodes_by_id = {str(node['id']): node for node in workflow_data['nodes']}
    links = workflow_data.get('links', [])
    
    processing_node_types = {'workflow/llm_model', 'workflow/iterative_llm'}
    output_node_type = 'workflow/text_output'
    
    used_output_slots = set()
    for link in links:
        source_node_id, source_slot_index = str(link[1]), link[2]
        used_output_slots.add(f"{source_node_id}_{source_slot_index}")

    dangling_nodes = []
    for node_id, node in nodes_by_id.items():
        if node.get('type') in processing_node_types and 'outputs' in node:
            for i, output_slot in enumerate(node['outputs']):
                if f"{node_id}_{i}" not in used_output_slots:
                    dangling_nodes.append({'node': node, 'slot_index': i})

    if dangling_nodes:
        print(f"AVERTISSEMENT MAESTRO: {len(dangling_nodes)} nœud(s) orphelin(s) détecté(s). Ajout automatique de nœuds de sortie.")
        last_node_id = workflow_data.get('last_node_id', len(nodes_by_id))
        last_link_id = workflow_data.get('last_link_id', len(links))

        for i, dangling in enumerate(dangling_nodes):
            source_node = dangling['node']
            source_slot_index = dangling['slot_index']
            
            last_node_id += 1
            last_link_id += 1
            
            new_output_node = {
                "id": last_node_id,
                "type": output_node_type,
                "pos": [source_node['pos'][0] + 300, source_node['pos'][1] + i * 100],
                "size": [180, 46],
                "flags": {}, "order": 100 + i, "mode": 0,
                "title": f"Sortie pour '{source_node.get('title', 'N/A')}'",
                "properties": {},
                "color": "#53a"
            }
            workflow_data['nodes'].append(new_output_node)
            
            new_link = [last_link_id, source_node['id'], source_slot_index, new_output_node['id'], 0, "string"]
            workflow_data['links'].append(new_link)

        workflow_data['last_node_id'] = last_node_id
        workflow_data['last_link_id'] = last_link_id

    for node in workflow_data['nodes']:
        if 'inputs' in node:
            for inp in node['inputs']:
                inp.pop('link', None)
        if 'outputs' in node:
            for outp in node['outputs']:
                outp['links'] = []

    for link in workflow_data['links']:
        link_id, source_id, source_slot, target_id, target_slot = link[0], str(link[1]), link[2], str(link[3]), link[4]
        
        if source_id in nodes_by_id:
            source_node = nodes_by_id[source_id]
            if 'outputs' in source_node and len(source_node['outputs']) > source_slot:
                if 'links' not in source_node['outputs'][source_slot] or source_node['outputs'][source_slot]['links'] is None:
                    source_node['outputs'][source_slot]['links'] = []
                source_node['outputs'][source_slot]['links'].append(link_id)

        if target_id in nodes_by_id:
            target_node = nodes_by_id[target_id]
            if 'inputs' in target_node and len(target_node['inputs']) > target_slot:
                target_node['inputs'][target_slot]['link'] = link_id
                
    return workflow_data


def escape_js_string(s):
    """Échappe une chaîne pour l'insérer dans du code JS."""
    return json.dumps(s)

def clean_json_string(json_str):
    """Nettoie une chaîne JSON en échappant les caractères problématiques."""
    def escape_newlines_in_strings(match):
        content = match.group(1)
        content = content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        content = content.replace('\b', '\\b').replace('\f', '\\f')
        return '"' + content + '"'
    
    cleaned = re.sub(r'"((?:[^"\\]|\\.)*)(?<!\\)"', escape_newlines_in_strings, json_str)
    return cleaned


def extract_json_from_response(text):
    """
    Extrait et nettoie une chaîne JSON d'une réponse texte potentiellement bruitée.
    Version améliorée pour gérer le JSON sans bloc de code.
    """
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return try_parse_json(match.group(1))
    
    match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return try_parse_json(match.group(1))

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and start < end:
        json_candidate = text[start:end+1]
        result = try_parse_json(json_candidate)
        if result:
            return result

    return None


def try_parse_json(json_str):
    """Essaie de parser du JSON en appliquant plusieurs stratégies de nettoyage."""
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            return json_str
    except json.JSONDecodeError:
        pass
    
    try:
        cleaned = clean_json_string(json_str)
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            return cleaned
    except json.JSONDecodeError:
        pass
    
    return None

def create_and_run_workflow(api_instance, user_prompt, global_model, complexity):
    """
    Fonction principale de Maestro : génère, sauvegarde et exécute un workflow.
    """
    window = webview.windows[0]
    try:
        window.evaluate_js("window.maestro_api.updateStatus('<i>Composition du workflow en cours...</i>')")
        system_prompt = load_system_prompt()
        
        complexity_instruction = ""
        if complexity == "simple":
            complexity_instruction = "Instruction de complexité : Le workflow doit être simple et contenir au maximum 3 nœuds de traitement (type llm_model ou iterative_llm).\n\n"
        elif complexity == "complexe":
            complexity_instruction = "Instruction de complexité : Le workflow doit être complexe, utiliser entre 5 et 15 nœuds au total, et explorer des solutions créatives enchaînant plusieurs étapes de traitement.\n\n"

        full_user_prompt = f"{complexity_instruction}Demande originale de l'utilisateur : {user_prompt}"
        final_user_prompt = full_user_prompt.replace("{{SELECTED_MODEL}}", global_model)
        
        history = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': final_user_prompt}
        ]
        
        raw_response = api_instance._ollama_worker_blocking(history, global_model)
        
        window.evaluate_js("window.maestro_api.updateStatus('<i>Validation et réparation du workflow...</i>')")
        json_string = extract_json_from_response(raw_response)
        
        if not json_string:
            error_msg = "Maestro n'a pas pu générer un JSON de workflow valide. Réponse reçue :\n\n" + raw_response
            window.evaluate_js(f"window.maestro_api.displayError({escape_js_string(error_msg)})")
            return

        workflow_data = json.loads(json_string)
        
        workflow_data = auto_correct_and_ensure_links(workflow_data)
        
        workflow_data = enhance_workflow_with_registry_data(workflow_data)
        validation_errors = validate_generated_workflow(workflow_data)
        if validation_errors:
            print(f"AVERTISSEMENT MAESTRO: Workflow généré avec des erreurs de validation: {validation_errors}")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        sanitized_prompt = re.sub(r'[\W_]+', '_', user_prompt[:30])
        filename = f"maestro_{timestamp}_{sanitized_prompt}.json"
        
        api_instance.save_workflow(filename, workflow_data)
        
        window.evaluate_js("window.maestro_api.updateStatus('<i>Exécution du workflow composé...</i>')")
        api_instance._run_workflow_stream_worker(filename, user_prompt, global_model)

    except Exception as e:
        error_message = f"Une erreur critique est survenue dans Maestro : {e}"
        print(traceback.format_exc())
        window.evaluate_js(f"window.maestro_api.displayError({escape_js_string(error_message)})")