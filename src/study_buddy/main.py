from agency_swarm import Agency

from study_buddy.StudyBuddy.study_buddy import StudyBuddy
from study_buddy.BubbleBot.bubble_bot import BubbleBot


# Initialize agents
study_buddy = StudyBuddy()
bubble_bot = BubbleBot()

# Define agency structure
# Simplified to only include the Coder agent
agency = Agency(
    [
        study_buddy,
        bubble_bot,
    ],
    shared_instructions="./agency_manifesto.md",
)  # Path relative to agency_swarm package
