import unittest
from unittest.mock import patch, MagicMock
import torch

# Adjust this import to match your project's folder structure
from backend.ai_opponent.model_loader import init_granite
from mellea.backends import ModelOption
import backend.ai_opponent.model_loader as model_loader

class TestModelLoader(unittest.TestCase):
    def setUp(self):
        # Crucial: Reset the global singleton before every test so they don't interfere
        model_loader.SESSION = None

    @patch('backend.ai_opponent.model_loader.torch.cuda.is_available', return_value=True)
    @patch('backend.ai_opponent.model_loader.MelleaSession')
    @patch('backend.ai_opponent.model_loader.LocalHFBackend')
    def test_init_granite_gpu_configuration(self, mock_hf_backend, mock_mellea_session, mock_cuda):
        
        """Test that the loader configures float16 and auto-mapping when a GPU is present."""
    
        session = init_granite()
        
        # verify the GPU check happened
        mock_cuda.assert_called_once()
        
        # verify the Hugging Face backend was initialised with the GPU options
        mock_hf_backend.assert_called_once()
        args, kwargs = mock_hf_backend.call_args
        options = kwargs.get('model_options')
        
        self.assertEqual(options['device_map'], 'auto')
        self.assertEqual(options['torch_dtype'], torch.float16)
        self.assertEqual(options[ModelOption.MAX_NEW_TOKENS], 64)
        
        # verify it returns the mocked session
        self.assertIsNotNone(session)

    @patch('backend.ai_opponent.model_loader.torch.cuda.is_available', return_value=False)
    @patch('backend.ai_opponent.model_loader.MelleaSession')
    @patch('backend.ai_opponent.model_loader.LocalHFBackend')
    def test_init_granite_cpu_configuration(self, mock_hf_backend, mock_mellea_session, mock_cuda):
        """Test that the loader falls back to float32 and CPU memory when no GPU is found."""
    
        session = init_granite()
        
        # verify the CPU options were passed
        mock_hf_backend.assert_called_once()
        args, kwargs = mock_hf_backend.call_args
        options = kwargs.get('model_options')
        
        self.assertEqual(options['device_map'], 'cpu')
        self.assertEqual(options['torch_dtype'], torch.float32)
        self.assertTrue(options['low_cpu_mem_usage'])
        
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
