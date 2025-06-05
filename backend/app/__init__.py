# /backend/app/__init__.py

"""
App package initializer.
Ensures this directory is on the Python path so modules can be imported directly.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
