import dash_bootstrap_components as dbc

from dash import html, dcc, Input, Output, State, callback, MATCH, ALL, ctx
from dash.exceptions import PreventUpdate
from dash.long_callback import DiskcacheLongCallbackManager
from dash_resizable_panels import PanelGroup, Panel, PanelResizeHandle

from constants import REFLEXION_FUNCTIONS


def update_indy_div(markdown_elements: list[dcc.Markdown], i: int) -> html.Div:
    """
    Displays the ith Indy
    """
    l_opacity = 0.2 if not i else 1
    r_opacity = 0.2 if i + 1 == len(markdown_elements) else 1
    if not markdown_elements:
        markdown_elements = [dcc.Markdown("No Indy yet.")]
    return html.Div(
        [
            html.Div(
                [
                    html.I(
                        className="fas fa-arrow-left fs-5 button",
                        id="previous-indy-button",
                        style={"opacity": l_opacity, "flex-shrink": 0},
                    ),
                    html.Div(
                        markdown_elements[i],
                        style={
                            "flex-grow": 1,
                            "overflow-x": "auto",
                            "min-width": 0,
                            "max-width": "calc(100% - 60px)",
                        },
                    ),
                    html.I(
                        className="fas fa-arrow-right fs-5 button",
                        id="next-indy-button",
                        style={"opacity": r_opacity, "flex-shrink": 0},
                    ),
                ],
                className="d-flex flex-row gap-2 justify-content-between align-items-center",
                style={"width": "100%"},
            ),
            html.Div(f"({i+1}/{len(markdown_elements)})"),
        ],
        className="d-flex flex-column gap-1 justify-content-between align-items-center",
        style={"width": "100%", "height": "100%"},
    )


def generate_reflexion_button(
    reflexion_function_name: str, activated: bool = False
) -> html.Div:
    color = "#161b22"
    if activated:
        color = "green"
    return html.Div(
        reflexion_function_name,
        className="p-1 ms-2 me-2 border border-secondary rounded button",
        style={"background-color": color, "font-family": "'Courier New', monospace"},
        id={"type": "reflexion_function", "id": reflexion_function_name},
    )


reflexion_buttons = html.Div(
    [generate_reflexion_button(func) for func in REFLEXION_FUNCTIONS],
    className="d-flex flex-column gap-2",
    id="reflexion-buttons",
)

reflexion_div = html.Div(
    [
        html.Div(
            "Fonctions de réflexion",
            className="p-3 fs-4 mb-1 fw-bolder lh-sm",
            style={"font-family": "'Courier New', monospace"},
        ),
        reflexion_buttons,
    ],
    className="d-flex flex-column gap-1 border border-solid border-secondary p-2 m-2 rounded",
    style={"width": "inherit", "height": "90vh"},
)

chat = html.Div(
    [],
    style={"width": "100%", "height": "80vw", "overflow-y": "scroll"},
    id="chat-window",
    className="p-2",
)

prompt_input = dbc.Textarea(
    placeholder="Tapez votre message ici...",
    className="border border-secondary",
    style={"background-color": "#161b22", "color": "#c9d1d9", "height": "1rem"},
    id="user-message-input",
)
# models_select = dbc.Select(
#     options=[{"label": model, "id": model} for model in model_names],
#     value=engine.model,
#     className="border border-secondary",
#     style={"background-color": "#161b22", "width": "30%", "color": "#c9d1d9"},
#     id="models-select",
# )


def create_indy_button(i, j, md_content, md_type, indy_storage):
    indy_id = f"t{i}m{j}"
    if indy_id not in indy_storage["stored_markdowns"]:
        indy_storage["stored_markdowns"].append(indy_id)
        indy_storage["markdown_elements"].append(md_content)
    icon = "fas fa-table" if md_type["type"] == "table" else "fas fa-code"
    return dbc.Button(
        html.Div(
            [
                html.I(className=icon),
                dcc.Markdown(f"**Open your {md_type['type']} Indy**"),
            ],
        ),
        style={"width": "30%"},
        className="d-flex flex-column border",
        color="dark",
        id={"type": "indy-button", "target": indy_id},
    )


def create_answer_divs(i, markdown_elements, color, indy_storage):
    answer_divs = []
    for j, (md_content, md_type) in enumerate(markdown_elements):
        element_id = {"turn": i, "markdown_id": j}
        md_style = {
            "color": color,
            "background": "#0d1117",
            "font-family": "'Courier New', monospace",
        }
        answer_element = dcc.Markdown(md_content, style=md_style, id=element_id)

        if md_type["type"] in ["code", "table"]:
            answer_element = create_indy_button(i, j, md_content, md_type, indy_storage)
        elif md_type["type"] == "short_code":
            answer_element = html.Div(
                [
                    dcc.Clipboard(
                        target_id=element_id,
                        style={"position": "relative", "left": "98%", "top": "2rem"},
                    ),
                    answer_element,
                ]
            )
        answer_divs.append(answer_element)
    return answer_divs


