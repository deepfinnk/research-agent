from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from camel.configs import GeminiConfig
from camel.messages import BaseMessage
from camel.agents import ChatAgent, TaskPlannerAgent
import os

def main(toolkit):
    # Define the model, here in this case we use GEMINI_2_0_FLASH_THINKING
    model = ModelFactory.create(
        model_platform=ModelPlatformType.GEMINI,
        model_type=ModelType.GEMINI_2_5_FLASH,
        model_config_dict=GeminiConfig().as_dict(),
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    # Define an assistant message
    system_msg = "You are a helpful financial advisor with insights into your client's financial situation."
    # Create agent with tool
    chat_agent = ChatAgent(system_msg, model=model, tools=toolkit)

    # The agent can now use the calculator tool in conversations
    user_prompt = 'I want to save up 50000 in 2 years, how should I budget my money to reach that goal?'

    plan_prompt = f"Given the prompt provided above and the tools provided, return the subset of tools that should be used to provide the answer. Make sure you take into account the user's current financial situation."

    response = chat_agent.step(user_prompt + '\n' + plan_prompt)
    print(response.msg.content.replace('`', '').split(','))

    # response = agent.step("What is 5 + 3?")
    # print(response.msgs[0].content)

# Define a tool
def calculator(a: int, b: int) -> int:
    r"""Adds two numbers.

    Args:
        a (int): The first number to be added.
        b (int): The second number to be added.

    Returns:
        integer: The sum of the two numbers.
    """
    return a + b

def get_account_balance() -> float:
    r"""Gets the balance of the user's account.

    Returns:
        float: The balance of the user's account.
    """
    return 5000.0

def get_income() -> float:
    r"""Gets the average monthly income of the user.

    Returns:
        float: The income of the user.
    """
    return 3000.0

def get_expenses() -> float:
    r"""Gets the average monthly expense of the user.

    Returns:
        float: The expenses of the user.
    """
    return 1500.0

def yap() -> str:
    r"""Outputs a bunch of nonsense

    
    """


if __name__ == "__main__":
    tools = [calculator, get_account_balance, get_income, get_expenses]
    main(toolkit=tools)
