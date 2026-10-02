class BusinessRuleError(ValueError):
    """Raised when an operation would violate an inventory rule."""


__all__ = ["BusinessRuleError"]
