import numpy as np

class MockCudaImage:
    def __init__(self, width, height, channels=3):
        self.width = width
        self.height = height
        self.channels = channels
        self.shape = (height, width, channels)

class detectNet:
    def __init__(self, model=None, labels=None, input_blob=None, output_blob=None, threshold=0.5, argv=None):
        pass

    class Detection:
        def __init__(self):
            self.ClassID = 0
            self.Confidence = 0.9
            self.Left = 10
            self.Top = 10
            self.Right = 100
            self.Bottom = 100
            self.Width = 90
            self.Height = 90
            self.Center = (55, 55)
            self.Area = 8100

    def Detect(self, image, overlay='box,labels,conf'):
        return [self.Detection()]

class lprNet:
    def __init__(self, model=None, labels=None, input_blob=None, output_blob=None, argv=None):
        pass

    def Recognize(self, image):
        # Returns (text, confidence)
        return ("ABC1234", 0.95)

class imageNet:
    def __init__(self, model=None, labels=None, input_blob=None, output_blob=None, argv=None):
        pass

    def Classify(self, image):
        # Returns (class_idx, confidence)
        return (0, 0.85)

    def GetClassDesc(self, index):
        return "mock_class"

def videoSource(url, argv=None):
    class MockSource:
        def __init__(self, url):
            self.url = url
        def Capture(self, timeout=1000):
            return MockCudaImage(1920, 1080)
        def Close(self):
            pass
    return MockSource(url)

def cudaToNumpy(cuda_img):
    return np.zeros((cuda_img.height, cuda_img.width, cuda_img.channels), dtype=np.uint8)

def cudaFromNumpy(np_img):
    h, w, c = np_img.shape
    return MockCudaImage(w, h, c)

def cudaMemcpy(dst, src):
    pass

def cudaDeviceSynchronize():
    pass

def cudaCrop(image, roi):
    # roi is (left, top, right, bottom)
    left, top, right, bottom = roi
    return MockCudaImage(int(right - left), int(bottom - top))

def cudaAllocMapped(width, height, format):
    return MockCudaImage(width, height)

# Expose modules
import sys
from types import ModuleType

inference_mod = ModuleType("jetson.inference")
inference_mod.detectNet = detectNet
inference_mod.lprNet = lprNet
inference_mod.imageNet = imageNet
sys.modules["jetson.inference"] = inference_mod

utils_mod = ModuleType("jetson.utils")
utils_mod.videoSource = videoSource
utils_mod.cudaToNumpy = cudaToNumpy
utils_mod.cudaFromNumpy = cudaFromNumpy
utils_mod.cudaMemcpy = cudaMemcpy
utils_mod.cudaDeviceSynchronize = cudaDeviceSynchronize
utils_mod.cudaCrop = cudaCrop
utils_mod.cudaAllocMapped = cudaAllocMapped
sys.modules["jetson.utils"] = utils_mod
