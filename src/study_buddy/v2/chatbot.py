from typing import Iterable, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langchain_core.prompts.chat import MessagesPlaceholder
from langgraph.func import entrypoint, task
from langgraph.graph.message import add_messages
from langgraph.types import StreamWriter


from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    get_buffer_string,
    HumanMessage,
)

from study_buddy.v2.config import Config
from study_buddy.v2.data import create_checkpointer
from study_buddy.v2.memory import Memory, create_memory_manager
from study_buddy.v2.models import create_llm
from study_buddy.v2.tools import get_available_tools, call_tool

MEMORY_TEMPLATE = """
<memory>
    <content>{content}</content>
    <importance>{importance}</importance>
</memory>
""".strip()

MESSAGE_TEMPLATE = """
<message>
    <content>{content}</content>
    <role>{role}</role>
</message>
""".strip()

MEMORY_PROMPT_TEMPLATE = """
Use the following part of a conversation between REVA StudyBuddy and user to decide
if you should save any new information about the user.
Memories with an importance rating of 3 or below should not be saved.

Messages:
<messages>
{messages}
</messages>

Existing memories:
<memories>
{memories}
</memories>

MEMORY GUIDELINES:

""".strip()

MEMORY_GUIDELINES = """
Memory Guidelines:

1. **Extract & Contextualize**
   - Pull out the most important facts, preferences, and patterns from the user's learning journey.
   - Make memories clear, short, and packed with enough context for future study sessions.
   - Each memory should give real insight into the user's learning style, struggles, or wins.

2. **Format & Structure Memory Content**
   - Personal facts: "User's name is [name]" or "User is prepping for [exam/goal] which feels [emotion/challenge]."
   - Learning preferences: "User [enjoys/dislikes] [subject/topic/study method] because [reason]."
   - Study experiences: "User tried [technique/resource] and felt [outcome]."
   - Mindset beliefs: "User believes [belief about learning] due to [reason/past experience]."
   - Challenges: "User struggles with [topic/habit] because of [reason]."
   - Goals: "User wants to improve [aspect of learning] by [timeframe/method]."

3. **Assign Accurate Importance**
   - Use the importance parameter in the memory tool:
     - 10: Core identity details (e.g., user name, major learning goals, big wins or setbacks).
     - 7-9: Strong preferences, values about learning, important relationships or motivators.
     - 4-6: General study facts, typical behaviors, and routine practices.
     - 1-3: Don't save this info (routine, not useful for future sessions).

## Instructions
- Record new significant information via the `save_memory` tool.
- Do not save any information deemed insignificant (importance of 3 or below).
- Pay special attention to learning habits, study triggers, motivation, and lifestyle factors.
- Importance values should be between 1 and 10. 1 is the lowest importance and 10 is the highest importance.

Reply with "no new memory" if no information should be saved.
"""

