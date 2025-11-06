import json
import os
import time
import threading
import webview
import re
import traceback
import requests
from node_registry import NODE_REGISTRY
import logging

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
            end_marker = "**EXEMPLES DE PLANS :**"
            
            start_index = base_prompt.find(start_marker)
            end_index = base_prompt.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                before_section = base_prompt[:start_index]
                after_section = base_prompt[end_index:]
                updated_prompt = before_section + dynamic_nodes_doc + "\n" + after_section
                return updated_prompt
        
        return base_prompt + "\n\n" + dynamic_nodes_doc
        
    except FileNotFoundError:
        base_fallback = "Tu es un générateur de plans de réponse structurés.\n"
        dynamic_nodes_doc = NODE_REGISTRY.generate_maestro_documentation()
        return base_fallback + dynamic_nodes_doc

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
        logging.warning(f"Maestro a détecté {len(dangling_nodes)} nœud(s) orphelin(s). Ajout automatique de nœuds de sortie.")
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


def clean_latex_in_text(text):
    """
    Nettoie le texte pour assurer un rendu LaTeX correct.
    Remplace les séquences problématiques qui peuvent casser le rendu.
    """
    return text


def extract_json_from_response(text):
    """
    Extrait et nettoie une chaîne JSON d'une réponse texte potentiellement bruitée.
    Stratégies multiples avec nettoyage progressif.
    """
    logging.debug(f"Tentative d'extraction JSON depuis une réponse de {len(text)} caractères")
    
    match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
    if match:
        logging.debug("Stratégie 1: Bloc ```json trouvé")
        result = try_parse_json(match.group(1))
        if result:
            return result
    
    match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', text, re.DOTALL)
    if match:
        logging.debug("Stratégie 2: Bloc ``` générique trouvé")
        result = try_parse_json(match.group(1))
        if result:
            return result

    start = text.find('{')
    if start != -1:
        brace_count = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i
                    break
        
        if end != -1:
            json_candidate = text[start:end+1]
            logging.debug(f"Stratégie 3: JSON candidat trouvé de {start} à {end}")
            result = try_parse_json(json_candidate)
            if result:
                return result
    
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and start < end:
        json_candidate = text[start:end+1]
        logging.debug("Stratégie 4: Extraction entre premier { et dernier }")
        result = try_parse_json(json_candidate)
        if result:
            return result
    
    logging.error("Toutes les stratégies d'extraction JSON ont échoué")
    return None


def try_parse_json(json_str):
    """
    Essaie de parser du JSON en appliquant plusieurs stratégies de nettoyage.
    Retourne la chaîne JSON valide ou None.
    """
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            logging.debug("Parse JSON direct réussi")
            return json_str
    except json.JSONDecodeError as e:
        logging.debug(f"Parse direct échoué: {e}")
    
    try:
        cleaned = json_str
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            logging.debug("Parse avec nettoyage caractères de contrôle réussi")
            return cleaned
    except json.JSONDecodeError as e:
        logging.debug(f"Parse avec nettoyage caractères échoué: {e}")
    
    try:
        def escape_newlines_in_strings(match):
            content = match.group(1)
            content = content.replace('\\', '\\\\')
            content = content.replace('\n', '\\n')
            content = content.replace('\r', '\\r')
            content = content.replace('\t', '\\t')
            content = content.replace('\b', '\\b')
            content = content.replace('\f', '\\f')
            content = content.replace('"', '\\"')
            return '"' + content + '"'
        
        cleaned = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', escape_newlines_in_strings, json_str)
        
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            logging.debug("Parse avec échappement newlines réussi")
            return cleaned
    except (json.JSONDecodeError, re.error) as e:
        logging.debug(f"Parse avec échappement newlines échoué: {e}")
    
    try:
        parsed = json.loads(json_str, strict=False)
        if isinstance(parsed, dict) and 'nodes' in parsed and 'links' in parsed:
            logging.debug("Parse non-strict réussi")
            return json_str
    except json.JSONDecodeError as e:
        logging.debug(f"Parse non-strict échoué: {e}")
    
    logging.debug("Tous les tests de parsing JSON ont échoué")
    return None


