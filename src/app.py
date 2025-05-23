import queue
import threading
import asyncio
from loguru import logger

from agency_swarm import Agency
from agency_swarm.util.files import get_file_purpose, get_tools
from agency_swarm.util.streaming import create_gradio_handler
from agency_swarm.tools import CodeInterpreter, FileSearch

from study_buddy.main import agency
from study_buddy.main import bubble_bot


def demo_gradio(agency: Agency, height=550, dark_mode=True, **kwargs):
    """
    Launches a Gradio-based demo interface for the agency chatbot.

    Parameters:
        height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 450.
        dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
        **kwargs: Additional keyword arguments to be passed to the Gradio interface.
    This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
    """

    try:
        import gradio as gr
    except ImportError:
        raise Exception("Please install gradio: pip install gradio")

    js = """function () {
            gradioURL = window.location.href
            if (!gradioURL.endsWith('?__theme={theme}')) {
                window.location.replace(gradioURL + '?__theme={theme}');
            }
        }"""

    if dark_mode:
        js = js.replace("{theme}", "dark")
    else:
        js = js.replace("{theme}", "light")

    attachments = []
    images = []
    message_file_names = None
    uploading_files = False
    studybuddy_agent = agency.main_recipients[0]

    chatbot_queue = queue.Queue()
    gradio_handler_class = create_gradio_handler(chatbot_queue=chatbot_queue)

    with gr.Blocks(
        js=js,
        css="""
    .chat-input-row {position: fixed; bottom: 0; left: 0; right: 0; background: #18181a; z-index: 100; padding: 0 0 24px 0; border: none; box-shadow: 0 -2px 16px rgba(0,0,0,0.12);}
    .chatbot-main {height: 70vh !important; min-height: 400px; max-height: 80vh; border: none !important; box-shadow: none !important; background: transparent;}
    .bubble-row-top {margin-bottom: 8px; justify-content: center; display: flex; gap: 16px;}
    .welcome-center {display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center;}
    .welcome-title {font-size: 2.5rem; font-weight: 700; margin-bottom: 24px; color: #fff;}
    .bubble-btn {min-width: 180px; margin: 0 8px; border-radius: 18px; background: #23272f; color: #fff; border: none; padding: 16px 24px; font-size: 1.1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: background 0.2s; display: none;}
    .bubble-btn.visible {display: inline-block;}
    .bubble-btn:hover {background: #343a46;}
    .gradio-container {background: #18181a !important;}
    .input-box-modern {border-radius: 16px; background: #23272f; border: 1px solid #343a46; color: #fff; font-size: 1.1rem; padding: 16px;}
    .file-upload-modern {background: transparent; border: none; color: #fff; min-width: 0;}
    #send-btn {height: 40px; border-radius: 12px; font-size: 1.1rem; margin-left: 8px; min-width: 80px; background: #6c47ff; color: #fff; border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: background 0.2s;}
    #send-btn:hover {background: #5436c7;}
    """,
    ) as demo:
        bubbles_state = gr.State([])

        # Welcome message and bubbles (shown only if no chat history)
        with gr.Column(visible=True, elem_classes="welcome-center") as welcome_col:
            gr.Markdown("<div class='welcome-title'>What can I help with?</div>")
            with gr.Row(elem_classes="bubble-row-top", equal_height=True):
                bubble_btns = [
                    gr.Button(visible=False, elem_classes="bubble-btn", scale=1)
                    for _ in range(4)
                ]

        chatbot = gr.Chatbot(
            height=None,
            type="tuples",
            elem_classes="chatbot-main",
            show_label=False,
            show_copy_button=False,
        )

        with gr.Row(elem_classes="chat-input-row", equal_height=True):
            with gr.Column(scale=8):
                msg = gr.Textbox(
                    placeholder="Ask anything",
                    lines=1,
                    max_lines=4,
                    label=None,
                    elem_classes="input-box-modern",
                )
            with gr.Column(scale=2, min_width=80):
                file_upload = gr.Files(
                    label=None,
                    type="filepath",
                    height=36,
                    elem_classes="file-upload-modern",
                )
            with gr.Column(scale=2, min_width=80):
                button = gr.Button(value="Send", variant="primary", elem_id="send-btn")

        def update_bubble_buttons(bubbles):
            updates = []
            for i, btn in enumerate(bubble_btns):
                if i < len(bubbles) and bubbles[i]:
                    updates.append(
                        gr.update(
                            value=bubbles[i],
                            visible=True,
                            elem_classes="bubble-btn visible",
                        )
                    )
                else:
                    updates.append(gr.update(visible=False, elem_classes="bubble-btn"))
            return updates

        def handle_file_upload(file_list):
            nonlocal attachments
            nonlocal message_file_names
            nonlocal uploading_files
            nonlocal images
            uploading_files = True
            attachments = []
            message_file_names = []
            if file_list:
                try:
                    for file_obj in file_list:
                        purpose = get_file_purpose(file_obj.name)

                        with open(file_obj.name, "rb") as f:
                            # Upload the file to OpenAI
                            file = agency.main_thread.client.files.create(
                                file=f, purpose=purpose
                            )

                        if purpose == "vision":
                            images.append(
                                {
                                    "type": "image_file",
                                    "image_file": {"file_id": file.id},
                                }
                            )
                        else:
                            attachments.append(
                                {
                                    "file_id": file.id,
                                    "tools": get_tools(file.filename),
                                }
                            )

                        message_file_names.append(file.filename)
                        logger.info(f"Uploaded file ID: {file.id}")
                    return attachments
                except Exception as e:
                    logger.error(f"Error: {e}", exc_info=True)
                    return str(e)
                finally:
                    uploading_files = False

            uploading_files = False
            return "No files uploaded"

        def user(user_message, history):
            if not user_message.strip():
                return user_message, history

            nonlocal message_file_names
            nonlocal uploading_files
            nonlocal images
            nonlocal attachments

            # Check if attachments contain file search or code interpreter types
            def check_and_add_tools_in_attachments(attachments, agent):
                for attachment in attachments:
                    for tool in attachment.get("tools", []):
                        if tool["type"] == "file_search":
                            if not any(isinstance(t, FileSearch) for t in agent.tools):
                                # Add FileSearch tool if it does not exist
                                agent.tools.append(FileSearch)
                                agent.client.beta.assistants.update(
                                    agent.id,
                                    tools=agent.get_oai_tools(),
                                )
                                logger.info(
                                    "Added FileSearch tool to agent to analyze the file."
                                )
                        elif tool["type"] == "code_interpreter":
                            if not any(
                                isinstance(t, CodeInterpreter) for t in agent.tools
                            ):
                                # Add CodeInterpreter tool if it does not exist
                                agent.tools.append(CodeInterpreter)
                                agent.client.beta.assistants.update(
                                    agent.id,
                                    tools=agent.get_oai_tools(),
                                )
                                logger.info(
                                    "Added CodeInterpreter tool to agent to analyze the file."
                                )
                return None

            check_and_add_tools_in_attachments(attachments, studybuddy_agent)

            if history is None:
                history = []

            original_user_message = user_message

            # Append the user message with a placeholder for bot response
            user_message = f"👤 User 🗣️ @studybuddy:\n" + user_message.strip()

            if message_file_names:
                user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

            return original_user_message, history + [[user_message, None]]

        def bot(original_message, history, bubbles):
            nonlocal attachments
            nonlocal message_file_names
            nonlocal images
            nonlocal uploading_files

            if not original_message:
                return (
                    "",
                    history,
                    bubbles,
                    *update_bubble_buttons(bubbles),
                )

            if uploading_files:
                history.append([None, "Uploading files... Please wait."])
                yield (
                    "",
                    history,
                    bubbles,
                    *update_bubble_buttons(bubbles),
                )
                return (
                    "",
                    history,
                    bubbles,
                    *update_bubble_buttons(bubbles),
                )

            logger.info(f"Message files: {attachments}")
            logger.info(f"Images: {images}")

            if images and len(images) > 0:
                original_message = [
                    {
                        "type": "text",
                        "text": original_message,
                    },
                    *images,
                ]

            completion_thread = threading.Thread(
                target=agency.get_completion_stream,
                args=(
                    original_message,
                    gradio_handler_class,
                    [],
                    studybuddy_agent,
                    "",
                    attachments,
                    None,
                ),
            )
            completion_thread.start()

            attachments = []
            message_file_names = []
            images = []
            uploading_files = False

            new_message = True
            current_bubbles = bubbles.copy() if bubbles else []
            while True:
                try:
                    bot_message = chatbot_queue.get(block=True)

                    # Handle bubble suggestion event
                    if (
                        isinstance(bot_message, dict)
                        and bot_message.get("type") == "bubble_suggestions"
                    ):
                        current_bubbles = bot_message.get("bubbles", [])[:4]
                        yield (
                            "",
                            history,
                            current_bubbles,
                            *update_bubble_buttons(current_bubbles),
                        )
                        continue

                    if bot_message == "[end]":
                        completion_thread.join()
                        # At the end of the stream, call bubble_bot to generate suggestions
                        # Gather conversation history and last agent message
                        conversation_history = []
                        last_agent_message = ""
                        for pair in history:
                            if pair[0]:
                                conversation_history.append(pair[0])
                            if pair[1]:
                                conversation_history.append(pair[1])
                        # Find the last non-empty agent (bot) message
                        for pair in reversed(history):
                            if pair[1]:
                                last_agent_message = pair[1]
                                break
                        try:
                            result = bubble_bot.generate_bubbles(
                                last_study_buddy_message=last_agent_message,
                                conversation_history=conversation_history,
                            )
                            bubbles_out = (
                                result["suggested_bubbles"][:4]
                                if result and "suggested_bubbles" in result
                                else []
                            )
                        except Exception as e:
                            print(f"BubbleBot error: {e}")
                            bubbles_out = []
                        yield (
                            "",
                            history,
                            bubbles_out,
                            *update_bubble_buttons(bubbles_out),
                        )
                        break

                    if bot_message == "[new_message]":
                        new_message = True
                        continue

                    if bot_message == "[change_recipient_agent]":
                        # Ignore agent change events
                        chatbot_queue.get(block=True)  # discard new agent name
                        continue

                    if new_message:
                        history.append([None, bot_message])
                        new_message = False
                    else:
                        history[-1][1] += bot_message

                    yield (
                        "",
                        history,
                        current_bubbles,
                        *update_bubble_buttons(current_bubbles),
                    )
                except queue.Empty:
                    break

        # Button click logic for send
        button.click(user, inputs=[msg, chatbot], outputs=[msg, chatbot]).then(
            bot,
            [msg, chatbot, bubbles_state],
            [msg, chatbot, bubbles_state, *bubble_btns],
        )
        # File upload
        file_upload.change(handle_file_upload, file_upload)
        # Textbox submit
        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot,
            [msg, chatbot, bubbles_state],
            [msg, chatbot, bubbles_state, *bubble_btns],
        )

        # Bubble button click logic
        for i, btn in enumerate(bubble_btns):

            def make_bubble_click(idx):
                def on_click(bubbles, history):
                    if bubbles and idx < len(bubbles):
                        bubble_text = bubbles[idx]
                        # Send the bubble text as a user message and clear bubbles
                        user_msg, new_history = user(bubble_text, history)
                        return user_msg, new_history, []
                    return "", history, []

                return on_click

            btn.click(
                make_bubble_click(i),
                inputs=[bubbles_state, chatbot],
                outputs=[msg, chatbot, bubbles_state],
            ).then(
                lambda *args: [],
                [],
                [bubbles_state],
            ).then(
                bot,
                [msg, chatbot, bubbles_state],
                [msg, chatbot, bubbles_state, *bubble_btns],
            )

        # Enable queuing for streaming intermediate outputs
        demo.queue(default_concurrency_limit=10)

        # Workaround for bug caused by mcp tool usage
        # TODO: Find the root cause and fix it
        if hasattr(demo, "_queue"):
            if getattr(demo._queue, "pending_message_lock", None) is None:
                demo._queue.pending_message_lock = asyncio.Lock()
            if getattr(demo._queue, "delete_lock", None) is None:
                demo._queue.delete_lock = asyncio.Lock()

    # Launch the demo

    return demo, kwargs


if __name__ == "__main__":
    demo, kwargs = demo_gradio(agency)
    demo.launch(**kwargs)
