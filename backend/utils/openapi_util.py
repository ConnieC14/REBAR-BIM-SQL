# OpenAI API Config
from backend.configs.api_config import setup_openai_api

openAIclient = setup_openai_api()

def get_embedding(text, model='text-embedding-ada-002') -> list:
    """
    Generates an OpenAI embedding for the given text using the
    'text-embedding-ada-002' model.

    Parameters:
    ----------
    text : str
        The input text from which the embedding is to be generated.

    Returns:
    -------
    list:
        A list of floating-point numbers representing the embedding
        vector of the input text.
    """
    response = openAIclient.embeddings.create(
        input=text, model=model
    )
    return response.data[0].embedding

