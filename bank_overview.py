import json
import os
import requests # Make sure requests is imported if you haven't already

def find_iban(aliases):
    """Helper function to find the IBAN from a list of account aliases."""
    if not aliases:
        return "N/A"
    for alias in aliases:
        # Use .get() for safer access in case keys are missing
        if alias.get('_type_') == 'IBAN':
            return alias.get('_value', 'N/A') # Return value or N/A if value is missing
    return "N/A" # Return N/A if no alias with type IBAN is found

def get_counterparty_name(transaction):
    """Helper to extract counterparty display name from payment/request."""
    try:
        # Navigate through the nested structure, using .get() for safety
        counterparty_alias = transaction.get('_counterparty_alias', {})
        label_account = counterparty_alias.get('label_monetary_account', {})
        # Prefer display name, fallback to pointer name if needed
        name = label_account.get('_display_name')
        if not name:
             pointer = counterparty_alias.get('pointer', {})
             name = pointer.get('_name')
        return name if name else "Unknown Counterparty"
    except Exception:
        return "Unknown Counterparty"


# --- MODIFIED FUNCTION ---
# Changed parameter name for clarity (optional)
def generate_bank_overview(data_dict):
    """
    Parses bank account data (as a dictionary) and returns a Markdown summary.

    Args:
    data_dict: A dictionary containing the bank account data.

    Returns:
    A string containing the bank account overview in Markdown format,
    or an error message.
    """
    try:
        # --- REMOVED THIS LINE: data = json.loads(json_data_string) ---
        # Now we assume data_dict is already the parsed dictionary

        # Check if the input is actually a dictionary (especially if get_bunq_data failed)
        if not isinstance(data_dict, dict) or not data_dict:
             return "Error: Input data is not a valid dictionary or is empty."

        # Use data_dict directly from now on
        user_info = data_dict.get('user', {})
        user_display_name = user_info.get('_display_name', 'N/A')
        user_legal_name = user_info.get('_legal_name', user_display_name)
        user_status = user_info.get('_status', 'N/A')

        accounts = data_dict.get('accounts', [])
        if not accounts:
            return "## Bank Account Overview\n\n*   No account data found."

        account = accounts[0]
        account_aliases = account.get('_alias', [])
        account_iban = find_iban(account_aliases)
        account_desc = account.get('_description', 'N/A')
        account_balance_info = account.get('_balance', {})
        account_balance = account_balance_info.get('_value', 'N/A')
        account_currency = account_balance_info.get('_currency', '')
        account_status = account.get('_status', 'N/A')
        daily_limit_info = account.get('_daily_limit', {})
        daily_limit = daily_limit_info.get('_value', 'N/A')
        daily_limit_currency = daily_limit_info.get('_currency', '')

        payments = data_dict.get('payments', [])
        requests_data = data_dict.get('requests', []) # Renamed variable to avoid conflict
        num_payments = len(payments)
        num_requests = len(requests_data) # Use the new variable name

        frequent_counterparty = "N/A"
        if payments:
            frequent_counterparty = get_counterparty_name(payments[0])
        elif requests_data: # Use the new variable name
            frequent_counterparty = get_counterparty_name(requests_data[0])

        cards = data_dict.get('cards', [])
        num_cards = len(cards)

        markdown = f"# Bank Account Overview\n\n"
        markdown += f"## User Information\n"
        markdown += f"*   **Name:** {user_legal_name} ({user_display_name})\n"
        markdown += f"*   **User Status:** {user_status}\n\n"

        markdown += f"## Account Details\n"
        markdown += f"*   **Description:** {account_desc}\n"
        markdown += f"*   **IBAN:** {account_iban}\n"
        markdown += f"*   **Status:** {account_status}\n"
        markdown += f"*   **Balance:** {account_currency} {account_balance}\n"
        markdown += f"*   **Daily Limit:** {daily_limit_currency} {daily_limit}\n\n"

        markdown += f"## Recent Activity Summary\n"
        markdown += f"*   **Recorded Payments:** {num_payments}\n"
        # Use the new variable name here too
        markdown += f"*   **Recorded Requests:** {num_requests}\n"
        if frequent_counterparty != "N/A" and frequent_counterparty != "Unknown Counterparty":
            markdown += f"*   **Recent Counterparty Example:** {frequent_counterparty}\n\n"
        else:
            markdown += "\n"

        markdown += f"## Associated Cards\n"
        markdown += f"*   **Number of Cards:** {num_cards}\n"

        return markdown

    # Keep JSONDecodeError in case the input *was* intended to be a string
    # but was invalid, although unlikely with the current flow.
    except json.JSONDecodeError:
        return "Error: Invalid JSON input. Could not decode."
    except Exception as e:
        return f"An error occurred during processing: {e}"


def get_bunq_data():
    """Fetches bunq overview data from the service."""
    bunq_service = os.environ.get("BUNQ_SERVICE", "http://localhost:42069")
    try:
        response = requests.get(f"{bunq_service}/bunq/overview", timeout=10) # Added timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return response.json() # Returns a dictionary
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from bunq service: {e}")
        return {} # Return empty dict on error
    except json.JSONDecodeError:
        print("Error decoding JSON response from bunq service.")
        return {} # Return empty dict on error
