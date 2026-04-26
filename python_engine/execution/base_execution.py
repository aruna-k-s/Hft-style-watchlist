from abc import ABC, abstractmethod
from typing import Any, Dict


class ExecutionEngine(ABC):
    """Abstract execution interface for Phase 4 trading system."""

    def __init__(self, config: Any):
        self.config = config

    @abstractmethod
    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade order."""
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """Return current positions."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> float:
        """Return current cash balance."""
        raise NotImplementedError
