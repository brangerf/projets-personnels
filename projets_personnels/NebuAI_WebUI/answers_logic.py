# Classic answering with reflexion functions
from copy import copy
from typing import Callable
from doc_llm.documents.document import Document
import datetime
import pytz

timezone = pytz.timezone('Europe/Paris')
date = datetime.datetime.now(timezone)


REFLEXION_FUNCTIONS_MAPPPING = {
    "Program of Thoughts": """Analysez la requête suivante : '{context}'
1. Décomposez le problème en sous-tâches spécifiques.
2. Pour chaque sous-tâche, élaborez un plan d'action détaillé.
3. Identifiez les connaissances ou ressources nécessaires pour chaque étape.
4. Anticipez les difficultés potentielles et proposez des solutions.
5. Synthétisez vos réflexions en un 'programme' de pensées cohérent.""",
    "Plan to Solve": """Basez-vous sur ce contexte : {context}
Utilisez maintenant la méthode Plan-to-Solve pour élaborer un plan détaillé et efficace pour résoudre le problème. Concentrez-vous uniquement sur la création d'un plan structuré et exhaustif. ATTENTION : L'UTILISATEUR N'A PAS ACCES A INTERNET ET N'A ACCES A AUCUNE RESSOURCE DOCUMENTAIRE.""",
    "Self Refine": """
Basez-vous sur ce contexte : {context}
1. Identifiez les points faibles ou les lacunes dans le raisonnement précédent.
2. Proposez des améliorations ou des alternatives pour chaque point identifié.
3. Ré-évaluez la cohérence globale de la réponse après ces modifications.
4. Affinez la formulation pour plus de clarté et de précision.""",
    "Analogical": """Examinez le problème suivant : {context}
1. Identifiez les caractéristiques essentielles du problème.
2. Cherchez des situations ou domaines analogues présentant des caractéristiques similaires.
3. Analysez comment ces analogies peuvent éclairer le problème actuel.
4. Adaptez les solutions ou approches des situations analogues au problème présent.""",
    "Metacognitive": """
Réfléchissez sur votre processus de pensée concernant : {context}
1. Évaluez l'efficacité de vos stratégies de résolution de problèmes.
2. Identifiez vos biais potentiels ou vos angles morts dans votre raisonnement.
3. Considérez comment vous pourriez améliorer votre approche pour des problèmes similaires à l'avenir.
4. Formulez des principes généraux que vous avez appris de cette expérience.""",
    "Chain of Thought": """Basez-vous sur ce contexte : {context}
Utilisez le raisonnement en chaîne de pensée pour résoudre ce problème :
1. Décomposez le problème en étapes logiques.
2. Pour chaque étape, expliquez votre raisonnement en détail.
3. Utilisez des marqueurs clairs pour chaque étape (par exemple, [Étape 1], [Étape 2], etc.).
4. Après chaque étape, réfléchissez sur la validité de votre raisonnement.
5. Si vous identifiez des erreurs, corrigez-les et expliquez pourquoi.
6. Concluez avec une synthèse de votre raisonnement et la solution finale.""",
    "Socratic Questioning": """Analysez la situation suivante en utilisant la méthode socratique : {context}
1. Posez une série de questions profondes et réfléchies sur le sujet.
2. Pour chaque question, fournissez une réponse réfléchie.
3. Utilisez ces questions pour explorer les hypothèses sous-jacentes, les implications et les preuves.
4. Continuez à approfondir avec des questions de suivi basées sur les réponses.
5. Concluez avec les insights clés obtenus grâce à ce processus de questionnement.""",
    "System Dynamics": """Créez un modèle de dynamique des systèmes pour analyser la situation suivante : {context}
1. Identifiez les principaux éléments ou variables du système.
2. Décrivez les relations et les boucles de rétroaction entre ces éléments.
3. Pour chaque relation importante :
    a) Expliquez la nature de la relation (positive ou négative).
    b) Décrivez comment un changement dans un élément affecte les autres.
4. Identifiez les boucles de rétroaction de renforcement et d'équilibrage dans le système.
5. Analysez les délais potentiels et leurs impacts sur le comportement du système.
6. Discutez des points de levier potentiels où des interventions pourraient avoir un impact significatif.
7. Prédisez le comportement probable du système au fil du temps, en tenant compte des interactions complexes.
8. Proposez des stratégies pour gérer ou modifier le système en fonction de votre analyse.""",
}


def classic_answer(chat_data, engine, activated_reflexion_functions: dict[str, bool]):
    context = ""
    if chat_data:
        for i, turn in enumerate(chat_data):
            letter = "Question: " if not i % 2 else "Answer: "
            context += f"{letter}{turn['content']}\n"
        user_input = chat_data[-1]["content"]

    reflexion_answers: list[dict] = []
    for reflexion_function, activated in activated_reflexion_functions.items():
        if not activated:
            continue
        prompt = copy(REFLEXION_FUNCTIONS_MAPPPING[reflexion_function]).replace(
            "{context}", context
        )
        print(f"==== ANSWERING WITH {reflexion_function} ====")
        response = engine.chat(chat_data + [{"role": "user", "content": prompt}])
        reflexion_answers.append({"function": reflexion_function, "response": response})
        context = response

    reflexion_answers_final = "\n".join(
        [
            f"Raisonnement '{answer['function']}': {answer['response']}"
            for answer in reflexion_answers
        ]
    )
    final_prompt = f"""Nous sommes le {date}. D'après le contexte de la conversation, répondez à la requête de l'utilisateur suivante : {user_input}.
Servez-vous de vos éventuelles réflexions personnelles ({reflexion_answers_final}) comme point d'appui, sans le recopier, pour fournir une réponse naturelle, complète et cohérente."""
    response = engine.chat(chat_data + [{"role": "user", "content": final_prompt}])
    return response, reflexion_answers


def rag_answer(chat_data, engine, document_path) -> str:
    context = ""
    if chat_data:
        for i, turn in enumerate(chat_data):
            letter = "Question: " if not i % 2 else "Answer: "
            context += f"{letter}{turn['content']}\n"
        user_input = chat_data[-1]["content"]
    else:
        return "<error> no chat data </error>"

    if document_path.split(".")[-1].lower() != "pdf":
        return "The document must be a pdf."
    document = Document(document_path)
    answer = document.query(engine, user_input)
    return answer.content
