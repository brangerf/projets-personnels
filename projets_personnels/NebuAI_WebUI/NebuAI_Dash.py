import os
import base64
import argparse

import diskcache
from dash import html, dcc, Input, Output, State, ALL, ctx
from dash.long_callback import DiskcacheLongCallbackManager
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash_extensions.enrich import DashProxy, MultiplexerTransform

from answers_logic import classic_answer, rag_answer
from llms import initialize
from split_markdown import split_markdown_by_blocks
from html_components import (
    create_answer_divs,
    create_indy_component,
    generate_reflexion_button,
    doc_llm_switch,
    update_indy_div,
    MAIN_LAYOUT,
)


def parse_arguments():
    parser = argparse.ArgumentParser(description="NebuAI")
    parser.add_argument(
        "--inference_mode",
        type=str,
        choices=["ollama", "openai", "llamacpp", "mock"],
        default="ollama",
        help="Set the inference mode. Default is 'ollama'.",
    )
    parser.add_argument(
        "--default_model",
        type=str,
        default=None,
        help="Set the default model. Default is None.",
    )
    return parser.parse_args()


def initialize_engine(args):
    return initialize(
        inference_mode=args.inference_mode,
        default_model=args.default_model,
    )


def setup_app(long_callback_manager):
    return DashProxy(
        external_stylesheets=[
            "assets/style.css",
            dbc.themes.DARKLY,
            dbc.icons.FONT_AWESOME,
        ],
        title="NebuAI",
        long_callback_manager=long_callback_manager,
        transforms=[MultiplexerTransform()],
    )