def create_and_run_workflow(api_instance, user_prompt, global_model, complexity):
    """
    Fonction principale de Maestro : génère, sauvegarde et exécute un workflow.
    Avec gestion améliorée des erreurs et tentatives multiples.
    """
    window = webview.windows[0]
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Phase 1: Génération du plan de réponse par Maestro (tentative {attempt + 1}/{MAX_RETRIES}).")
            window.evaluate_js("window.maestro_api.updateStatus('<i>Analyse de votre demande et création du plan de réponse...</i>')")
            
            system_prompt = load_system_prompt()
            
            complexity_instruction = ""
            if complexity == "simple":
                complexity_instruction = (
                    "**CONTRAINTE DE COMPLEXITÉ : MODE SIMPLE**\n"
                    "Tu dois créer un plan de réponse contenant entre 3 et 6 parties principales.\n"
                    "Chaque partie sera traitée par un agent LLM dédié.\n"
                    "Structure recommandée : 3 grandes parties avec éventuellement 1-2 sous-parties chacune,\n"
                    "OU un plan linéaire avec 4-6 sections distinctes.\n"
                    "TOTAL D'AGENTS À CRÉER : entre 3 et 6\n\n"
                )
            elif complexity == "complexe":
                complexity_instruction = (
                    "**CONTRAINTE DE COMPLEXITÉ : MODE COMPLEXE**\n"
                    "Tu dois créer un plan de réponse détaillé contenant entre 6 et 12 parties.\n"
                    "Chaque partie sera traitée par un agent LLM dédié.\n"
                    "Structure recommandée : 3-4 grandes parties avec plusieurs sous-parties détaillées,\n"
                    "OU un plan linéaire avec 8-12 sections distinctes.\n"
                    "TOTAL D'AGENTS À CRÉER : entre 6 et 12\n\n"
                )

            json_format_instruction = (
                "\n\n**INSTRUCTION CRITIQUE DE FORMAT :**\n"
                "Tu dois répondre UNIQUEMENT avec l'objet JSON, sans AUCUN texte avant ou après.\n"
                "Ne commence PAS par des explications, des réflexions ou du texte.\n"
                "Ne termine PAS par des commentaires ou des notes.\n"
                "Ta réponse doit commencer par '{' et se terminer par '}'.\n"
                "Si tu dois réfléchir ou planifier, fais-le mentalement mais ne l'écris PAS dans ta réponse.\n"
            )

            full_user_prompt = f"{complexity_instruction}**DEMANDE DE L'UTILISATEUR :**\n{user_prompt}{json_format_instruction}"
            final_user_prompt = full_user_prompt.replace("{{SELECTED_MODEL}}", global_model)
            
            history = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': final_user_prompt}
            ]
            
            logging.info(f"Appel LLM pour générer le workflow avec le modèle '{global_model}'.")
            
            raw_response = api_instance._ollama_worker_blocking(history, global_model)
            
            logging.info(f"Réponse brute reçue ({len(raw_response)} caractères)")
            logging.debug(f"--- RÉPONSE BRUTE (début) ---\n{raw_response[:500]}\n--------------------")
            
            window.evaluate_js("window.maestro_api.updateStatus('<i>Validation et optimisation du plan...</i>')")
            json_string = extract_json_from_response(raw_response)
            
            if not json_string:
                if attempt < MAX_RETRIES - 1:
                    logging.warning(f"Échec de l'extraction JSON (tentative {attempt + 1}). Nouvelle tentative...")
                    window.evaluate_js(f"window.maestro_api.updateStatus('<i>Nouvelle tentative de génération (essai {attempt + 2}/{MAX_RETRIES})...</i>')")
                    time.sleep(1)
                    continue
                else:
                    error_msg = (
                        "Maestro n'a pas réussi à générer un plan de réponse valide après plusieurs tentatives.\n\n"
                        "Suggestions :\n"
                        "- Simplifiez votre demande\n"
                        "- Essayez un autre modèle\n"
                        "- Réessayez avec une formulation différente\n\n"
                        f"Dernière réponse reçue (extrait) :\n{raw_response[:500]}..."
                    )
                    logging.error("Échec de l'extraction du JSON après toutes les tentatives.")
                    window.evaluate_js(f"window.maestro_api.displayError({escape_js_string(error_msg)})")
                    return

            workflow_data = json.loads(json_string)
            
            logging.info("JSON extrait et parsé avec succès. Application des corrections et améliorations.")
            workflow_data = auto_correct_and_ensure_links(workflow_data)
            workflow_data = enhance_workflow_with_registry_data(workflow_data)
            
            validation_errors = validate_generated_workflow(workflow_data)
            if validation_errors:
                logging.warning(f"Workflow généré avec des avertissements de validation: {validation_errors}")

            timestamp = time.strftime("%Y%m%d-%H%M%S")
            sanitized_prompt = re.sub(r'[\W_]+', '_', user_prompt[:30])
            filename = f"maestro_{timestamp}_{sanitized_prompt}.json"
            
            api_instance.save_workflow(filename, workflow_data)
            
            agent_count = sum(1 for node in workflow_data['nodes'] if node['type'] == 'workflow/llm_model')
            logging.info(f"Plan généré avec succès avec {agent_count} agent(s). Démarrage de l'exécution.")
            
            window.evaluate_js(f"window.maestro_api.updateStatus('<i>Exécution du plan avec {agent_count} agent(s) spécialisé(s)...</i>')")
            api_instance._run_workflow_stream_worker(filename, user_prompt, global_model)
            
            break

        except json.JSONDecodeError as e:
            if attempt < MAX_RETRIES - 1:
                logging.warning(f"Erreur de parsing JSON (tentative {attempt + 1}): {e}. Nouvelle tentative...")
                window.evaluate_js(f"window.maestro_api.updateStatus('<i>Nouvelle tentative de génération (essai {attempt + 2}/{MAX_RETRIES})...</i>')")
                time.sleep(1)
                continue
            else:
                error_message = f"Erreur de parsing JSON après {MAX_RETRIES} tentatives : {e}"
                logging.error(f"{error_message}\n{traceback.format_exc()}")
                window.evaluate_js(f"window.maestro_api.displayError({escape_js_string(error_message)})")
                return
                
        except Exception as e:
            error_message = f"Une erreur critique est survenue dans Maestro : {e}"
            logging.error(f"{error_message}\n{traceback.format_exc()}")
            window.evaluate_js(f"window.maestro_api.displayError({escape_js_string(error_message)})")
            return