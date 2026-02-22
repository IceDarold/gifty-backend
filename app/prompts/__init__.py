import os
from functools import lru_cache

class PromptRegistry:
    def __init__(self, prompts_dir: str):
        self.prompts_dir = prompts_dir

    @lru_cache(maxsize=32)
    def get_prompt(self, name: str) -> str:
        """Loads a prompt from a markdown file in the prompts directory."""
        file_path = os.path.join(self.prompts_dir, f"{name}.md")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt '{name}' not found at {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

# Default instance pointing to the app/prompts directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
registry = PromptRegistry(os.path.join(BASE_DIR, "prompts"))
