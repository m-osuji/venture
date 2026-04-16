"""
Handles the technical details for the Granite 4.0 LLM integration.

Usage:
    Import `init_granite` to initialise a shared Mellea session.
"""
import os
from dotenv import load_dotenv

# apply Hugging Face compatibility patches before importing any Mellea modules
import backend.helpers.hf_helpers

from mellea import MelleaSession
from mellea.backends import ModelOption, model_ids
from mellea.backends.huggingface import LocalHFBackend

# HF's `transformers` will automatically look for the HF_TOKEN environment variable for authentication
load_dotenv()

SESSION = None

def init_granite() -> MelleaSession:
    """
    Initialises a shared Mellea session for the Granite 4.0 LLM.

    Returns:
        MelleaSession: The initialized Mellea session.
    """
    global SESSION # use a global variable to store the session instance

    if SESSION is None:
        SESSION = MelleaSession(
            # use the local Hugging Face backend with the Granite 4.0 hybrid micro model
            LocalHFBackend(
                model_ids.IBM_GRANITE_4_HYBRID_MICRO, 
                model_options={ModelOption.MAX_NEW_TOKENS: 256}, # limit the number of new tokens generated to 256
            )
        ) 

        print('> [model] Granite 4.0 session initialised.')

    return SESSION
