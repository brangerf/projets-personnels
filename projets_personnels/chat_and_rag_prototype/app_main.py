# app_main.py

import webview
import threading
import requests
import json
import os
import re
import base64
import traceback
import statistics

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# --- Configuration du dossier de base ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Constantes pour le RAG ---
CONTEXT_WINDOW_WORDS = 250 
MAX_SNIPPETS = 10
MAX_SEGMENT_WORD_DISTANCE = 500 

JACCARD_SIMILARITY_THRESHOLD = 0.7

KEYWORD_EXTRACTION_PROMPT_TEMPLATE = """
Tu es un expert en analyse sémantique. Ton rôle est d'identifier les concepts clés dans la question d'un utilisateur et leurs variations lexicales.
Extrais les **noms et entités spécifiques** essentiels à la recherche. Pour chaque terme, fournis une liste de ses variations (singulier, pluriel, masculin, féminin, adjectif, etc.).
Ignore les termes conceptuels vagues comme "rapport", "relation", "lien".

Ta réponse DOIT être un objet JSON contenant une seule clé "termes_cles" avec une liste de listes de chaînes de caractères.

Exemple 1:
Question: "Quel est le rapport entre la musique et les stoïciens ?"
Ta réponse:
{{
  "termes_cles": [
    ["musique", "musical", "mélodie"],
    ["stoïcien", "stoïciens", "stoïcienne", "stoïciennes", "stoïcisme", "stoïque"]
  ]
}}

Exemple 2:
Question: "La définition de la justice dans la République de Platon"
Ta réponse:
{{
  "termes_cles": [
    ["justice", "juste"],
    ["République"],
    ["Platon"]
  ]
}}

Question de l'utilisateur: "{question}"
Ta réponse:
"""

RAG_PROMPT_TEMPLATE = """
Tu es un assistant IA spécialisé dans l'analyse de documents.
Réponds à la question de l'utilisateur en te basant EXCLUSIVEMENT sur le contexte suivant.
Ne mentionne pas que tu utilises un contexte, réponds directement. Si la réponse ne se trouve pas dans le contexte, dis clairement "L'information n'a pas été trouvée dans le document fourni.".

--- CONTEXTE EXTRAIT DU DOCUMENT ---
{context}
--- FIN DU CONTEXTE ---

Question de l'utilisateur : {question}
"""


