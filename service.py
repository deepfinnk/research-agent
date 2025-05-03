import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import os
import sys
import pathlib
from flasgger import Swagger
from datetime import datetime
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType
from pydantic import BaseModel
from typing import List
import requests


class ResponseFormat(BaseModel):
    points: List[str]


# Add the agent directory to the path to find deep_finnk
# Assuming service.py is in the 'agent' directory
agent_dir = pathlib.Path(__file__).parent.resolve()
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

# Now import DeepFinnk
try:
    # Ensure deep_finnk doesn't have relative imports that break
    # when imported from service.py
    from deep_finnk import DeepFinnk
except ImportError as e:
    print("Error importing DeepFinnk: %s" % e)
    # Attempt to provide more context if possible
    print("Current sys.path: %s" % sys.path)
    print("Attempted to import from directory: %s" % agent_dir)
    # Handle the error appropriately, maybe raise it or exit
    sys.exit(
        "Could not import DeepFinnk. Check file location and potential import errors within deep_finnk.py."
    )
except Exception as e:
    print("An unexpected error occurred during DeepFinnk import: %s" % e)
    sys.exit("Exiting due to import error.")


app = Flask(__name__)
swagger = Swagger(app)

# Instantiate DeepFinnk once
# Ensure .env is loaded correctly relative to deep_finnk.py location if needed
# DeepFinnk's __init__ handles dotenv loading based on its own file location
try:
    print("Initializing DeepFinnk...")
    deep_finnk_instance = DeepFinnk()
    print("DeepFinnk initialized successfully.")
except Exception as e:
    print("Error initializing DeepFinnk: %s" % e)
    # Log the full traceback for debugging
    import traceback

    traceback.print_exc()
    deep_finnk_instance = None  # Indicate initialization failure


# Initialize query history state
query_history: list = []


@app.route("/query", methods=["POST"])
def generate_plan():
    """
    Execute a query using the DeepFinnk agent.
    ---
    tags:
      - Query
    parameters:
      - name: body
        in: body
        required: true
        schema:
          id: QueryRequest
          required:
            - prompt
          properties:
            prompt:
              type: string
              description: The natural language query to process.
              example: "I want to buy a house in Delft. What should I do?"
    responses:
      200:
        description: Query processed successfully.
        schema:
          id: QueryResponse
          properties:
            result:
              type: string
              description: The combined results from the DeepFinnk agent.
      400:
        description: Bad Request - Invalid JSON or missing 'prompt'.
      500:
        description: Internal Server Error - DeepFinnk initialization failed or error during query processing.
    """
    print("Received request at /query")  # Debug log
    if not deep_finnk_instance:
        print("Error: DeepFinnk service not initialized")
        return jsonify({"error": "DeepFinnk service not initialized"}), 500

    if not request.is_json:
        print("Error: Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    prompt = data.get("prompt")
    print("Received prompt: %s" % prompt)  # Debug log

    if not prompt:
        print("Error: Missing 'prompt' in request body")
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    try:
        print("Calling deep_finnk_instance.query with prompt: '%s'" % prompt)
        result = deep_finnk_instance.query(prompt=prompt)
        print("Query result: %s" % result)  # Debug log

        if result is None:
            print("Error: Query execution failed or returned no result")
            return jsonify(
                {"error": "Query execution failed or returned no result"}
            ), 500

        # todo: summarize result into shorter plan
        model = ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,  # Using enum
            model_type=ModelType.GEMINI_2_5_PRO_EXP,  # Using enum
        )
        agent = ChatAgent(
            "Make a nice summary of actions that user needs to take to achieve the desired goal. Write the exact numbers related to user budget (different categories like food, entertainment, transport, rent, and so on).",
            model=model,
        )
        result = agent.step(result, response_format=ResponseFormat)
        first_message = result.msgs[0]
        text_response = first_message.content

        # Store the query and result in history
        now = datetime.now()
        query_history.append(
            {"prompt": prompt, "result": text_response, "created_at": now}
        )

        # Assuming the result is a string that might need further processing
        # or is directly returnable.
        return jsonify({"result": text_response})
    except Exception as e:
        print("Error processing query: %s" % e)
        # Log the full traceback for debugging
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Internal server error during query processing"}), 500


