import random
from typing import List

import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from study_buddy.v2.chatbot import ask_chatbot, chat_workflow
from study_buddy.v2.memory import create_memory_manager

LOADING_MESSAGES = [
    "Cracking open the brain snacks... 🍟🧠",
    "Sharpening my virtual pencils... ✏️🤓",
    "Googling the universe (JK, I'm smarter than that)... 🌐🚀",
    "Summoning the study squad... 📚👾",
    "Charging up my brain cells... ⚡️🧠",
    "Finding the cheat sheet (legally)... 📝😏",
    "Doing a quick brain dance... 🕺🧠",
    "Making sure I don't sound like a textbook... 📖❌",
    "Loading up the Gen Z vibes... 😎✨",
    "Checking for quantum banana theory... 🍌🔬",
    "Hyping up your next answer... 🎉🙌",
    "Plotting your brain glow-up... 💡🔥",
    "Flexing my AI muscles... 💪🤖",
    "Getting my meme game ready... 🥳📸",
    "Prepping a brainwave just for you... 🌊🧠",
    "Making sure I'm not cringe... 😅👌",
    "Channeling my inner study buddy... 🎓🤝",
    "Rolling out the brain carpet... 🧠🪄",
    "Double-checking my fun facts... 🤔🎲",
    "Warming up my hype squad voice... 📣😃",
]

CHATBOT_INTRO = "Hey hey! 👋 I'm your AI study buddy — part tutor, part hype squad, and 100% here for your brain goals. 😎 What are we diving into today? Math? History? Quantum banana theory? (Okay fine, made that one up.)\n\nYou feeling confident or kinda 'help me plz'? Any upcoming tests or just curious vibes?\n\nWanna roll in English, Kannada, Hindi, or full-on desi mode? 🇮🇳"


def create_history(prompt: str, app_config) -> List[BaseMessage]:
    state = chat_workflow.get_state(app_config)
    is_new_conversation = not state.values
    messages = [welcome_message] if is_new_conversation else []
    return messages + [HumanMessage(prompt)]


st.set_page_config(
    page_title="REVA StudyBuddy",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.header("REVA StudyBuddy")
st.subheader(
    "Your Gen Z AI study buddy — hype squad, brain cheerleader, and co-learner!"
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "1"

app_config = {
    "configurable": {
        "user_id": "1",
        "thread_id": str(st.session_state.thread_id),
    }
}

memories = create_memory_manager().find_all_memories(
    app_config["configurable"]["user_id"]
)

with st.sidebar:
    with st.form("conversation_id_form"):
        st.write("Choose your conversation")
        st.text_input("Conversation id", key="thread_id")
        submitted = st.form_submit_button("Submit")
        if submitted:
            st.toast(f"New conversation ID: {st.session_state.thread_id}", icon="💬")

if memories:
    st.markdown("## Memories")
    for memory in memories:
        st.markdown(f"- {memory.content} (importance: {memory.importance})")

welcome_message = AIMessage(content=CHATBOT_INTRO)

state = chat_workflow.get_state(app_config)
st.session_state.messages = state.values or [welcome_message]

for message in st.session_state.messages:
    is_user = type(message) is HumanMessage
    avatar = "👤" if is_user else "🤖"
    with st.chat_message("user" if is_user else "ai", avatar=avatar):
        st.markdown(message.content)

if prompt := st.chat_input("Ask me anything"):
    with st.chat_message("user", avatar="👤"):
        st.session_state.messages.append(HumanMessage(prompt))
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        message_placeholder.status(random.choice(LOADING_MESSAGES), state="running")

        try:
            full_response = ""
            for chunk in ask_chatbot(create_history(prompt, app_config), app_config):
                full_response += chunk
                message_placeholder.markdown(full_response)
            print(f"Assistant response: '{full_response}'")  # Debug print
            if not full_response.strip():
                full_response = "😅 Oops, I blanked out! Can you try that again?"
                message_placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"Uh oh, I hit a brain freeze: {e}"
            message_placeholder.markdown(full_response)
        st.session_state.messages.append(AIMessage(full_response))
