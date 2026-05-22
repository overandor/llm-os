"""LLM OS — Autonomous operating system for LLMs to create LLMs and economically viable systems.

The LLM OS is a unifying layer on top of membra-core that enables autonomous:
- LLM creation and training (LLM Factory)
- Software system development (System Builder)
- Real income generation (Economic Engine)
- Financial tracking and profit optimization (Treasury)
- Safety and policy enforcement (Governance)

Usage:
    from llm_os import Kernel
    os = Kernel()
    os.start()
"""

__version__ = "0.1.0"

from llm_os.kernel import Kernel
from llm_os.governance import ActionClass, Governance, Policy
from llm_os.treasury import Treasury
from llm_os.economic_engine import EconomicEngine
from llm_os.system_builder import SystemBuilder
from llm_os.llm_factory import LLMFactory

__all__ = [
    "Kernel",
    "ActionClass",
    "Governance",
    "Policy",
    "Treasury",
    "EconomicEngine",
    "SystemBuilder",
    "LLMFactory",
]
