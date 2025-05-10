import os
from agency_swarm import Agent
from pydantic import BaseModel


class BubbleSuggestions(BaseModel):
    suggested_bubbles: list[str]


class BubbleBot(Agent):
    def __init__(self):
        # Get the current directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Construct paths relative to the current directory
        instructions_path = os.path.join(current_dir, "instructions.md")

        super().__init__(
            name="BubbleBot",
            description="Generates contextual question/reply suggestions for users",
            instructions=instructions_path,
            temperature=0.7,  # Creative but consistent
            model="gpt-4.1-nano",  # Match the model used by StudyBuddy
        )

    def generate_bubbles(
        self, last_study_buddy_message: str, conversation_history: list[str]
    ) -> list[str]:
        """
        Generate contextual question/reply suggestions for users
        TypeError('You tried to pass a `BaseModel` class to `chat.completions.create()`;
        You must use `beta.chat.completions.parse()` instead')

        """
        response = self.client.beta.chat.completions.parse(
            model="gpt-4.1-nano",
            response_format=BubbleSuggestions,
            messages=[
                {"role": "system", "content": self.instructions},
                {
                    "role": "user",
                    "content": "conversation history: "
                    + "\n".join(conversation_history)
                    + "\n\nlast message: "
                    + last_study_buddy_message,
                },
            ],
        )
        print(response.choices[0].message.parsed.suggested_bubbles)
        return {
            "suggested_bubbles": response.choices[0].message.parsed.suggested_bubbles
        }