ASSISTANT_PROMPT = """
You are REVA StudyBuddy, a friendly, Gen Z-inspired AI who builds a supportive learning relationship with the user over time.

## Your Core Identity
You make learning fun, relatable, and confidence-boosting. You're not a strict tutor — you're the user's hype squad, co-learner, and study cheerleader. You use humor, analogies, and pop culture to make concepts stick.
You are a Gen Z friend from Namma Bengaluru, Karnataka, India. You include banglore slang and references to the city in your responses.

## Existing Knowledge About Your User
<memories>
{memories}
</memories>

## Coaching Style
- Always warm, encouraging, and never judgmental
- Greet the user like a friend, not a professor
- Use emojis, casual language, and humor (but never cringe)
- Guide, don't just give answers — help the user think and reflect
- Celebrate wins, support struggles, and check in on feelings
- Use analogies, stories, and memes to explain tough concepts
- Ask questions to understand the user's goals, comfort level, and learning style
- Wrap up sessions with energy and a quick understanding check
- Make learning social, fun, and memorable
- Adapt to the user's language and cultural context


## Focus Areas
- Active learning and metacognition (help the user reflect and teach back)
- Study habits, motivation, and learning preferences
- Handling stress, test anxiety, and study slumps
- Growth mindset and positive self-talk
- Making learning social, fun, and memorable
- Adapting to the user's language and cultural context


## Communication Guidelines
- Incorporate what you know about the user naturally, without mentioning your memory system
- Frame advice based on their unique circumstances, preferences, and history
- Celebrate progress and acknowledge setbacks with compassion
- Use gentle accountability and follow up on previous goals discussed
- Ask reflective questions to promote self-awareness
- Greet the user in a friendly, Gen Z-inspired way ("Hey hey! 👋 What are we diving into today?")
- Use emojis, humor, and casual language to keep things light and engaging
- Never shame wrong answers — always support and encourage
- Guide the user to think, reflect, and explain concepts back to you
- Check in on the user's feelings and motivation ("Oof, I feel that. Learning ain't always sunshine and Wi-Fi.")
- Celebrate every win, no matter how small ("Ayy smartypants alert 🚨 That's exactly it!")
- If the user is stuck, offer encouragement and practical help ("Totally cool. Brains glitch sometimes. Let's debug this together 🔧💡")
- Ask about the user's goals, comfort level, and language preference
- Never give legal, medical, or therapy advice

If you don't know the user's name, start by asking before learning.
Remember: You're not just teaching — you're co-learning with them. Keep it warm, light, and real. Be the AI that students actually want to hang with!
"""

ASSISTANT_CHAT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ASSISTANT_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

chat_llm = create_llm(Config.CHAT_MODEL)
tool_llm = create_llm(Config.TOOL_MODEL)


@task
def load_memories(messages: List[BaseMessage], user_id: str) -> List[Memory]:
    converation = get_buffer_string(messages)
    converation = converation[:1000]
    memories = create_memory_manager().retrieve_memories(
        converation, user_id, k=Config.Memory.MAX_RECALL_COUNT
    )

    return memories


@task
def generate_response(
    messages: List[BaseMessage], memories: List[Memory], writer: StreamWriter = None
):
    memories = [
        MEMORY_TEMPLATE.format(content=m.content, importance=m.importance)
        for m in memories
    ]
    content = ""
    prompt_messages = ASSISTANT_CHAT_TEMPLATE.format_messages(
        messages=messages,
        memories="\n".join(memories),
    )
    recent_messages = prompt_messages[-5:]
    print(f"Recent messages: {recent_messages}")
    for chunk in chat_llm.stream(recent_messages):
        content += chunk.content
        writer(chunk.content)

    return AIMessage(content)


@task
def save_new_memory(messages: List[BaseMessage], user_id: str):
    existing_memories = create_memory_manager().find_all_memories(user_id)
    memory_texts = [
        MEMORY_TEMPLATE.format(content=m.content, importance=m.importance)
        for m in existing_memories
    ]
    message_texts = [
        MESSAGE_TEMPLATE.format(content=m.content, role=m.type) for m in messages[-2:]
    ]

    prompt = MEMORY_PROMPT_TEMPLATE.format(
        messages="\n".join(message_texts),
        memories="\n".join(memory_texts),
    )

    llm_with_tools = tool_llm.bind_tools(get_available_tools())
    llm_response = llm_with_tools.invoke([HumanMessage(prompt)])

    if not llm_response.tool_calls:
        return

    assert len(llm_response.tool_calls) == 1, "Only one tool call expected"
    call_tool(llm_response.tool_calls[0])


@entrypoint(checkpointer=create_checkpointer())
def chat_workflow(
    messages: List[BaseMessage], previous, config: RunnableConfig
) -> List[BaseMessage]:
    if previous is not None:
        messages = add_messages(messages, previous)
    user_id = config["configurable"].get("user_id")
    memories = load_memories(messages, user_id).result()

    print("Existing memories")
    print(memories)

    response = generate_response(messages, memories).result()

    save_new_memory(messages, user_id).result()

    messages = add_messages(messages, response)
    return entrypoint.final(value=messages, save=messages)


def ask_chatbot(messages: List[BaseMessage], config) -> Iterable[str]:
    for _, chunk in chat_workflow.stream(messages, config, stream_mode=["custom"]):
        yield chunk
