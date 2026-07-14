"""Cache Vault Mobile — desktop bridge (read-only LAN API).

See docs/MOBILE_ANDROID_DIRECTION.md. Android app not included here.
"""

from .models import PairedDevice, hash_token

__all__ = ["PairedDevice", "hash_token"]

def __getattr__(name: str):
    if name == "MobileBridge":
        from .bridge import MobileBridge
        return MobileBridge
    if name == "MobileAccessController":
        from .mobile_access_controller import MobileAccessController
        return MobileAccessController
    if name == "relative_timestamp":
        from .mobile_access_controller import relative_timestamp
        return relative_timestamp
    raise AttributeError(name)
