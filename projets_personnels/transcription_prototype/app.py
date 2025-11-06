import webview
import whisper
import threading
import traceback
import torch
import warnings
from tkinter import Tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
import requests
from packaging import version
import subprocess
import json
import os
import tempfile
from pathlib import Path
import shutil
import re

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

SEGMENT_DURATION_MINUTES = 2
MIN_DURATION_FOR_SPLIT = 4 * 60

def check_pytorch_update():
    """Vérifie si une nouvelle version de PyTorch (pour CUDA) est disponible."""
    try:
        current_ver_str = torch.__version__
        current_ver = version.parse(current_ver_str.split('+')[0])
        
        cuda_ver_simple = torch.version.cuda.replace('.', '')
        
        print(f"Version PyTorch actuelle : {current_ver_str}")

        response = requests.get("https://pypi.org/pypi/torch/json", timeout=5)
        response.raise_for_status()
        
        latest_ver_str = response.json()['info']['version']
        latest_ver = version.parse(latest_ver_str)

        if latest_ver > current_ver:
            print("\n--- MISE À JOUR DISPONIBLE ---")
            print(f"Une nouvelle version de PyTorch est disponible : {latest_ver_str}")
            print("Pour mettre à jour et conserver le support GPU, utilisez cette commande :")
            
            update_command = (
                f"pip install --upgrade torch torchvision torchaudio "
                f"--index-url https://download.pytorch.org/whl/cu{cuda_ver_simple}"
            )
            print(f"\n  {update_command}\n")
            print("-----------------------------\n")

    except requests.exceptions.RequestException as e:
        print(f"[Info] Impossible de vérifier les mises à jour de PyTorch : {e}")
    except Exception as e:
        print(f"[Info] Erreur lors de la vérification des mises à jour de PyTorch : {e}")

