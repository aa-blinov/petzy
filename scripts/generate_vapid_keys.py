"""Generate a VAPID key pair for Web Push, printed ready to paste into .env.

Usage:
    python -m scripts.generate_vapid_keys
"""

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02 as Vapid

if __name__ == "__main__":
    vapid = Vapid()
    vapid.generate_keys()

    public_raw = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")

    public_b64 = base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode()
    private_b64 = base64.urlsafe_b64encode(private_raw).rstrip(b"=").decode()

    print("Add these to your .env:\n")
    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print(f"VAPID_PRIVATE_KEY={private_b64}")
    print("VAPID_CLAIMS_EMAIL=your-email@example.com")
