"""Stubs for social media connectors.

Implement platform-specific posting functions here. Keep secrets out of source control.
"""

from .stub_connector import StubConnector
from .facebook_connector import FacebookConnector

__all__ = ["StubConnector", "FacebookConnector"]