def create_callbacks(app, engine, model_names):
    @app.callback(
        [Output("models-select", "options"), Output("models-select", "value")],
        Input("main-layout", "id"),
    )
    def update_available_models(_):
        options = [{"label": model, "id": model} for model in model_names]
        return options, engine.model

    @app.callback(
        Output("conversation-history", "data"),
        Output("user-message-input", "value"),
        Input("send-message-button", "n_clicks"),
        Input("reinit-button", "n_clicks"),
        Input("user-message-input", "n_submit"),
        State("user-message-input", "value"),
        State("conversation-history", "data"),
        prevent_initial_call=True,
    )
    def send_message(
        send_clicks, reinit_clicks, submit_clicks, message, conversation_history
    ):
        if conversation_history is None:
            conversation_history = []
        if ctx.triggered_id in ["send-message-button", "user-message-input"]:
            if message:
                conversation_history.append({"role": "user", "content": message})
            return conversation_history, ""
        elif ctx.triggered_id == "reinit-button":
            return [], ""
        return conversation_history, message

    @app.callback(
        Output("chat-window", "children"),
        Output("indy-storage", "data"),
        Output("number-of-indy-elements", "data"),
        Output("has-new-indy", "data"),
        Input("conversation-history", "data"),
        State("indy-storage", "data"),
        State("number-of-indy-elements", "data"),
        prevent_initial_call=True,
    )
    def update_display(conversation_data, indy_storage, num_indy_elements):
        if not indy_storage:
            indy_storage = {"stored_markdowns": [], "markdown_elements": []}
        divs = []
        for i, turn in enumerate(conversation_data):
            color = "#3498db" if turn["role"] == "user" else "rgb(182, 189, 194)"
            markdown_elements = split_markdown_by_blocks(turn["content"])
            answer_divs = create_answer_divs(i, markdown_elements, color, indy_storage)
            divs.append(
                html.Div(
                    [
                        html.Div(answer_divs, className="d-flex flex-column"),
                        html.Hr(style={"opacity": 0.1}),
                    ],
                    className="d-flex flex-column",
                )
            )
        new_num_indy_elements = len(indy_storage["markdown_elements"])
        has_new_indy = new_num_indy_elements > num_indy_elements
        return divs, indy_storage, new_num_indy_elements, has_new_indy

    @app.callback(
        Output("indy-div", "children"),
        Input("indy-storage", "data"),
        Input("indy-current-i", "data"),
        prevent_initial_call=True,
    )
    def update_indy(indy_storage, current_indy_div):
        if not indy_storage:
            indy_storage = {"stored_markdowns": [], "markdown_elements": []}
        divs = [
            create_indy_component(i, md_content)
            for i, md_content in enumerate(indy_storage["markdown_elements"])
        ]
        if not divs:
            current_indy_div = 0
        return update_indy_div(divs, current_indy_div)

    @app.callback(
        Output("indy-current-i", "data"),
        [
            Input("next-indy-button", "n_clicks"),
            Input("previous-indy-button", "n_clicks"),
        ],
        State("indy-current-i", "data"),
        prevent_initial_call=True,
    )
    def update_indy_current_i(next_clicks, previous_clicks, current_i):
        if ctx.triggered_id == "next-indy-button":
            return current_i + 1
        elif ctx.triggered_id == "previous-indy-button":
            return max(current_i - 1, 0)
        else:
            raise PreventUpdate

    @app.callback(
        Output("Indy-tab", "tab_style"),
        Input("has-new-indy", "data"),
    )
    def update_indy_tab_style(has_new_indy):
        return {"color": "yellow"} if has_new_indy else {"color": "white"}

    @app.callback(
        Output("has-new-indy", "data"),
        Input("details-tabs", "active_tab"),
        prevent_initial_call=True,
    )
    def reset_has_new_indy(active_tab):
        if active_tab == "Indy-tab":
            return False
        else:
            raise PreventUpdate

    @app.callback(
        Output("details-tabs", "active_tab"),
        Input({"type": "indy-button", "target": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def update_currently_shown_indy(clicked_buttons):
        if any(clicked_buttons):
            return "Indy-tab"
        else:
            raise PreventUpdate

    @app.callback(
        Output("store-file-path", "data"),
        Input("upload-file", "contents"),
        State("upload-file", "filename"),
    )
    def upload_file(contents, filename):
        if contents is not None:
            file_path = save_uploaded_file(contents, filename)
            return os.path.basename(file_path)
        return None

    @app.callback(
        Output("conversation-history", "data", allow_duplicate=True),
        Output("reflection-results", "data"),
        Input("conversation-history", "data"),
        State("models-select", "value"),
        State("activated-reflexion-functions", "data"),
        State("store-file-path", "data"),
        State("use-rag", "value"),
        prevent_initial_call=True,
        background=True,
    )
    def generate_response(
        chat_data,
        model,
        activated_functions,
        uploaded_file,
        use_rag,
    ):
        if not chat_data or chat_data[-1]["role"] != "user":
            raise PreventUpdate
        engine.model = model
        engine.set_prices(0, 0)
        response, reflexion_answers = get_model_response(
            chat_data, engine, activated_functions, uploaded_file, use_rag
        )
        chat_data.append({"role": "assistant", "content": response})
        return chat_data, reflexion_answers

    @app.callback(
        Output("reflexion-buttons", "children"),
        Input("activated-reflexion-functions", "data"),
        prevent_initial_call=True,
    )
    def update_reflexion_buttons_style(reflexion_functions_data):
        return [
            generate_reflexion_button(func, activated)
            for func, activated in reflexion_functions_data.items()
        ]

    @app.callback(
        Output("activated-reflexion-functions", "data"),
        Input({"type": "reflexion_function", "id": ALL}, "n_clicks"),
        State("activated-reflexion-functions", "data"),
        prevent_initial_call=True,
    )
    def update_activation(reflexion_function_clicks, activated_functions):
        func_id = ctx.triggered_id["id"]
        activated_functions[func_id] = not activated_functions[func_id]
        return activated_functions

    @app.callback(
        Output("reflexion-results-div", "children"),
        Input("reflection-results", "data"),
        prevent_initial_call=True,
    )
    def update_details_div(reflection_results):
        if not reflection_results:
            return html.Div(
                "No reflection performed yet.",
                style={
                    "color": "#008F11",
                    "background": "#0d1117",
                    "font-family": "'Courier New', monospace",
                },
            )
        return html.Div(
            [create_reflection_div(result) for result in reflection_results]
        )

    @app.callback(
        [
            Output("docllm-stored-file", "children"),
            Output("docllm-stored-file", "style"),
        ],
        Input("store-file-path", "data"),
        prevent_initial_call=True,
    )
    def update_stored_file(stored_file):
        if not stored_file:
            return html.Div([doc_llm_switch, html.Div("No stored file")]), {
                "opacity": 0,
                "display": "none",
            }
        return (
            html.Div(
                [
                    doc_llm_switch,
                    html.Div(
                        [
                            html.Div(className="radial-gradient-button"),
                            html.Div(stored_file),
                        ],
                        className="d-flex flex-row gap-1",
                    ),
                ],
                className="d-flex flex-row gap-1 justify-content-between",
            ),
            {"opacity": 1},
        )


def save_uploaded_file(contents, filename):
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, "wb") as f:
        f.write(decoded)
    return file_path


def get_model_response(chat_data, engine, activated_functions, uploaded_file, use_rag):
    if not uploaded_file or not use_rag:
        return classic_answer(chat_data, engine, activated_functions)
    else:
        response = rag_answer(chat_data, engine, f"uploads/{uploaded_file}")
        return response, []


def create_reflection_div(result):
    return html.Div(
        [
            html.H4(
                result["function"],
                className="mb-2",
                style={
                    "color": "white",
                    "background": "#0d1117",
                    "font-family": "'Courier New', monospace",
                },
            ),
            dcc.Markdown(
                result["response"],
                className="mb-4",
                style={
                    "color": "#008F11",
                    "background": "#0d1117",
                    "font-family": "'Courier New', monospace",
                },
            ),
            html.Hr(),
        ]
    )


def main():
    args = parse_arguments()
    engine, model_names = initialize_engine(args)

    # Diskcache setup
    cache = diskcache.Cache("./cache")
    long_callback_manager = DiskcacheLongCallbackManager(cache)

    app = setup_app(long_callback_manager)
    app.layout = html.Div(
        [
            MAIN_LAYOUT,
            dcc.Store(id="has-new-indy", data=False),
            dcc.Store(id="number-of-indy-elements", data=0),
        ]
    )

    create_callbacks(app, engine, model_names)

    if __name__ == "__main__":
        app.run_server(debug=True)


main()
