class DyadResearchError(Exception):
    """Base exception for expected application failures."""


class ConfigurationError(DyadResearchError):
    """The research configuration is invalid or unsafe."""


class DataCapabilityError(DyadResearchError):
    """The requested data is outside the truthful local capability."""


class PointInTimeUnavailableError(DataCapabilityError):
    """Historical point-in-time data is not available."""


class DataContractError(DyadResearchError):
    """A source database does not satisfy the expected schema."""
