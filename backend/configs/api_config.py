import os
import sys
import importlib.util
from dotenv import load_dotenv
# OPENAI
from openai import OpenAI


def setup_openai_api():
    """
    """
    # Connect path to env file out of this directory.
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(root_path)
    load_dotenv()

    # Check if env.py exists and import it directly.
    if os.path.isfile(os.path.join(root_path, 'env.py')):
        spec = importlib.util.spec_from_file_location(
            "env", os.path.join(root_path, 'env.py')
        )
        env = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(env)

    # OPENAI Client Setup.
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return client
