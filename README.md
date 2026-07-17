# Personal Exploration Projects

This repository gathers a collection of projects dedicated to interacting with locally-running language models via Ollama. The main project, **`full_app_prototype`**, served as a matrix from which several specialized modules were derived. Each of these modules was developed independently in order to isolate, test, and refine a specific technology before its potential integration into the central application. The GBNF grammar file is an excerpt from my personal research on `system_prompts`, predating the emergence of the first reasoning models.

---

## M2 Master's Thesis — Philosophy of Science

**Title:** *The Third Mode of Genesis: Mechanism and Explanation in Large Language Models*  
**Institution:** University of Caen Normandy — UFR Humanities and Social Sciences  
**Degree:** Master II in Philosophy, Philosophy of Science track  
**Supervisor:** Pascal Bertin  
**Academic Year:** 2025–2026  
**Grade:** 18/20, with jury congratulations  
**External Audit:** Reviewed by Franck Varenne, engineer and Philosophy PhD specializing in AI and computer simulations  
**Length:** 109 pages

Large language models are at once highly capable and opaque, and their opacity is not a mere lack of access, since it persists even when the code, the parameters, and the full computational trace are available. This thesis takes as its object **mechanistic interpretability**, the research program that seeks to explain these models by reconstructing the internal causal mechanisms from which their outputs emerge. The guiding question is whether the strategies of mechanistic explanation inherited from the life sciences, in the sense of Machamer, Darden, and Craver, are adequate to such systems.

We defend a two-part thesis. On the one hand, these strategies yield explanations that are genuinely mechanistic in form, for they decompose the system, localize its functions, and establish its causal relations through intervention. On the other hand, their very success requires enriching the concepts of explanation, function, and component, because the organization of a trained model arises neither from evolution nor from design, but from a **third mode of genesis: training**. We finally show that this result reverses the initial question, since it challenges the tacit equivalence between mechanistically explaining a system and rendering it intelligible. In this respect, the approach constitutes a piece of **conceptual engineering**, understood as an adaptation of our concepts to a new object rather than as the correction of a defect.

*Keywords:* mechanistic interpretability · explainability · large language models · mechanistic explanation · epistemic opacity · function · understanding · conceptual engineering · intervention · causal abstraction

---

### M1 Research Thesis

**Title:** *Ontological Re-evaluation of LLM Agents and Artificial Intelligence*  
**Institution:** University of Caen Normandy  
**Length:** 94 pages

This research thesis explored how the emergence of new artificial intelligences leads us to reconsider our conception of life. It examined the ontological implications of LLM agents and their capacity to exhibit behaviors that challenge traditional boundaries between living and non-living systems.

---

## About `full_app_prototype`

This desktop software is designed to interact with local artificial intelligences. Its specificity lies in its ability to orchestrate teams of AI agents to solve multi-step problems. When a request proves too complex for a single response, an intelligent coordinator module, dubbed **Maestro**, takes over. Like a project manager, it analyzes the user's request, segments it into a series of distinct missions, and dynamically generates a complete work scheme. This plan connects different specialized agents, each with a precise role, and defines how information flows from one to another until final resolution. The system can even correct this plan autonomously if it detects inconsistencies. To ensure clear restitution, a final agent intervenes to synthesize and format all the results, thus delivering a unified and readable report. The graphical interface offers the possibility to visualize and modify these schemes on an interactive canvas, save custom configurations, and choose the language model to use.

## About `chat_and_rag`

This project is the first development module stemming from the main prototype. It takes the form of a desktop application allowing you to chat with local language models. Its central function is to enable asking questions about a personal document. For semantic search, the approach is more elaborate than simple keyword search. The language model is first used to extract the fundamental concepts of the question and their variations. Then, the program identifies in the document the areas where these terms are most relevant and concentrated. These passages are evaluated based on the diversity of concepts they contain and the proximity of terms. To avoid presenting redundant information, a Jaccard similarity filter retains only the most singular excerpts, which will form the final context of the response. The interface of this module was deliberately streamlined to focus on this mechanics.

## About `only_maestro_prototype`

This component is another technology brick derived from the main application. It was designed separately to perfect the generation of structured and complex responses. The objective is to develop a methodical approach to content creation. Instead of formulating a monolithic response, this module employs a "Maestro" who acts as an information architect. The process unfolds in two stages: the AI is first tasked with designing a detailed response plan, in the manner of a table of contents. Subsequently, this plan is automatically transformed into a multi-agent workflow, where each agent is assigned the drafting of a specific section. To guarantee the reliability of the process, the system incorporates robustness mechanisms, such as multiple attempts and an analysis logic to validate the generated plan. Particular attention was paid to the management of technical content, with support for rendering mathematical formulas thanks to LaTeX.

## About `transcription_prototype`

This third specialized module, also intended to be integrated into the main application, provides a complete processing chain from audio/video file transcription to the generation of professional documents. It relies on OpenAI's Whisper model, driven by a Python backend, with a web interface managed by pywebview. To handle large files, the module automatically segments long recordings into smaller chunks using FFmpeg. It is optimized to take advantage of NVIDIA graphics cards (CUDA) but remains functional on CPU. Once the raw transcription is obtained, a local language model intervenes to post-process the text, whether to embellish it, summarize it, or extract its main themes. Its strength lies in its ability to generate structured documents in LaTeX format, correcting common errors in the code generated by the AI before compiling it into a finalized PDF file.

## About `NebuAI_WebUI`

This older project, which is not a derivative of the main prototype, is the fruit of collaborative work and represents my first experience in interface creation. It is a local chat application designed to chat with language models via Ollama or the OpenAI API, relying on Python and the Dash library. Its main interest is to propose a framework for guiding and deepening the reasoning of the artificial intelligence before it provides its answer. To do so, the user can activate "reflection functions", such as "Chain of Thought" or "Socratic Questioning", prompting the model to analyze the question from different angles. To avoid cluttering the conversation, code blocks or tables are extracted and presented via clickable buttons, which open a dedicated viewer. The interface also allows you to query the content of a PDF document and visualize in detail the steps of the model's reasoning.
