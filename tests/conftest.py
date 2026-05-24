"""Shared pytest fixtures for llm-os tests."""

import os
import tempfile

import pytest

from llm_os.governance import ActionClass, Governance, Policy
from llm_os.treasury import Treasury
from llm_os.economic_engine import EconomicEngine
from llm_os.system_builder import SystemBuilder
from llm_os.llm_factory import LLMFactory


@pytest.fixture
def temp_storage_path():
    """Provide a unique temp file path for each test."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def gov():
    """Fresh Governance instance with simulation-safe policy."""
    return Governance()


@pytest.fixture
def treasury(temp_storage_path):
    """Fresh Treasury instance with temp storage."""
    return Treasury(storage_path=temp_storage_path)


@pytest.fixture
def economic_engine(temp_storage_path):
    """Fresh EconomicEngine instance with temp storage."""
    g = Governance()
    t = Treasury(storage_path=temp_storage_path)
    e = EconomicEngine(g, t, storage_path=temp_storage_path + "_econ")
    return e


@pytest.fixture
def system_builder(temp_storage_path):
    """Fresh SystemBuilder instance with temp storage."""
    g = Governance()
    t = Treasury(storage_path=temp_storage_path)
    return SystemBuilder(g, t, storage_path=temp_storage_path + "_builder")


@pytest.fixture
def llm_factory(temp_storage_path):
    """Fresh LLMFactory instance with temp storage."""
    g = Governance()
    t = Treasury(storage_path=temp_storage_path)
    return LLMFactory(g, t, storage_path=temp_storage_path + "_factory")
