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


def demo_gradio(agency: Agency, height=450, dark_mode=True, **kwargs):
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
    recipient_agent_names = [agent.name for agent in agency.main_recipients]
    recipient_agent = agency.main_recipients[0]

    chatbot_queue = queue.Queue()
    gradio_handler_class = create_gradio_handler(chatbot_queue=chatbot_queue)

    with gr.Blocks(js=js) as demo:
        chatbot = gr.Chatbot(height=height)
        with gr.Row():
            with gr.Column(scale=9):
                dropdown = gr.Dropdown(
                    label="Recipient Agent",
                    choices=recipient_agent_names,
                    value=recipient_agent.name,
                )
                msg = gr.Textbox(label="Your Message", lines=4)
            with gr.Column(scale=1):
                file_upload = gr.Files(label="OpenAI Files", type="filepath")
        button = gr.Button(value="Send", variant="primary")

        # Add a state to hold the current suggestion bubbles
        bubbles_state = gr.State([])
        # Add a row of up to 4 buttons for suggestion bubbles
        with gr.Row() as bubble_row:
            bubble_btns = [gr.Button(visible=False) for _ in range(4)]

        def update_bubble_buttons(bubbles):
            # Update the button labels and visibility based on the bubbles list
            updates = []
            for i, btn in enumerate(bubble_btns):
                if i < len(bubbles):
                    updates.append(gr.update(value=bubbles[i], visible=True))
                else:
                    updates.append(gr.update(visible=False))
            return updates

        def handle_dropdown_change(selected_option):
            nonlocal recipient_agent
            recipient_agent = agency._get_agent_by_name(selected_option)

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
            nonlocal recipient_agent

            # Check if attachments contain file search or code interpreter types
            def check_and_add_tools_in_attachments(attachments, recipient_agent):
                for attachment in attachments:
                    for tool in attachment.get("tools", []):
                        if tool["type"] == "file_search":
                            if not any(
                                isinstance(t, FileSearch) for t in recipient_agent.tools
                            ):
                                # Add FileSearch tool if it does not exist
                                recipient_agent.tools.append(FileSearch)
                                recipient_agent.client.beta.assistants.update(
                                    recipient_agent.id,
                                    tools=recipient_agent.get_oai_tools(),
                                )
                                logger.info(
                                    "Added FileSearch tool to recipient agent to analyze the file."
                                )
                        elif tool["type"] == "code_interpreter":
                            if not any(
                                isinstance(t, CodeInterpreter)
                                for t in recipient_agent.tools
                            ):
                                # Add CodeInterpreter tool if it does not exist
                                recipient_agent.tools.append(CodeInterpreter)
                                recipient_agent.client.beta.assistants.update(
                                    recipient_agent.id,
                                    tools=recipient_agent.get_oai_tools(),
                                )
                                logger.info(
                                    "Added CodeInterpreter tool to recipient agent to analyze the file."
                                )
                return None

            check_and_add_tools_in_attachments(attachments, recipient_agent)

            if history is None:
                history = []

            original_user_message = user_message

            # Append the user message with a placeholder for bot response
            if recipient_agent:
                user_message = (
                    f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                )
            else:
                user_message = "👤 User:" + user_message.strip()

            if message_file_names:
                user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

            return original_user_message, history + [[user_message, None]]

        def bot(original_message, history, dropdown, bubbles):
            nonlocal attachments
            nonlocal message_file_names
            nonlocal recipient_agent
            nonlocal recipient_agent_names
            nonlocal images
            nonlocal uploading_files

            if not original_message:
                return (
                    "",
                    history,
                    gr.update(
                        value=recipient_agent.name,
                        choices=set([*recipient_agent_names, recipient_agent.name]),
                    ),
                    bubbles,
                    *update_bubble_buttons(bubbles),
                )

            if uploading_files:
                history.append([None, "Uploading files... Please wait."])
                yield (
                    "",
                    history,
                    gr.update(
                        value=recipient_agent.name,
                        choices=set([*recipient_agent_names, recipient_agent.name]),
                    ),
                    bubbles,
                    *update_bubble_buttons(bubbles),
                )
                return (
                    "",
                    history,
                    gr.update(
                        value=recipient_agent.name,
                        choices=set([*recipient_agent_names, recipient_agent.name]),
                    ),
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
                    recipient_agent,
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
                    print(f"{bot_message=}")

                    # Handle bubble suggestion event
                    if (
                        isinstance(bot_message, dict)
                        and bot_message.get("type") == "bubble_suggestions"
                    ):
                        current_bubbles = bot_message.get("bubbles", [])[:4]
                        yield (
                            "",
                            history,
                            gr.update(
                                value=recipient_agent.name,
                                choices=set(
                                    [*recipient_agent_names, recipient_agent.name]
                                ),
                            ),
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
                            gr.update(
                                value=recipient_agent.name,
                                choices=set(
                                    [*recipient_agent_names, recipient_agent.name]
                                ),
                            ),
                            bubbles_out,
                            *update_bubble_buttons(bubbles_out),
                        )
                        break

                    if bot_message == "[new_message]":
                        new_message = True
                        continue

                    if bot_message == "[change_recipient_agent]":
                        new_agent_name = chatbot_queue.get(block=True)
                        recipient_agent = agency._get_agent_by_name(new_agent_name)
                        yield (
                            "",
                            history,
                            gr.update(
                                value=new_agent_name,
                                choices=set(
                                    [*recipient_agent_names, recipient_agent.name]
                                ),
                            ),
                            current_bubbles,
                            *update_bubble_buttons(current_bubbles),
                        )
                        continue

                    if new_message:
                        history.append([None, bot_message])
                        new_message = False
                    else:
                        history[-1][1] += bot_message

                    yield (
                        "",
                        history,
                        gr.update(
                            value=recipient_agent.name,
                            choices=set([*recipient_agent_names, recipient_agent.name]),
                        ),
                        current_bubbles,
                        *update_bubble_buttons(current_bubbles),
                    )
                except queue.Empty:
                    break

        # Button click logic for send
        button.click(user, inputs=[msg, chatbot], outputs=[msg, chatbot]).then(
            bot,
            [msg, chatbot, dropdown, bubbles_state],
            [msg, chatbot, dropdown, bubbles_state, *bubble_btns],
        )
        # Dropdown change
        dropdown.change(handle_dropdown_change, dropdown)
        # File upload
        file_upload.change(handle_file_upload, file_upload)
        # Textbox submit
        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot,
            [msg, chatbot, dropdown, bubbles_state],
            [msg, chatbot, dropdown, bubbles_state, *bubble_btns],
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
                [msg, chatbot, dropdown, bubbles_state],
                [msg, chatbot, dropdown, bubbles_state, *bubble_btns],
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
    demo.launch(**kwargs)
    return demo


if __name__ == "__main__":
    demo_gradio(agency)