def get_audio_duration(file_path):
    """Obtient la durée du fichier audio/vidéo en secondes."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"Erreur lors de la lecture de la durée : {e}")
        return None

def split_audio(file_path, segment_duration_minutes, temp_dir):
    """
    Découpe un fichier audio/vidéo en segments de durée définie.
    Retourne une liste de chemins vers les segments créés.
    """
    try:
        segment_duration_seconds = segment_duration_minutes * 60
        segments = []
        
        total_duration = get_audio_duration(file_path)
        if total_duration is None:
            raise Exception("Impossible de déterminer la durée du fichier")
        
        print(f"Durée totale du fichier : {total_duration/60:.1f} minutes")
        
        num_segments = int(total_duration / segment_duration_seconds) + 1
        print(f"Découpage en {num_segments} segments de {segment_duration_minutes} minutes")
        
        for i in range(num_segments):
            start_time = i * segment_duration_seconds
            segment_path = os.path.join(temp_dir, f"segment_{i:03d}.wav")
            
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-ss', str(start_time),
                '-t', str(segment_duration_seconds),
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                segment_path
            ]
            
            print(f"Création du segment {i+1}/{num_segments}...")
            subprocess.run(cmd, capture_output=True, check=True)
            segments.append(segment_path)
        
        return segments
    
    except Exception as e:
        print(f"Erreur lors du découpage : {e}")
        raise

window = None

class Api:
    def __init__(self):
        self.current_model = None
        self.current_model_name = None
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.use_fp16 = self.device == "cuda"
        
        if self.device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU détecté: {gpu_name}")
            print(f"Mémoire GPU: {gpu_memory:.1f} GB")
            print(f"CUDA Version: {torch.version.cuda}")
            
            torch.cuda.empty_cache()
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
        else:
            print("⚠️ Aucun GPU détecté - Utilisation du CPU (sera plus lent)")

    def get_gpu_status(self):
        if self.device == "cuda":
            return {
                "available": True,
                "name": torch.cuda.get_device_name(0),
                "memory": f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB"
            }
        return {"available": False}
    
    def handle_dropped_file(self, base64_data, filename):
        """Gère un fichier déposé depuis l'interface en le sauvegardant temporairement."""
        try:
            import base64
            
            file_data = base64.b64decode(base64_data)
            
            file_extension = Path(filename).suffix
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            temp_file.write(file_data)
            temp_file.close()
            
            print(f"Fichier déposé sauvegardé temporairement: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            print(f"Erreur lors du traitement du fichier déposé: {e}")
            traceback.print_exc()
            return None

    def open_file_dialog(self):
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        file_path = askopenfilename(
            title="Sélectionnez un fichier audio ou vidéo",
            filetypes=[
                ("Fichiers Média", "*.mp3 *.wav *.m4a *.mp4 *.mov *.avi *.mkv"),
                ("Tous les fichiers", "*.*")
            ]
        )
        root.destroy()
        return file_path

    def transcribe_file(self, file_path, model_name):
        thread = threading.Thread(target=self._transcribe_thread, args=(file_path, model_name))
        thread.daemon = True
        thread.start()

    def _transcribe_segment(self, segment_path, segment_num, total_segments):
        global window
        
        try:
            progress = (segment_num - 1) / total_segments * 100
            status_msg = f"Transcription du segment {segment_num}/{total_segments}..."
            progress_data = json.dumps({"percent": progress, "text": status_msg})
            window.evaluate_js(f'updateProgress({progress_data})')
            
            transcribe_options = {
                "fp16": self.use_fp16,
                "language": None,
                "task": "transcribe",
                "verbose": False,
            }
            
            if self.device == "cuda":
                transcribe_options.update({
                    "beam_size": 10,
                    "best_of": 10,
                    "temperature": 0,
                    "condition_on_previous_text":True,
                })
            
            with torch.cuda.amp.autocast() if self.device == "cuda" else torch.no_grad():
                result = self.current_model.transcribe(segment_path, **transcribe_options)
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            return result['text'], result.get('language', 'unknown')
            
        except Exception as e:
            print(f"Erreur lors de la transcription du segment {segment_num}: {e}")
            raise

    def _transcribe_thread(self, file_path, model_name):
        global window
        temp_dir = None
        
        try:
            if not file_path:
                raise ValueError("Aucun fichier fourni.")
            
            if self.current_model_name != model_name:
                print(f"Chargement du modèle Whisper ({model_name}) sur {self.device}...")
                device_info = "GPU (CUDA)" if self.device == "cuda" else "CPU"
                window.evaluate_js(
                    f'updateProgress({{"percent": 0, "text": "Chargement du modèle {model_name} sur {device_info}..."}})'
                )
                
                if self.current_model is not None and self.device == "cuda":
                    del self.current_model
                    torch.cuda.empty_cache()
                
                self.current_model = whisper.load_model(model_name, device=self.device)
                self.current_model_name = model_name
                
                if self.device == "cuda":
                    self.current_model = self.current_model.cuda()
                    self.current_model.eval()
                    memory_used = torch.cuda.memory_allocated() / 1024**3
                    print(f"Mémoire GPU utilisée: {memory_used:.2f} GB")
                
                print(f"Modèle {model_name} chargé sur {self.device}.")

            transcribe_options = {
                "fp16": self.use_fp16,
                "language": None,
                "task": "transcribe",
                "verbose": False,
            }
            if self.device == "cuda":
                transcribe_options.update({"beam_size": 5, "best_of": 5, "temperature": 0})

            duration = get_audio_duration(file_path)
            
            if duration is not None and duration > MIN_DURATION_FOR_SPLIT:
                print(f"Fichier long détecté ({duration/60:.1f} min) - Découpage automatique activé")
                window.evaluate_js(
                    f'updateProgress({{"percent": 0, "text": "Fichier long détecté - Découpage en segments..."}})'
                )
                
                temp_dir = tempfile.mkdtemp(prefix="whisper_segments_")
                print(f"Répertoire temporaire : {temp_dir}")
                
                segments = split_audio(file_path, SEGMENT_DURATION_MINUTES, temp_dir)
                
                transcripts = []
                detected_language = None
                
                for i, segment_path in enumerate(segments, 1):
                    transcript, lang = self._transcribe_segment(segment_path, i, len(segments))
                    transcripts.append(transcript)
                    if detected_language is None and lang != 'unknown':
                        detected_language = lang
                
                full_transcript = " ".join(transcripts)
                
            else:
                if duration:
                    print(f"Fichier court ({duration/60:.1f} min) - Transcription directe")
                else:
                    print("Durée inconnue - Transcription directe")
                
                window.evaluate_js(f'updateProgress({{"percent": 0, "text": "Transcription en cours..."}})')
                
                with torch.cuda.amp.autocast() if self.device == "cuda" else torch.no_grad():
                    result = self.current_model.transcribe(file_path, **transcribe_options)
                
                full_transcript = result['text']
                detected_language = result.get('language', 'unknown')
            
            print("Transcription terminée.")
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            response = {
                "status": "success", 
                "transcript": full_transcript,
                "language": detected_language,
                "device_used": self.device.upper(),
                "duration_minutes": duration/60 if duration else None,
                "was_split": duration is not None and duration > MIN_DURATION_FOR_SPLIT
            }

        except torch.cuda.OutOfMemoryError:
            print("[Erreur] Mémoire GPU insuffisante")
            if self.device == "cuda": torch.cuda.empty_cache()
            response = {"status": "error", "message": "Mémoire GPU insuffisante. Essayez un modèle plus petit."}
        except FileNotFoundError as e:
            print(f"[Erreur] Fichier non trouvé : {e}")
            response = {"status": "error", "message": "Erreur : FFmpeg non trouvé. Assurez-vous qu'il est installé."}
        except Exception as e:
            print(f"Erreur pendant la transcription : {e}")
            traceback.print_exc()
            response = {"status": "error", "message": str(e)}
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print(f"Répertoire temporaire supprimé : {temp_dir}")
                except Exception as e:
                    print(f"Erreur lors du nettoyage : {e}")

        response_json = json.dumps(response, ensure_ascii=False)
        window.evaluate_js(f'updateTranscriptionResult({response_json})')

    def process_transcription(self, text, profile):
        thread = threading.Thread(target=self._process_thread, args=(text, profile))
        thread.daemon = True
        thread.start()


    def _cleanup_latex_code(self, latex_code):
        """
        Nettoie et corrige les erreurs courantes dans le code LaTeX généré par l'IA.
        """
        environments = ["tblr", "itemize", "enumerate"]
        for env in environments:
            begin_tag = f"\\begin{{{env}}}"
            end_tag = f"\\end{{{env}}}"
            if latex_code.count(begin_tag) > latex_code.count(end_tag):
                print(f"AVERTISSEMENT : Correction d'un environnement '{env}' non fermé.")
                latex_code += f"\n{end_tag}"

        latex_code = re.sub(r'\\begin{itemize}(\[.*?\])?\s*\\end{itemize}', '', latex_code)
        latex_code = re.sub(r'\\begin{enumerate}(\[.*?\])?\s*\\end{enumerate}', '', latex_code)
        
        latex_code = re.sub(r'\\vbox\s*\{', '', latex_code)
        open_braces = latex_code.count('{')
        close_braces = latex_code.count('}')
        if open_braces > close_braces:
            latex_code = latex_code.rstrip() + '}' * (open_braces - close_braces)
        
        latex_code = latex_code.lstrip()
        
        latex_code = re.sub(r'^\\newpage\s*', '', latex_code)
        latex_code = re.sub(r'^\\clearpage\s*', '', latex_code)
        latex_code = re.sub(r'^\\pagebreak\s*', '', latex_code)
        
        latex_code = re.sub(
            r'\\begin{itemize}\[([^\]]*)\]',
            r'\\begin{itemize}[nosep, leftmargin=*, label=\\textbullet]',
            latex_code
        )
        
        return latex_code

    def _process_thread(self, text, profile):
        global window
        try:
            if not text or text.strip() == "":
                response = {"status": "error", "message": "Aucun texte à traiter."}
                response_json = json.dumps(response, ensure_ascii=False)
                window.evaluate_js(f'updateProcessingResult({response_json})')
                return

            print(f"Début du traitement avec Ollama (Profil: {profile})...")
            window.evaluate_js('updateProcessingStatus("Traitement du texte avec Ollama...")')

            prompts = {
                "embellir": """Tu es un assistant spécialisé dans la mise en forme de transcriptions.
                Ta tâche est de recopier le texte fourni le plus fidèlement possible, tout en appliquant une surcouche de structure textuelle avec d'éventuels titres et sous-titres. 
                Les fautes d'orthographe, les éventuelles erreurs ou incohérences de transcription, et les erreurs de conjugaison doivent être corrigées également.
                TA RÉPONSE DOIT ÊTRE UNIQUEMENT AU FORMAT LATEX.
                - Utilise `\\section{Titre}` pour les titres principaux.
                - Utilise `\\subsection{Sous-titre}` pour les sections secondaires.
                - Utilise l'environnement `itemize` avec `\\item` pour les listes à puces.
                - Utilise `\\textbf{texte}` pour le gras et `\\textit{texte}` pour l'italique.
                - N'inclus PAS le préambule LaTeX (pas de `\\documentclass`, `\\begin{document}`, etc.).
                
                Voici le texte à traiter :""",

                "resumer": """Tu es un assistant spécialisé dans la mise en forme de transcriptions.
                Ta tâche est de corriger et de structurer le texte fourni.
                TA RÉPONSE DOIT ÊTRE UNIQUEMENT AU FORMAT LATEX.
                - Utilise `\\section{Titre}` pour les titres principaux.
                - Utilise `\\subsection{Sous-titre}` pour les sections secondaires.
                - Utilise l'environnement `itemize` avec `\\item` pour les listes à puces.
                - Utilise `\\textbf{texte}` pour le gras et `\\textit{texte}` pour l'italique.
                - N'inclus PAS le préambule LaTeX (pas de `\\documentclass`, `\\begin{document}`, etc.).

                Voici le texte à traiter :""",

                "developper": """Tu es un assistant spécialisé dans l'enseignement. Développe les sujets de la transcription pour en améliorer la compréhension.
                TA RÉPONSE DOIT ÊTRE UNIQUEMENT AU FORMAT LATEX.
                - Structure ta réponse avec `\\section{Thème}` et `\\subsection{Sous-thème}`.
                - Explique les concepts en utilisant des paragraphes clairs.
                - N'inclus PAS le préambule LaTeX (pas de `\\documentclass`, `\\begin{document}`, etc.).

                Voici la transcription à traiter :""",
  
                "themes": """Tu es un expert LaTeX spécialisé dans le package moderne `tabularray`.
                Ta tâche est de créer un tableau récapitulatif parfait à partir de la transcription.

                TA RÉPONSE DOIT ÊTRE UNIQUEMENT LE CODE LATEX POUR LE TABLEAU, SANS AUCUN AUTRE TEXTE.

                Instructions OBLIGATOIRES :
                1.  Utilise l'environnement `tblr`.
                2.  La configuration du tableau DOIT être la suivante :
                    `\\begin{tblr}{
                    width = \\textwidth,
                    colspec = {X[0.6, c, m] X[1.5, j, m] X[0.9, c, m]},
                    row{1} = {font=\\bfseries, c, m},
                    rowhead = 1,
                    hlines,
                    vlines,
                    }`
                3.  Les en-têtes sont sur la première ligne, séparés par `&`. Les en-têtes sont : "Thème Principal", "Description / Points Clés", "Mots-clés".
                4.  Pour les listes dans les cellules, tu DOIS utiliser cette structure EXACTE :
                    `\\begin{itemize}[nosep, leftmargin=*, label=\\textbullet]
                    \\item Premier point
                    \\item Deuxième point
                    \\end{itemize}`
                5.  N'utilise JAMAIS de \\vbox dans les cellules.
                6.  Pour le texte justifié dans la colonne centrale, écris simplement le texte sans commande spéciale.
                7.  Ta réponse doit commencer par `\\begin{tblr}{...}` et se terminer par `\\end{tblr}`.
                8.  IMPORTANT : Évite les listes vides. Chaque itemize doit contenir au moins un \\item.

                Voici le texte à traiter :"""
                 
            }

            system_instruction = prompts.get(profile, prompts["embellir"])
            full_prompt = system_instruction + text

            import requests
            
            try:
                print("Envoi de la requête à Ollama...")
                
                ollama_url = "http://localhost:11434/api/generate"
                
                payload = {
                    "model": "hf.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF:IQ2_M",
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": -1,
                        "num_ctx": 65000,
                    }
                }
                
                response_api = requests.post(
                    ollama_url,
                    json=payload,
                    timeout=900
                )
                
                if response_api.status_code == 200:
                    result_data = response_api.json()
                    output_text = result_data.get('response', '').strip()
                    
                    output_text = self._cleanup_latex_code(output_text)

                    print(f"Traitement terminé. Longueur de la réponse: {len(output_text)} caractères")
                    
                    response = {
                        "status": "success",
                        "processed_text": output_text
                    }
                else:
                    error_msg = f"Erreur HTTP {response_api.status_code}: {response_api.text}"
                    print(f"Erreur Ollama API: {error_msg}")
                    response = {
                        "status": "error",
                        "message": f"Erreur lors du traitement Ollama: {error_msg}"
                    }
                    
            except requests.exceptions.ConnectionError:
                print("Impossible de se connecter à Ollama")
                response = {
                    "status": "error",
                    "message": "Impossible de se connecter à Ollama. Assurez-vous qu'Ollama est démarré (ollama serve)."
                }
            except requests.exceptions.Timeout:
                response = {
                    "status": "error",
                    "message": "Timeout: Le traitement a pris trop de temps (plus de 5 minutes)."
                }

        except Exception as e:
            print(f"Erreur pendant le traitement: {e}")
            traceback.print_exc()
            response = {"status": "error", "message": str(e)}

        response_json = json.dumps(response, ensure_ascii=False)
        window.evaluate_js(f'updateProcessingResult({response_json})')

    def save_file(self, content, file_type):
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        file_types_map = {
            'txt': [("Fichiers Texte (LaTeX)", "*.tex"), ("Tous les fichiers", "*.*")],
            'pdf': [("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")]
        }
        
        default_extension = ".tex" if file_type == 'txt' else f".{file_type}"
        
        file_path = asksaveasfilename(
            defaultextension=default_extension,
            filetypes=file_types_map.get(file_type, [("Tous les fichiers", "*.*")]),
            title=f"Enregistrer le fichier .{file_type}"
        )
        
        root.destroy()

        if not file_path:
            return {"status": "cancelled", "message": "Sauvegarde annulée."}

        try:
            if file_type == 'pdf':
                temp_dir = None
                try:
                    latex_preamble = r"""
\documentclass[12pt, a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[french]{babel}
\usepackage{geometry}
\geometry{a4paper, margin=0.75in, top=0.75in, bottom=0.75in}
\usepackage{hyperref}
\usepackage{tabularray}
\usepackage{enumitem}
\usepackage{ragged2e}  % Pour une meilleure justification
\UseTblrLibrary{booktabs, varwidth}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,      
    urlcolor=cyan,
    pdftitle={Transcription Traitée},
    pdfpagemode=FullScreen,
}

% Configuration globale pour les listes dans tabularray
\SetTblrInner[itemize]{itemsep=2pt, topsep=2pt}

% Supprimer l'indentation des paragraphes
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

% Éliminer l'espace vertical au début du document
\AtBeginDocument{\vspace*{-2cm}}

\begin{document}
\pagestyle{empty} % Supprimer les numéros de page
\thispagestyle{empty} % S'assurer que la première page n'a pas de numéro

"""
                    latex_postamble = r"\end{document}"
                    
                    full_latex_content = f"{latex_preamble}\n{content}\n{latex_postamble}"
                    
                    temp_dir = tempfile.mkdtemp(prefix="latex_compile_")
                    base_name = "output"
                    tex_file_path = os.path.join(temp_dir, f"{base_name}.tex")
                    
                    with open(tex_file_path, 'w', encoding='utf-8') as f:
                        f.write(full_latex_content)
                        
                    command = [
                        'pdflatex',
                        '-interaction=nonstopmode',
                        '-output-directory', temp_dir,
                        tex_file_path
                    ]
                    
                    print(f"Compilation LaTeX dans : {temp_dir}")
                    for i in range(2):
                        print(f"Passe de compilation {i+1}/2...")
                        result = subprocess.run(command, capture_output=True, text=True)
                        if result.returncode != 0:
                            print("--- ERREUR DE COMPILATION LATEX ---")
                            print(result.stdout)
                            log_path = os.path.join(temp_dir, f"{base_name}.log")
                            if os.path.exists(log_path):
                                with open(log_path, 'r', encoding='utf-8') as log_file:
                                    log_content = log_file.read()
                                error_line = next((line for line in log_content.splitlines() if line.startswith('! ')), "Détails dans le fichier .log")
                                raise RuntimeError(f"La compilation LaTeX a échoué. Erreur : {error_line}")
                            raise RuntimeError("La compilation LaTeX a échoué. Vérifiez le code LaTeX.")

                    generated_pdf_path = os.path.join(temp_dir, f"{base_name}.pdf")
                    if os.path.exists(generated_pdf_path):
                        shutil.move(generated_pdf_path, file_path)
                        print(f"PDF généré et déplacé vers : {file_path}")
                    else:
                        raise FileNotFoundError("Le fichier PDF n'a pas été généré par pdflatex.")

                except FileNotFoundError:
                    return {"status": "error", "message": "Commande 'pdflatex' non trouvée. Assurez-vous qu'une distribution LaTeX (MiKTeX, TeX Live) est installée et dans votre PATH."}
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"Répertoire temporaire supprimé : {temp_dir}")
            
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            print(f"Fichier enregistré avec succès : {file_path}")
            return {"status": "success", "message": f"Fichier enregistré : {file_path}"}

        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": f"Une erreur inattendue est survenue: {str(e)}"}

    def get_system_info(self):
        info = {
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": self.device,
            "fp16_enabled": self.use_fp16
        }
        
        if torch.cuda.is_available():
            info.update({
                "cuda_version": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_memory_gb": torch.cuda.get_device_properties(0).total_memory / 1024**3
            })
        
        return info

if __name__ == '__main__':
    torch.set_num_threads(1)
    
    import multiprocessing
    multiprocessing.freeze_support()
    
    api = Api()

    print("\n=== Configuration Système ===")
    sys_info = api.get_system_info()
    for key, value in sys_info.items():
        print(f"{key}: {value}")
    print(f"Découpage automatique: activé pour les fichiers > {MIN_DURATION_FOR_SPLIT/60:.0f} minutes")
    print(f"Durée des segments: {SEGMENT_DURATION_MINUTES} minutes")
    print("============================\n")

    if torch.cuda.is_available():
        check_pytorch_update()

    window = webview.create_window(
        'Scribe',
        'gui/index.html',
        js_api=api,
        width=1200,
        height=900,
        min_size=(600, 500),
        easy_drag=True,
    )
    
    webview.start(debug=False)