class Api:
    def __init__(self):
        self.document_text = ""
        self.document_words = []
        self.prompt_file_path = os.path.join(BASE_DIR, 'system_prompt.txt')

    def get_initial_system_prompt(self):
        try:
            with open(self.prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "You are a helpful AI assistant."

    def save_system_prompt(self, prompt_text):
        try:
            with open(self.prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du prompt système : {e}")

    def _escape_js_string(self, text):
        return text.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')

    def _clean_text(self, text):
        text = re.sub(r'-\s*\n', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _highlight_terms(self, text, term_groups):
        all_terms = {term for group in term_groups for term in group}
        sorted_terms = sorted(list(all_terms), key=len, reverse=True)
        highlighted_text = text
        for term in sorted_terms:
            pattern = r'\b(' + re.escape(term) + r')\b'
            replacement = r'<mark>\1</mark>'
            highlighted_text = re.sub(pattern, replacement, highlighted_text, flags=re.IGNORECASE)
        return highlighted_text

    def get_installed_models(self):
        try:
            response = requests.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            return sorted([model['name'] for model in response.json()['models']])
        except requests.exceptions.RequestException:
            return ["OLLAMA_OFFLINE"]
        except Exception:
            return []

    def send_message_to_ollama(self, message_history, model_name, model_options, system_prompt_text):
        threading.Thread(target=self._ollama_worker_stream, args=(message_history, model_name, model_options, system_prompt_text)).start()

    def _ollama_worker_stream(self, message_history, model_name, model_options, system_prompt_text, custom_prompt=None):
        window = webview.windows[0]
        try:
            options = { "temperature": float(model_options.get("temperature", 0.7)), "num_predict": int(model_options.get("num_predict", -1)), "num_ctx": int(model_options.get("num_ctx", 4096)) }
            api_messages = [{"role": "user", "content": custom_prompt}] if custom_prompt else [{"role": "system", "content": system_prompt_text or "You are a helpful AI assistant."}] + list(message_history)
            payload = { "model": model_name, "messages": api_messages, "stream": True, "options": options }

            with requests.post("http://localhost:11434/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        content_part = chunk['message']['content']
                        if not content_part.startswith('<context>'):
                            window.evaluate_js(f"window.api.appendToResponse(`{self._escape_js_string(content_part)}`)")
            
            window.evaluate_js("window.api.finalizeResponse()")

        except requests.exceptions.RequestException as e:
            error_msg = f'Erreur de connexion à Ollama. Détails : {e}'
            window.evaluate_js(f"window.api.showError('{self._escape_js_string(error_msg)}')")
        except Exception as e:
            error_msg = f'Une erreur inattendue est survenue : {e}'
            window.evaluate_js(f"window.api.showError('{self._escape_js_string(error_msg)}')")

    def load_document(self, file_data):
        try:
            file_name, data_url = file_data['name'], file_data['data']
            _, encoded = data_url.split(",", 1)
            decoded_bytes = base64.b64decode(encoded)
            raw_text = ""
            if file_name.lower().endswith('.pdf'):
                if not fitz: raise ImportError("PyMuPDF n'est pas installé.")
                with fitz.open(stream=decoded_bytes, filetype="pdf") as doc:
                    raw_text = "".join(page.get_text() for page in doc)
            elif file_name.lower().endswith(('.txt', '.md')):
                raw_text = decoded_bytes.decode('utf-8')
            else:
                raise ValueError("Type de fichier non supporté.")
            
            print("[RAG] Nettoyage du texte extrait...")
            self.document_text = self._clean_text(raw_text)
            self.document_words = self.document_text.split(' ')
            print(f"[RAG] Document chargé et nettoyé. ({len(self.document_words)} mots)")
            
            return len(self.document_text)
        except Exception as e:
            raise webview.errors.JavascriptException(self._escape_js_string(f"Erreur lors du traitement du document : {e}"))
    
    def _get_structured_keywords_from_llm(self, question, model_name):
        try:
            prompt_content = KEYWORD_EXTRACTION_PROMPT_TEMPLATE.format(question=question)
            payload = {"model": model_name, "messages": [{"role": "user", "content": prompt_content}], "stream": False, "options": {"temperature": 0.0}}
            
            print(f"[RAG] Extraction des termes clés avec le modèle {model_name}...")
            response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=45)
            response.raise_for_status()
            
            response_text = response.json()['message']['content'].strip()
            print(f"[RAG] Réponse brute du LLM: {repr(response_text)}")
            
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if 'termes_cles' in data and isinstance(data['termes_cles'], list) and data['termes_cles']:
                    print(f"[RAG] Termes clés extraits: {data['termes_cles']}")
                    return data['termes_cles']
            
            print(f"[RAG] Impossible d'extraire une liste de listes de termes clés valide.")
            return None
            
        except Exception as e:
            print(f"[RAG] Erreur inattendue lors de l'extraction des termes clés: {e}")
            traceback.print_exc()
            return None

    def rag_query(self, question, model_name, model_options):
        threading.Thread(target=self._rag_worker, args=(question, model_name, model_options)).start()

    def _rag_worker(self, question, model_name, model_options):
        window = webview.windows[0]
        
        if not self.document_words:
            window.evaluate_js("window.api.showError('Aucun document chargé.')")
            return

        print(f"[RAG] Début de la requête RAG pour: {question}")
        
        key_term_groups = self._get_structured_keywords_from_llm(question, model_name)
        if not key_term_groups:
            error_msg = "Le LLM n'a pas pu déterminer les termes de recherche."
            window.evaluate_js(f"window.api.showError('{self._escape_js_string(error_msg)}')")
            return
            
        print("[RAG] Indexation des positions des termes clés...")
        text_lower = self.document_text.lower()
        term_locations = []
        for group_id, group in enumerate(key_term_groups):
            for term in group:
                term_lower = term.lower()
                try:
                    for match in re.finditer(r'\b' + re.escape(term_lower) + r'\b', text_lower):
                        word_pos_approx = text_lower[:match.start()].count(' ')
                        term_locations.append({'pos': match.start(), 'group_id': group_id, 'word_pos': word_pos_approx})
                except re.error:
                    print(f"[RAG] Erreur de regex avec le terme: {term_lower}")
        
        if not term_locations:
            error_msg = "Aucun des termes clés n'a été trouvé dans le document."
            window.evaluate_js(f"window.api.showError('{self._escape_js_string(error_msg)}')")
            return
        
        term_locations.sort(key=lambda x: x['pos'])
        print(f"[RAG] {len(term_locations)} occurrences de termes trouvées et triées.")

        print("[RAG] Génération optimisée des segments candidats...")
        best_segments = []
        for i in range(len(term_locations)):
            start_term = term_locations[i]
            groups_in_segment = {start_term['group_id']}
            
            for j in range(i, len(term_locations)):
                current_term = term_locations[j]

                if current_term['word_pos'] - start_term['word_pos'] > MAX_SEGMENT_WORD_DISTANCE:
                    break

                groups_in_segment.add(current_term['group_id'])
                
                score = len(groups_in_segment)
                start_pos_char = start_term['pos']
                end_pos_char = current_term['pos']
                density = end_pos_char - start_pos_char + 1

                positions_in_segment = [loc['pos'] for loc in term_locations[i:j+1]]
                std_dev = statistics.stdev(positions_in_segment) if len(positions_in_segment) > 1 else 0.0

                best_segments.append({
                    'start': start_pos_char,
                    'end': end_pos_char,
                    'score': score,
                    'density': density,
                    'standard_deviation': std_dev
                })
        
        print(f"[RAG] {len(best_segments)} segments candidats générés.")
        
        print("[RAG] Tri des segments...")
        best_segments.sort(key=lambda x: (x['score'], -x['density'], -x['standard_deviation']), reverse=True)

        print("[RAG] Sélection et déduplication des meilleurs extraits...")
        unique_results = []
        for segment in best_segments:
            char_window = CONTEXT_WINDOW_WORDS * 5 
            start_context_char = max(0, segment['start'] - char_window)
            end_context_char = min(len(self.document_text), segment['end'] + char_window)
            
            snippet_text = self.document_text[start_context_char:end_context_char]
            
            first_space = snippet_text.find(' ')
            last_space = snippet_text.rfind(' ')
            if first_space != -1 and start_context_char > 0: snippet_text = snippet_text[first_space+1:]
            if last_space != -1 and end_context_char < len(self.document_text): snippet_text = snippet_text[:last_space]
            
            if not snippet_text:
                continue

            is_too_similar = False
            words_new = set(snippet_text.lower().split())

            for existing_item in unique_results:
                words_existing = set(existing_item['snippet'].lower().split())
                
                intersection_len = len(words_new.intersection(words_existing))
                union_len = len(words_new.union(words_existing))
                
                if union_len == 0:
                    similarity = 1.0
                else:
                    similarity = intersection_len / union_len

                if similarity > JACCARD_SIMILARITY_THRESHOLD:
                    is_too_similar = True
                    break 

            if not is_too_similar:
                method = f"Score {segment['score']}/{len(key_term_groups)} (densité: {segment['density']}, écart-type: {segment['standard_deviation']:.2f})"
                unique_results.append({'snippet': snippet_text, 'method': method})
                if len(unique_results) >= MAX_SNIPPETS:
                    break
        
        print(f"[RAG] {len(unique_results)} extraits uniques et pertinents trouvés après déduplication.")

        context_for_ui_parts = []
        retrieved_context_for_llm = []

        print("\n[RAG] --- DÉBUT DU CONTENU DES EXTRAITS SÉLECTIONNÉS ---")
        for i, item in enumerate(unique_results):
            clean_snippet = item['snippet']
            highlighted_snippet = self._highlight_terms(clean_snippet, key_term_groups)
            
            print(f"\n--- EXTRAIT {i+1} (Méthode: {item['method']}) ---")
            print(clean_snippet)

            context_for_ui_parts.append(f"--- Extrait {i+1} ({item['method']}) ---\n{highlighted_snippet}")
            retrieved_context_for_llm.append(clean_snippet)
        print("\n[RAG] --- FIN DU CONTENU DES EXTRAITS SÉLECTIONNÉS ---\n")
        
        if not retrieved_context_for_llm:
             error_msg = "Aucun extrait suffisamment pertinent et unique n'a pu être trouvé pour répondre à la question."
             window.evaluate_js(f"window.api.showError('{self._escape_js_string(error_msg)}')")
             return

        full_context_block = f"<context>{'\n\n'.join(context_for_ui_parts)}</context>"
        window.evaluate_js(f"window.api.appendToResponse(`{self._escape_js_string(full_context_block)}`)")

        final_prompt = RAG_PROMPT_TEMPLATE.format(context="\n\n---\n\n".join(retrieved_context_for_llm), question=question)
        self._ollama_worker_stream([], model_name, model_options, "", custom_prompt=final_prompt)
    
    def extract_text_from_file(self, file_data):
        try:
            file_name, data_url = file_data['name'], file_data['data']
            _, encoded = data_url.split(",", 1)
            decoded_bytes = base64.b64decode(encoded)
            raw_text = ""

            if file_name.lower().endswith('.pdf'):
                if not fitz:
                    raise ImportError("PyMuPDF doit être installé pour lire les fichiers PDF.")
                with fitz.open(stream=decoded_bytes, filetype="pdf") as doc:
                    raw_text = "".join(page.get_text() for page in doc)
            elif file_name.lower().endswith(('.txt', '.md')):
                raw_text = decoded_bytes.decode('utf-8')
            else:
                raise ValueError("Type de fichier non supporté (.txt, .md, .pdf uniquement).")
            
            return self._clean_text(raw_text)

        except Exception as e:
            raise webview.errors.JavascriptException(self._escape_js_string(f"Erreur lors de l'extraction du texte : {e}"))


if __name__ == '__main__':
    api = Api()
    html_file = os.path.join(BASE_DIR, 'interface.html')
    window = webview.create_window('Ollama Chat', url=html_file, js_api=api, width=1200, height=800, min_size=(800, 600))
    webview.start(debug=False)