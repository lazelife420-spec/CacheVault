"""Mobile Access version compatibility handshake.

Evaluates whether a paired (or pairing) Android client's protocol version
and app version are compatible with this desktop build, independent of
token authentication. See docs/MOBILE_API_CONTRACT.md for the wire contract.
"""

from __future__ import annotations

from dataclasses import dataclass

# Protocol range this desktop build accepts. Bump MOBILE_PROTOCOL_MAX when a
# new protocol is introduced; bump MOBILE_PROTOCOL_MIN only once older
# clients are no longer supported.
MOBILE_PROTOCOL_MIN = 1
MOBILE_PROTOCOL_MAX = 1

# Oldest Android app version allowed to connect at all.
MINIMUM_MOBILE_VERSION = "0.1.5"

STATE_COMPATIBLE = "compatible"
STATE_UPDATE_RECOMMENDED = "update_recommended"
STATE_UPDATE_REQUIRED = "update_required"
STATE_UNKNOWN_CLIENT_VERSION = "unknown_client_version"
STATE_UNSUPPORTED_PROTOCOL = "unsupported_protocol"

ERROR_UPDATE_REQUIRED = "mobile_update_required"

_STATE_MESSAGES = {
    STATE_COMPATIBLE: "Compatible.",
    STATE_UPDATE_RECOMMENDED: "A newer CacheVault mobile companion is available.",
    STATE_UPDATE_REQUIRED: "Update the CacheVault mobile companion to continue.",
    STATE_UNKNOWN_CLIENT_VERSION: "Client app version could not be determined.",
    STATE_UNSUPPORTED_PROTOCOL: "Update the CacheVault mobile companion to continue.",
}


def parse_version(version: str | None) -> tuple[int, ...] | None:
    """Parse a dotted version string ("0.1.5") into a comparable tuple.

    Returns ``None`` for missing or malformed input rather than raising —
    callers must treat that as an unknown version, not a crash.
    """
    if not version or not isinstance(version, str):
        return None
    base = version.strip().split("-", 1)[0]
    parts = base.split(".")
    if not parts:
        return None
    out = []
    for p in parts:
        if not p.isdigit():
            return None
        out.append(int(p))
    return tuple(out) if out else None


@dataclass(frozen=True)
class CompatibilityResult:
    state: str
    compatible: bool
    update_required: bool
    message: str
    client_protocol: int | None
    server_protocol_min: int = MOBILE_PROTOCOL_MIN
    server_protocol_max: int = MOBILE_PROTOCOL_MAX
    minimum_mobile_version: str = MINIMUM_MOBILE_VERSION

    def to_response(self) -> dict:
        """Fields merged into a successful (200) handshake-bearing response."""
        return {
            "compatible": self.compatible,
            "server_protocol_min": self.server_protocol_min,
            "server_protocol_max": self.server_protocol_max,
            "minimum_mobile_version": self.minimum_mobile_version,
            "update_required": self.update_required,
        }

    def to_error_response(self) -> dict:
        """The structured 426 body for an incompatible client."""
        return {
            "error": ERROR_UPDATE_REQUIRED,
            "compatible": False,
            "client_protocol": self.client_protocol,
            "server_protocol_min": self.server_protocol_min,
            "server_protocol_max": self.server_protocol_max,
            "minimum_mobile_version": self.minimum_mobile_version,
            "update_required": True,
            "message": self.message,
        }


def evaluate_compatibility(
    protocol: int | None,
    app_version: str | None,
    *,
    protocol_min: int = MOBILE_PROTOCOL_MIN,
    protocol_max: int = MOBILE_PROTOCOL_MAX,
    minimum_mobile_version: str = MINIMUM_MOBILE_VERSION,
    recommended_mobile_version: str | None = None,
) -> CompatibilityResult:
    """Evaluate one client handshake against this desktop's supported range.

    Precedence (first match wins): unsupported/missing protocol > app version
    below the hard minimum > unparseable app version > update recommended >
    compatible. Protocol is the hard gate — a device is rejected outright if
    its protocol falls outside [protocol_min, protocol_max]. App version is a
    softer signal layered on top once the protocol itself is acceptable.
    """
    kwargs = dict(
        client_protocol=protocol,
        server_protocol_min=protocol_min,
        server_protocol_max=protocol_max,
        minimum_mobile_version=minimum_mobile_version,
    )

    if protocol is None or protocol < protocol_min or protocol > protocol_max:
        return CompatibilityResult(
            state=STATE_UNSUPPORTED_PROTOCOL, compatible=False, update_required=True,
            message=_STATE_MESSAGES[STATE_UNSUPPORTED_PROTOCOL], **kwargs,
        )

    min_tuple = parse_version(minimum_mobile_version)
    app_tuple = parse_version(app_version)

    if app_tuple is None:
        return CompatibilityResult(
            state=STATE_UNKNOWN_CLIENT_VERSION, compatible=True, update_required=False,
            message=_STATE_MESSAGES[STATE_UNKNOWN_CLIENT_VERSION], **kwargs,
        )

    if min_tuple is not None and app_tuple < min_tuple:
        return CompatibilityResult(
            state=STATE_UPDATE_REQUIRED, compatible=False, update_required=True,
            message=_STATE_MESSAGES[STATE_UPDATE_REQUIRED], **kwargs,
        )

    recommended_tuple = parse_version(recommended_mobile_version)
    if recommended_tuple is not None and app_tuple < recommended_tuple:
        return CompatibilityResult(
            state=STATE_UPDATE_RECOMMENDED, compatible=True, update_required=False,
            message=_STATE_MESSAGES[STATE_UPDATE_RECOMMENDED], **kwargs,
        )

    return CompatibilityResult(
        state=STATE_COMPATIBLE, compatible=True, update_required=False,
        message=_STATE_MESSAGES[STATE_COMPATIBLE], **kwargs,
    )
