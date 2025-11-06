# projets-personnels

A propos de chat_and_rag :

Ce projet est une application de bureau qui permet de chatter avec des modèles de langage locaux via Ollama. Je l'ai construit en utilisant Python pour la logique principale et une interface utilisateur en HTML et JavaScript, le tout unifié dans une fenêtre grâce à pywebview.
La fonctionnalité principale est de pouvoir poser des questions sur un document personnel. Pour la recherche sémantique, l'approche est un peu plus élaborée. Plutôt que de chercher les mots exacts de la question, j'utilise d'abord le modèle de langage pour extraire les concepts clés et leurs variations. Ensuite, le programme recherche ces termes dans le document et identifie les zones où ils sont les plus pertinents et concentrés. Ces passages sont évalués selon plusieurs critères, notamment la diversité des concepts qu'ils contiennent et la proximité des termes entre eux. Pour éviter de présenter des informations redondantes, un filtre de similarité Jaccard est appliqué pour ne retenir que les extraits les plus uniques, qui formeront le contexte final de la réponse.
L'interface permet aussi de régler quelques paramètres du modèle, comme la température ou la taille du contexte, et de modifier le prompt système pour ajuster le comportement de l'assistant.
