"""
Registre central pour tous les types de nœuds disponibles dans l'application.
Cette structure unique sert de "source de vérité" pour :
- La génération automatique des options d'interface
- La construction dynamique des prompts Maestro
- La validation des workflows
- L'extensibilité future
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class NodeCategory(Enum):
    """Catégories de nœuds pour l'organisation"""
    INPUT = "input"
    PROCESSING = "processing"  
    OUTPUT = "output"
    UTILITY = "utility"
    VISUALIZATION = "visualization"

@dataclass
class NodeSlot:
    """Définition d'un slot d'entrée ou de sortie"""
    name: str
    type: str
    description: str
    required: bool = True

@dataclass
class NodeProperty:
    """Définition d'une propriété configurable du nœud"""
    name: str
    type: str
    description: str
    default: Any = None
    options: Optional[List[str]] = None
    placeholder: Optional[str] = None

@dataclass
class NodeDefinition:
    """Définition complète d'un type de nœud"""
    node_type: str
    title: str
    description: str
    category: NodeCategory
    color: str
    inputs: List[NodeSlot] = field(default_factory=list)
    outputs: List[NodeSlot] = field(default_factory=list)
    properties: List[NodeProperty] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    maestro_usage_hint: str = ""

class NodeRegistry:
    """Registre central des nœuds disponibles"""
    
    def __init__(self):
        self._nodes: Dict[str, NodeDefinition] = {}
        self._register_builtin_nodes()
    
    def _register_builtin_nodes(self):
        """Enregistre tous les nœuds intégrés"""
        
        self.register_node(NodeDefinition(
            node_type="workflow/text_input",
            title="Entrée Texte",
            description="Point de départ du workflow, contient le texte d'entrée de l'utilisateur",
            category=NodeCategory.INPUT,
            color="#3a5",
            outputs=[
                NodeSlot("texte", "string", "Texte saisi par l'utilisateur")
            ],
            properties=[
                NodeProperty("value", "string", "Valeur par défaut", "", placeholder="Texte d'entrée")
            ],
            examples=[
                "Recevoir la demande initiale de l'utilisateur",
                "Stocker un prompt personnalisé"
            ],
            maestro_usage_hint="Utilisez ce nœud comme point de départ unique. Il recevra automatiquement la demande de l'utilisateur."
        ))
        
        self.register_node(NodeDefinition(
            node_type="workflow/llm_model", 
            title="Modèle LLM",
            description="Interroge un modèle de langage avec un prompt personnalisable pouvant accepter plusieurs entrées.",
            category=NodeCategory.PROCESSING,
            color="#a35",
            inputs=[
                NodeSlot("in_1", "string", "Première entrée de texte", required=False),
                NodeSlot("in_2", "string", "Deuxième entrée de texte", required=False),
                NodeSlot("in_3", "string", "Troisième entrée de texte", required=False),
                NodeSlot("in_4", "string", "Quatrième entrée de texte", required=False)
            ],
            outputs=[
                NodeSlot("résultat", "string", "Réponse générée par le LLM")
            ],
            properties=[
                NodeProperty("model", "string", "Modèle à utiliser", "{{SELECTED_MODEL}}", placeholder="{{SELECTED_MODEL}}"),
                NodeProperty("prompt", "string", "Template de prompt (utilisez {{in_1}}, {{in_2}}... pour les entrées)", "Contexte 1: {{in_1}}\n\nContexte 2: {{in_2}}", placeholder="Analyser ceci: {{in_1}} en vous basant sur cela: {{in_2}}")
            ],
            examples=[
                "Analyser un texte en se basant sur un autre",
                "Générer du contenu créatif à partir de plusieurs sources", 
                "Traduire un document en respectant un glossaire fourni en seconde entrée"
            ],
            maestro_usage_hint="Nœud principal multi-entrées. Personnalisez le prompt pour définir sa tâche. Utilisez les placeholders {{in_1}}, {{in_2}}, etc., pour injecter le contenu des différentes entrées dans votre prompt. Cela permet de donner plusieurs contextes distincts à l'agent."
        ))
        
        self.register_node(NodeDefinition(
            node_type="workflow/text_output",
            title="Sortie Texte", 
            description="Point de sortie du workflow, affiche le résultat final",
            category=NodeCategory.OUTPUT,
            color="#53a",
            inputs=[
                NodeSlot("texte", "string", "Texte à afficher")
            ],
            examples=[
                "Afficher le résultat final",
                "Présenter une partie spécifique du traitement"
            ],
            maestro_usage_hint="Utilisez pour définir ce qui sera affiché à l'utilisateur. Créez plusieurs nœuds de sortie pour organiser l'affichage."
        ))
        
        
        self.register_node(NodeDefinition(
            node_type="workflow/iterative_llm",
            title="LLM Itératif",
            description="Applique un LLM plusieurs fois de suite, chaque résultat devenant l'entrée du suivant",
            category=NodeCategory.PROCESSING,
            color="#a53",
            inputs=[
                NodeSlot("prompt initial", "string", "Texte de départ pour les itérations")
            ],
            outputs=[
                NodeSlot("résultat final", "string", "Résultat après toutes les itérations")
            ],
            properties=[
                NodeProperty("iterations", "int", "Nombre d'itérations", 3)
            ],
            examples=[
                "Affiner progressivement un texte",
                "Développer une idée par étapes",
                "Améliorer itérativement un contenu"
            ],
            maestro_usage_hint="Utilisez pour des tâches nécessitant un raffinement progressif ou un développement par étapes."
        ))

    def register_node(self, node_def: NodeDefinition):
        """Enregistre un nouveau type de nœud"""
        self._nodes[node_def.node_type] = node_def
    
    def get_node_definition(self, node_type: str) -> Optional[NodeDefinition]:
        """Récupère la définition d'un nœud"""
        return self._nodes.get(node_type)
    
    def get_all_nodes(self) -> Dict[str, NodeDefinition]:
        """Récupère tous les nœuds enregistrés"""
        return self._nodes.copy()
    
    def get_nodes_by_category(self, category: NodeCategory) -> Dict[str, NodeDefinition]:
        """Récupère tous les nœuds d'une catégorie donnée"""
        return {
            node_type: node_def 
            for node_type, node_def in self._nodes.items()
            if node_def.category == category
        }
    
    def generate_maestro_documentation(self) -> str:
        """Génère la documentation des nœuds pour le prompt Maestro"""
        doc = "**NŒUDS DISPONIBLES :**\n\n"
        
        for category in NodeCategory:
            category_nodes = self.get_nodes_by_category(category)
            if not category_nodes:
                continue
                
            doc += f"**{category.value.upper()} :**\n"
            for node_type, node_def in category_nodes.items():
                doc += f"- `{node_type}` : {node_def.description}\n"
                
                if node_def.inputs:
                    doc += f"  - Entrées : {', '.join(f'{slot.name} ({slot.type})' for slot in node_def.inputs)}\n"
                if node_def.outputs:
                    doc += f"  - Sorties : {', '.join(f'{slot.name} ({slot.type})' for slot in node_def.outputs)}\n"
                if node_def.properties:
                    props = [f"{prop.name}" for prop in node_def.properties if prop.name != "model"]
                    if props:
                        doc += f"  - Propriétés configurables : {', '.join(props)}\n"
                if node_def.maestro_usage_hint:
                    doc += f"  - Usage : {node_def.maestro_usage_hint}\n"
                doc += "\n"
        
        return doc
    
    def generate_interface_options(self) -> List[Dict[str, str]]:
        """Génère les options pour le sélecteur d'interface"""
        options = []
        for node_type, node_def in self._nodes.items():
            options.append({
                "value": node_type,
                "label": node_def.title,
                "category": node_def.category.value
            })
        return sorted(options, key=lambda x: (x["category"], x["label"]))
    
    def validate_workflow_structure(self, workflow_data: Dict[str, Any]) -> List[str]:
        """Valide la structure d'un workflow contre le registre"""
        errors = []
        
        if "nodes" not in workflow_data:
            errors.append("Le workflow doit contenir une clé 'nodes'")
            return errors
            
        for node in workflow_data["nodes"]:
            node_type = node.get("type")
            if not node_type:
                errors.append(f"Nœud {node.get('id', 'inconnu')} sans type")
                continue
                
            node_def = self.get_node_definition(node_type)
            if not node_def:
                errors.append(f"Type de nœud inconnu : {node_type}")
                continue
                
            node_properties = node.get("properties", {})
            for prop_def in node_def.properties:
                if prop_def.name not in node_properties and prop_def.default is None:
                    errors.append(f"Propriété manquante '{prop_def.name}' dans nœud {node_type}")
        
        return errors

NODE_REGISTRY = NodeRegistry()