class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass

class ForbiddenError(Exception):
    """Raised when a user does not have permission."""
    pass

class ValidationError(Exception):
    """Raised when data validation fails."""
    pass

class ConflictError(Exception):
    """Raised when an operation conflicts with existing data (e.g. duplicate)."""
    pass
