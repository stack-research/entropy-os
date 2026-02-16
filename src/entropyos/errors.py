"""Domain errors for deterministic decay behavior."""


class EntropyError(Exception):
    """Base class for entropy runtime errors."""


class ExpiredError(EntropyError):
    """Raised when an API has expired."""


class ExpiredStateError(EntropyError):
    """Raised when requested state has already expired."""


class EntityNotFoundError(EntropyError):
    """Raised when a tracked entity is not present."""
