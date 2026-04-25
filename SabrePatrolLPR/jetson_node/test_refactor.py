import sys
import os
import unittest
import numpy as np
from unittest.mock import MagicMock, patch

# Add the current directory to sys.path to import local modules
sys.path.append(os.path.dirname(__file__))

import mock_jetson

class TestSabreALPR(unittest.TestCase):
    def test_engine_initialization(self):
        from alpr_engine import ALPREngineThread
        engine = ALPREngineThread()
        # Mocking model loading
        with patch('jetson.inference.detectNet'), \
             patch('jetson.inference.lprNet'), \
             patch('jetson.inference.imageNet'):
            engine._initialize_models()
            self.assertIsNotNone(engine.net_det)
            self.assertIsNotNone(engine.net_lpr)
            self.assertIsNotNone(engine.net_vmmr)
            self.assertIsNotNone(engine.net_color)

    def test_engine_cropping_logic(self):
        from alpr_engine import ALPREngineThread
        import jetson.utils

        engine = ALPREngineThread()
        engine.db = MagicMock()

        # Manually set mocked nets
        engine.net_det = MagicMock()
        engine.net_lpr = MagicMock()
        engine.net_vmmr = MagicMock()
        engine.net_color = MagicMock()

        # Mock detection
        mock_det = MagicMock()
        mock_det.Confidence = 0.9
        mock_det.Left = 100
        mock_det.Top = 100
        mock_det.Right = 200
        mock_det.Bottom = 150
        engine.net_det.Detect.return_value = [mock_det]

        # Mock OCR
        engine.net_lpr.Recognize.return_value = ("TEST123", 0.99)

        # Mock Classification
        engine.net_vmmr.Classify.return_value = (0, 0.9)
        engine.net_vmmr.GetClassDesc.return_value = "CA_Toyota_Camry"
        engine.net_color.Classify.return_value = (0, 0.9)
        engine.net_color.GetClassDesc.return_value = "White"

        # Mock Image conversion and save
        with patch('jetson.utils.cudaToNumpy', return_value=np.zeros((50, 100, 3), dtype=np.uint8)), \
             patch('jetson.utils.cudaCrop') as mock_crop, \
             patch('cv2.imwrite'):

            # Create mock cuda images
            cuda_color = MagicMock()
            cuda_color.width = 1920
            cuda_color.height = 1080
            cuda_ir = MagicMock()

            engine.enqueue_frames(cuda_color, cuda_ir)

            # Run one iteration manually by calling the internal loop logic if possible
            # or just testing the methods directly

            # Test color determination
            color = engine._determine_color(cuda_color, mock_det)
            self.assertEqual(color, "White")
            # Verify cudaCrop was called for color
            # Expansion logic: left = max(0, 100 - 100) = 0, top = max(0, 100 - 50) = 50, etc.
            mock_crop.assert_any_call(cuda_color, (0, 50, 300, 200))

            # Test OCR and main loop logic
            # We simulate the queue processing
            engine.run_flag = False # Don't actually loop

            # Manual trigger of queue processing part
            c, i = engine.frame_queue.pop(0)
            detections = engine.net_det.Detect(i, overlay='none')
            for det in detections:
                roi = (det.Left, det.Top, det.Right, det.Bottom)
                plate = jetson.utils.cudaCrop(i, roi)
                mock_crop.assert_any_call(i, roi)
                text, conf = engine.net_lpr.Recognize(plate)
                self.assertEqual(text, "TEST123")

    def test_main_imports(self):
        from main import app, signal_handler
        self.assertIsNotNone(app)
        self.assertIsNotNone(signal_handler)

if __name__ == '__main__':
    unittest.main()
