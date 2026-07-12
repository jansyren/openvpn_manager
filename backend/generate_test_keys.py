"""Generate an RS256 test keypair for local/CI test runs.

Writes test_private.pem / test_public.pem next to this script (the backend
directory), so it works both inside the container and for local runs.
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_HERE = Path(__file__).resolve().parent

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

(_HERE / "test_private.pem").write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
)

(_HERE / "test_public.pem").write_bytes(
    key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)

print(f"Wrote test_private.pem and test_public.pem to {_HERE}")
