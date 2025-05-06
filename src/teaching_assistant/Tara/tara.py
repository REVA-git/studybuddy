import os
from agency_swarm import Agent


class Tara(Agent):
    def __init__(self):
        # Get the current directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Construct paths relative to the current directory
        instructions_path = os.path.join(current_dir, "instructions.md")
        files_folder = os.path.join(current_dir, "files")
        schemas_folder = os.path.join(current_dir, "schemas")
        # tools_folder needs update if still used
        tools_folder = os.path.join(
            current_dir, "tools"
        )  # This path might be incorrect now

        super().__init__(
            name="Tara",
            description="TARA - Teaching Assistant for REVA Academy, is an AI-powered tutor and coach designed to help undergraduate students at REVA University master academic concepts and prepare for an AI-driven future.",
            instructions=instructions_path,
            files_folder=files_folder,
            schemas_folder=schemas_folder,
            model="gpt-4.1-nano",
        )
