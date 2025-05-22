import queue
import threading
import asyncio
from loguru import logger

from agency_swarm import Agency
from agency_swarm.util.files import get_file_purpose, get_tools
from agency_swarm.util.streaming import create_gradio_handler
from agency_swarm.tools import CodeInterpreter, FileSearch

from study_buddy.main import agency


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

        def bot(original_message, history, dropdown):
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
                )
                return (
                    "",
                    history,
                    gr.update(
                        value=recipient_agent.name,
                        choices=set([*recipient_agent_names, recipient_agent.name]),
                    ),
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
            while True:
                try:
                    bot_message = chatbot_queue.get(block=True)

                    if bot_message == "[end]":
                        completion_thread.join()
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
                    )
                except queue.Empty:
                    break

        button.click(user, inputs=[msg, chatbot], outputs=[msg, chatbot]).then(
            bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
        )
        dropdown.change(handle_dropdown_change, dropdown)
        file_upload.change(handle_file_upload, file_upload)
        msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
            bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
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
