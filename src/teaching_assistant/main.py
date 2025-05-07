from agency_swarm import Agency

from teaching_assistant.Tara.tara import Tara


# Initialize agents
tara = Tara()

# Define agency structure
# Simplified to only include the Coder agent
agency = Agency(
    [
        tara,
    ],
    shared_instructions="./agency_manifesto.md",
)  # Path relative to agency_swarm package
