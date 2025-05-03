import pathlib
import sys

from camel.logger import set_log_level
from camel.models import ModelFactory
from camel.societies import RolePlaying
from camel.toolkits import (
    ExcelToolkit,
    ImageAnalysisToolkit,
    SearchToolkit,
    BrowserToolkit,
    FileWriteToolkit,
)
from camel.types import ModelPlatformType, ModelType
from dotenv import load_dotenv
from owly.utils import run_society, DocumentProcessingToolkit


base_dir = pathlib.Path(__file__).parent.parent
env_path = base_dir / "agent" / "owly" / ".env"
load_dotenv(dotenv_path=str(env_path))
set_log_level(level="DEBUG")


def _construct_society(question: str) -> RolePlaying:
    models = {
        "user": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
        "assistant": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
        "browsing": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
        "planning": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
        "image": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
        "document": ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_2_0_FLASH_THINKING,
            model_config_dict={"temperature": 0},
        ),
    }

    tools = [
        *BrowserToolkit(
            headless=True,
            web_agent_model=models["browsing"],
            planning_agent_model=models["planning"],
        ).get_tools(),
        *ImageAnalysisToolkit(model=models["image"]).get_tools(),
        SearchToolkit().search_duckduckgo,  # Comment this out if you don't have google search
        *ExcelToolkit().get_tools(),
        *DocumentProcessingToolkit(model=models["document"]).get_tools(),
        *FileWriteToolkit(output_dir="./").get_tools(),
    ]

    user_agent_kwargs = {"model": models["user"]}
    assistant_agent_kwargs = {"model": models["assistant"], "tools": tools}

    task_kwargs = {
        "task_prompt": question,
        "with_task_specify": False,
    }

    society = RolePlaying(
        **task_kwargs,
        user_role_name="user",
        user_agent_kwargs=user_agent_kwargs,
        assistant_role_name="assistant",
        assistant_agent_kwargs=assistant_agent_kwargs,
    )

    return society


def run_owl(prompt: str):
    society = _construct_society(prompt)
    answer, chat_history, token_count = run_society(society)
    print(f"\033[94mAnswer: {answer}\033[0m")


if __name__ == "__main__":
    run_owl(prompt="Buying a house Netherlands. Don't verify your results.")
