# NebuAI

  Your ollama cat companion.

![NebuAI Ollama Cat](https://github.com/user-attachments/assets/753e159c-8e4f-4208-a979-059365cd1f87)

# Installation
1. Create (or enter) a virtual environnement.
2. Install the requirements
```bash
pip install -r requirements.txt
```
3. Install (or update) [Couscous](https://github.com/Viagounet/couscous)
In the cloned *couscous* repository (make sure you're still in your virtual environnement)
```bash
git pull
pip install .
```
# Start the interface
## With Ollama
### With the first found Ollama model
```bash
python NebuAI_Dash.py
```
### Starting with a default model
```bash
python NebuAI_Dash.py --default_model="phi3:latest"
```

## With OpenAI API
### With the first found OpenAI model
```bash
python NebuAI_Dash.py --inference_mode=openai
```
### Starting with a default model
```bash
python NebuAI_Dash.py --inference_mode=openai --default_model="gpt-4-turbo"
```