@app.route("/implement-plan", methods=["POST"])
def implement_plan():
    """
    Implement a financial plan by calling the Bunq agent.
    ---
    tags:
      - Plan Implementation
    parameters:
      - in: body
        name: body
        required: true
        schema:
          id: ImplementPlanRequest
          required:
            - plan
          properties:
            plan:
              type: string
              description: The financial plan generated by the /query endpoint.
              example: "['Create a budget account named \'Groceries\' with a monthly limit of €300', 'Set up a savings goal named \'Vacation Fund\' aiming for €1000']"
    responses:
      200:
        description: Plan implementation initiated successfully.
        schema:
          id: ImplementPlanResponse
          properties:
            message:
              type: string
              description: Confirmation message.
            bunq_response:
              type: object
              description: Response from the Bunq agent API.
      400:
        description: Bad Request - Missing 'plan' in request body or invalid JSON.
      500:
        description: Internal Server Error - Failed to reach Bunq API or other internal issue.
      503:
        description: Service Unavailable - BUNQ_API_URL environment variable not set.
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    plan = data.get("plan")

    if not plan:
        return jsonify({"error": "Missing 'plan' parameter in request body"}), 400

    bunq_api_url = os.getenv("BUNQ_API_URL")
    if not bunq_api_url:
        print("Error: BUNQ_API_URL environment variable not set.")
        return jsonify({"error": "Bunq API endpoint configuration missing."}), 503

    task_endpoint = f"{bunq_api_url.rstrip('/')}/agent/task"

    # Construct a more effective task prompt
    task_prompt = (
        "Based on the following financial details:"
        f"<details>{plan}</details>. "
        "Here's what you must do:\n"
        "1. Check which bunq tools are available to you.\n"
        "2. Check the active monetary accounts\n"
        "3. Make a list of needed monetary accounts\n"
        "4. Create the missing monetary accounts (e.g., groceries, savings, bills, etc.) based on the plan.\n"
        "5. There are tools to get the account overview, accounts, payments, cards, etc. Check the tools and use them."
        "6. If a tool fails, retry it."
        "7. YOU MUST create monetary accounts for every budget envelope, and to transfer the appropriate amount of money to it."
        "Iteratively do each step, without asking the user for input. Always proceed to the next step. Proceed on implementing the plan."
    )

    payload = {"task": task_prompt}

    try:
        print(f"Sending task to Bunq API: {task_endpoint} with payload: {payload}")
        response = requests.post(task_endpoint, json=payload)  # Added timeout
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        bunq_response_data = response.json()
        print(f"Received response from Bunq API: {bunq_response_data}")

        return jsonify(
            {
                "message": "Plan implementation task sent to Bunq agent.",
                "bunq_response": bunq_response_data,
            }
        ), 200

    except requests.exceptions.RequestException as e:
        print(f"Error calling Bunq API: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to communicate with Bunq API: {e}"}), 500
    except Exception as e:
        print(f"Unexpected error in /implement-plan: {e}")
        import traceback

        traceback.print_exc()
        return jsonify(
            {"error": "Internal server error during plan implementation"}
        ), 500


@app.route("/history", methods=["GET"])
def get_history():
    """
    Get query history.
    ---
    tags:
      - History
    responses:
      200:
        description: Query history retrieved successfully.
        schema:
          id: QueryHistoryResponse
          properties:
            history:
              type: array
              items:
                type: object
                properties:
                  prompt:
                    type: string
                    description: The natural language query.
                  result:
                    type: string
                    description: The combined results from the DeepFinnk agent.
                  created_at:
                    type: string
                    format: date-time
                    description: The timestamp when the query was executed.
      500:
        description: Internal Server Error - Error retrieving query history.
    """
    try:
        # Sort history by date, newest first
        sorted_history = sorted(
            query_history, key=lambda item: item["created_at"], reverse=True
        )
        return jsonify(sorted_history)
    except Exception as e:
        print("Error retrieving query history: %s" % e)
        # Log the full traceback for debugging
        import traceback

        traceback.print_exc()
        return jsonify(
            {"error": "Internal server error during query history retrieval"}
        ), 500


if __name__ == "__main__":
    # Load environment variables if needed here for Flask specifically
    # e.g., load_dotenv() if service needs its own .env
    # Note: DeepFinnk already loads .env based on its location.
    # Make sure the .env file has necessary vars like GEMINI_API_KEY
    # and BUNQ_SERVICE if not set globally.
    load_dotenv()
    print("Starting Flask server...")
    port = int(
        os.environ.get("FLASK_PORT", 5001)
    )  # Use a different port than bunq service (42069)
    print("Running on http://0.0.0.0:%s" % port)
    # Setting debug=False for potentially cleaner logs in production/testing
    # Set debug=True for development if needed
    app.run(debug=False, host="0.0.0.0", port=port)
