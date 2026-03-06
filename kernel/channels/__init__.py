"""Channel ingress adapters."""

from kernel.channels.email import EVENT_TYPE as EMAIL_EVENT_TYPE
from kernel.channels.email import emit_email_artifact

__all__ = [
    "EMAIL_EVENT_TYPE",
    "emit_email_artifact",
]
