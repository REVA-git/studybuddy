from agency_swarm import Agency

from study_buddy.StudyBuddy.study_buddy import StudyBuddy


# Initialize agents
study_buddy = StudyBuddy()

# Define agency structure
# Simplified to only include the Coder agent
agency = Agency(
    [
        study_buddy,
    ],
    shared_instructions="./agency_manifesto.md",
)  # Path relative to agency_swarm package