def create_indy_component(i, markdown_element):
    markdown_html = dcc.Markdown(
        markdown_element,
        className="p-2",
        style={
            "color": "white",
            "background": "#0d1117",
            "font-family": "'Courier New', monospace",
            "white-space": "pre-wrap",
            "word-wrap": "break-word",
            "overflow-x": "auto",
            "width": "100%",
        },
        id={"indy-id": i},
    )
    return html.Div(
        [
            dcc.Clipboard(
                target_id={"indy-id": i},
                style={"position": "absolute", "right": "5px", "top": "5px"},
            ),
            markdown_html,
        ],
        className="d-flex justify-content-center",
        style={"position": "relative", "width": "100%"},
    )


models_select = dbc.Select(
    options=[{"label": model, "id": model} for model in []],
    value=None,
    className="border border-secondary",
    style={"background-color": "#161b22", "width": "30%", "color": "#c9d1d9"},
    id="models-select",
)
file_icon = html.I(className="fas fa-file-upload button", style={"font-size": "1.5rem"})

bottom_bar = html.Div(
    [
        models_select,
        dcc.Upload(file_icon, id="upload-file"),
        prompt_input,
        dbc.Button("Envoyer", color="success", id="send-message-button"),
        dbc.Button("Réinitialiser", color="danger", id="reinit-button"),
    ],
    className="d-flex flex-row gap-2 justify-content-center align-items-center",
)

doc_llm_switch = dbc.Checklist(
    options=[
        {"label": "RAG", "value": 1},
    ],
    value=[1],
    id="use-rag",
    switch=True,
)

bottom_bar_with_file_indication = html.Div(
    [
        bottom_bar,
        html.Div(
            [doc_llm_switch],
            id="docllm-stored-file",
            style={"opacity": 0, "display": "none"},
        ),
    ],
    className="d-flex flex-column gap-1",
)
main_window_div = html.Div(
    [chat, html.Hr(), bottom_bar_with_file_indication],
    className="d-flex flex-column border border-solid border-secondary p-3 m-2 rounded",
    style={"width": "inherit", "height": "90vh", "flex-grow": "2"},
)


reflexion_results_div = html.Div(
    id="reflexion-results-div",
    className="d-flex flex-column pt-1",
    style={"max-width": "28vw"},
)

indy_div = html.Div(children=update_indy_div([], 0), id="indy-div")

details_div = html.Div(
    children=dbc.Tabs(
        [
            dbc.Tab(reflexion_results_div, label="Reflexions", tab_id="Reflexions-tab"),
            dbc.Tab(indy_div, label="Indy", tab_id="Indy-tab", id="Indy-tab"),
            dbc.Tab(
                ["Souvenirs: Pas encore implémenté"],
                label="Souvenirs",
                tab_id="Memory-tabs",
            ),
        ],
        id="details-tabs",
    ),
    className="border border-solid border-secondary p-3 m-2 rounded",
    style={
        "width": "100%",
        "height": "90vh",
        "display": "flex",
        "flexDirection": "column",
    },
)

handle = PanelResizeHandle(
    html.Div(
        html.Div(
            style={
                "height": "100%",
                "border-right": "#807c7685 dashed 1px",
            },
            className="d-flex flex-row justify-content-center align-items-center",
        ),
        style={
            "width": "0.25rem",
            "height": "100%",
        },
        className="d-flex flex-row justify-content-center align-items-center",
    )
)
panel = html.Div(
    [
        PanelGroup(
            children=[
                Panel(reflexion_div, defaultSizePercentage=15),
                handle,
                Panel(main_window_div, defaultSizePercentage=60),
                handle,
                Panel(
                    details_div,
                    defaultSizePercentage=25,
                    # style={"overflow": "clip"},
                ),
            ],
            id="panel-group",
            direction="horizontal",
            style={"width": "98vw"},
        ),
    ],
    className="d-flex flex-row justify-content-center align-items-center",
)

MAIN_LAYOUT = html.Div(
    [
        html.Div(
            "NebuAI",
            className="d-flex justify-content-center align-items-center mt-1 fs-1",
            style={
                "font-family": "'Courier New', monospace",
                "letter-spacing": ".5rem",
            },
        ),
        html.Div(
            [
                dcc.Store(id="conversation-history", data=[]),
                dcc.Store(
                    id="activated-reflexion-functions",
                    data={func: False for func in REFLEXION_FUNCTIONS},
                ),
                dcc.Store(
                    id="reflection-results", data=[]
                ),  # New store for reflection results
                dcc.Store(
                    data={"markdown_elements": [], "stored_markdowns": []},
                    id="indy-storage",
                ),
                dcc.Store(id="store-file-path"),
                dcc.Store(id="indy-current-i", data=0),
                dcc.Interval(
                    id="stream-update-interval",
                    interval=100,
                    n_intervals=0,
                    disabled=True,
                ),
                panel,
                html.Div(id="placeholder"),
            ]
        ),
    ],
    className="d-flex flex-column gap-0",
    style={"background-color": "#0d1117", "height": "100vh"},
    id="main-layout",
)
