"""
Human transfer stub.

Real transfer to a phone line or live agent is NOT implemented.
This module exposes a clear interface so the conversation layer can
report a structured result without falsely claiming success.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class TransferResult:
    success: bool
    status: Literal["not_implemented", "queued", "failed"]
    message: str


def request_human_transfer(reason: str = "") -> TransferResult:
    """
    Request a transfer to a human representative.

    Always returns success=False because live transfer is not implemented
    in this prototype. The conversation layer should tell the caller that
    a representative will follow up with them — it must NOT say the
    transfer succeeded.
    """
    return TransferResult(
        success=False,
        status="not_implemented",
        message=(
            "Human transfer is not yet implemented in this prototype. "
            "A representative will need to follow up with the caller."
        ),
    )
