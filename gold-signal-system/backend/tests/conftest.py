"""pytest configuration for async tests."""

import os
import sys

# Ensure the backend root is on the path so `app` is importable during tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
