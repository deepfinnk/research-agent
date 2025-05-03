import pathlib


import json
import time
import os
import requests

from camel.agents import ChatAgent
from camel.logger import set_log_level
from camel.models import ModelFactory
from camel.societies import RolePlaying
from camel.toolkits import (
    AudioAnalysisToolkit,
    CodeExecutionToolkit,
    SearchToolkit,
    BrowserToolkit,
)
from camel.types import ModelPlatformType, ModelType
from dotenv import load_dotenv

from pydantic import BaseModel
from typing import List


# Assuming owly.utils contains run_society and DocumentProcessingToolkit
# Make sure DocumentProcessingToolkit is imported correctly if it's custom
try:
    from owly.utils import run_society
except ImportError:
    print(
        "Warning: owly.utils not found. Assuming DocumentProcessingToolkit is standard or placeholder."
    )

    # If DocumentProcessingToolkit is standard CAMEL, import it directly if needed
    # from camel.toolkits import DocumentProcessingToolkit # Or wherever it lives
    # If run_society is also from owly, you'll need to handle that too.
    # For now, let's assume it exists for the structure.
    # Define placeholders if needed for the code to run:
    class DocumentProcessingToolkit:  # Placeholder
        def __init__(self, model=None):
            pass

        def get_tools(self):
            return []

    def run_society(society, round_limit=5):  # Placeholder
        print("Warning: Using placeholder run_society")
        return "Placeholder Answer", [], 0


base_dir = pathlib.Path(__file__).parent.parent
# Adjust env_path if needed based on your project structure
# Assuming deep_finnk.py is inside an 'agent' directory
base_dir = pathlib.Path(__file__).parent
env_path = base_dir / "owly" / ".env"  # Example: if .env is in agent/owly/
# If deep_finnk.py is one level up from 'agent':
# base_dir = pathlib.Path(__file__).parent.parent
# env_path = base_dir / "agent" / "owly" / ".env" # Your original path


print(f"Looking for .env file at: {env_path.resolve()}")  # Debug print
load_dotenv(dotenv_path=str(env_path))
set_log_level(level="DEBUG")


INIT_SETTINGS = """
    You are a financial advisor in the bank Bunq in the Netherlands.
    Your task is to indicate the main actions a user can take so the goal will be achieved. Take into account budgeting, taxes, current economical situation, interest rates and so on.
"""

print(INIT_SETTINGS)


def _extract_result(response):
    if hasattr(response, "msgs") and response.msgs:
        first_message = response.msgs[0]
        text_response = first_message.content
        try:
            json.loads(text_response)
            return text_response
        except json.JSONDecodeError:
            print(f"Warning: Response is not valid JSON: {text_response}")
            return None
    else:
        return None


class ResponseFormat(BaseModel):
    points: List[str]


class DeepFinnk:
    MODEL_PLATFORM = ModelPlatformType.GEMINI
    MODEL_TYPE = ModelType.GEMINI_2_0_FLASH

    def __init__(self):
        self.models = {
            "user": ModelFactory.create(
                model_platform=self.MODEL_PLATFORM,
                model_type=self.MODEL_TYPE,
            ),
            "assistant": ModelFactory.create(
                model_platform=self.MODEL_PLATFORM,
                model_type=self.MODEL_TYPE,
            ),
            "browsing": ModelFactory.create(
                model_platform=self.MODEL_PLATFORM,
                model_type=self.MODEL_TYPE,
            ),
            "planning": ModelFactory.create(
                model_platform=self.MODEL_PLATFORM,
                model_type=self.MODEL_TYPE,
            ),
        }
        self.init_model = self.models["assistant"]

        self.browser_toolkit = BrowserToolkit(
            headless=True,
            web_agent_model=self.models["browsing"],
            planning_agent_model=self.models["planning"],
        )
        self.audio_toolkit = AudioAnalysisToolkit()  # Requires OPENAI_API_KEY
        self.code_toolkit = CodeExecutionToolkit(sandbox="subprocess", verbose=True)
        self.search_toolkit = SearchToolkit()  # Keep the instance

        self.all_tools = [
            *self.browser_toolkit.get_tools(),
            *self.audio_toolkit.get_tools(),
            *self.code_toolkit.get_tools(),
            self.search_toolkit.search_duckduckgo,
            self.search_toolkit.search_google,
            self.search_toolkit.search_bing,
            self.search_toolkit.search_brave,
        ]

        self.started = True

    def query(self, prompt: str):
        if not self.started:
            pass

        init_response_str = self.init_query(INIT_SETTINGS, prompt)
        if not init_response_str:
            print("Error: Initial query did not return a valid response.")
            return None

        try:
            data = json.loads(init_response_str)
        except json.JSONDecodeError:
            print(
                f"Error: Failed to decode JSON from initial response: {init_response_str}"
            )
            return None

        if "points" in data and isinstance(data["points"], list):
            points_list = data["points"]
            deep_results = []

            # 2. Deep Search for each point
            for point in points_list:
                point += " As an anwer, write a summary of your findings."
                print(f"\n--- Running Deep Search for Point: {point} ---")
                try:
                    deep_result_answer = self.deep_search(prompt=point, round_limit=2)
                    print(f"--- Result for Point '{point}': ---")
                    deep_result_answer = [
                        item["assistant"]
                        for item in deep_result_answer
                        if "assistant" in item
                    ]
                    deep_results.append(
                        {
                            "point": point,
                            "result": deep_result_answer,  # Store the raw answer string
                        }
                    )
                except Exception as e:
                    print(f"Error during deep search for point '{point}': {e}")
                time.sleep(1)

            combined_results = "\n\n".join(
                [
                    f"Point: {item['point']}\nResult:\n{item['result']}"
                    for item in deep_results
                ]
            )
            return combined_results

        else:
            print("Error: 'points' key missing or not a list in the initial response.")
            return None

    def init_query(self, settings: str, prompt: str):
        agent = ChatAgent(settings, model=self.init_model)
        try:
            response = agent.step(prompt, response_format=ResponseFormat)
            return _extract_result(response)
        except Exception as e:
            print(f"Error during init_query step: {e}")
            return None

    def deep_search(self, prompt, round_limit=5):
        society = self._construct_society(prompt)
        try:
            answer, chat_history, token_count = run_society(
                society, round_limit=round_limit
            )
            return chat_history
        except Exception as e:
            print(f"Error during run_society for prompt '{prompt}': {e}")
            return f"\033[91mError running society: {e}\033[0m"  # Option 2: Return formatted error

    def _construct_society(self, question: str) -> RolePlaying:
        user_agent_kwargs = {"model": self.models["user"]}
        assistant_agent_kwargs = {
            "model": self.models["assistant"],
            "tools": self.all_tools,
        }

        task_kwargs = {
            "task_prompt": question,
            "with_task_specify": False,  # Keep False if assistant should just execute
        }

        # Create the RolePlaying instance
        society = RolePlaying(
            **task_kwargs,
            user_role_name="user",  # Standard role name
            user_agent_kwargs=user_agent_kwargs,
            assistant_role_name="assistant",  # Standard role name
            assistant_agent_kwargs=assistant_agent_kwargs,
        )

        return society


if __name__ == "__main__":
    df = DeepFinnk()
    final_result = df.query(
        prompt="I want to buy a house in Delft, The Netherlands. What should I do?"
    )
    print("\n\n===== Final Combined Results =====")
    print(final_result)
