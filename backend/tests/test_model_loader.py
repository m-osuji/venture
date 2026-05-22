import unittest
from unittest.mock import patch, MagicMock

# Adjust this import to match your project's folder structure
from backend.ai_opponent.model_loader import init_granite
from mellea.backends import ModelOption
import backend.ai_opponent.model_loader as model_loader

class TestModelLoader(unittest.TestCase):
    def setUp(self):
        # Crucial: Reset the global singleton before every test so they don't interfere
        model_loader.SESSION = None

    @patch('backend.ai_opponent.model_loader.MelleaSession')
    @patch('backend.ai_opponent.model_loader.LocalHFBackend')
    def test_init_granite_initialises_expected_backend_options(self, mock_hf_backend, mock_mellea_session):
        """Test that the loader initialises Granite with the configured token cap."""
    
        session = init_granite()

        mock_hf_backend.assert_called_once()
        args, kwargs = mock_hf_backend.call_args
        options = kwargs.get('model_options')

        self.assertEqual(options[ModelOption.MAX_NEW_TOKENS], 128)
        mock_mellea_session.assert_called_once()
        self.assertIsNotNone(session)
        
    def test_init_granite_singleton_pattern(self):
        """Test that calling init_granite twice returns the exact same instance."""
        
        # just testing the global variable logic, so can mock the instance
        mock_session_instance = MagicMock()
        model_loader.SESSION = mock_session_instance
        
        result1 = init_granite()
        result2 = init_granite()
        
        # ensure it didn't overwrite the mock and returned the same object both times
        self.assertEqual(result1, mock_session_instance)
        self.assertEqual(result1, result2)

if __name__ == '__main__':
    unittest.main()
