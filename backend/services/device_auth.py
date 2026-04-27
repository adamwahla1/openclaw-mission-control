"""OpenClaw Device Authentication Protocol.

Implements the full challenge-response-connect handshake per the
OpenClaw Gateway Protocol (v3 signature payloads).

Flow:
  1. Client opens WebSocket to gateway
  2. Gateway sends `connect.challenge` with a nonce
  3. Client signs v3 payload (includes nonce) with Ed25519 private key
  4. Client sends `connect` message with device identity + signature
  5. Gateway validates and responds with `connect.ok` (or error)

If no device identity exists, one is auto-generated.
"""
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────

def _resolve_openclaw_home() -> Path:
    """Resolve the OpenClaw home directory.

    Priority:
    1. OPENCLAW_HOME env var
    2. ~/.openclaw (standard)
    3. Auto-detect from device.json location
    """
    # Explicit env var
    env = os.environ.get("OPENCLAW_HOME")
    if env:
        return Path(env)

    # Standard location
    standard = Path.home() / ".openclaw"
    if (standard / "identity" / "device.json").exists():
        return standard

    # Auto-detect: search common paths
    import glob
    for p in glob.glob("/data/users/*/.openclaw", recursive=False):
        candidate = Path(p)
        if (candidate / "identity" / "device.json").exists():
            return candidate

    # Fallback to standard
    return standard


OPENCLAW_HOME = _resolve_openclaw_home()
DEVICE_IDENTITY_PATH = OPENCLAW_HOME / "identity" / "device.json"
DEVICE_AUTH_PATH = OPENCLAW_HOME / "identity" / "device-auth.json"
OPENCLAW_CONFIG_PATH = OPENCLAW_HOME / "openclaw.json"


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class DeviceIdentity:
    """Represents a device's cryptographic identity."""
    version: int = 1
    device_id: str = ""
    public_key_pem: str = ""
    private_key_pem: str = ""
    created_at_ms: int = 0

    # Lazy-loaded key objects
    _private_key: Optional[Ed25519PrivateKey] = field(default=None, repr=False)
    _public_key: Optional[Ed25519PublicKey] = field(default=None, repr=False)

    @property
    def private_key(self) -> Ed25519PrivateKey:
        if self._private_key is None:
            self._private_key = serialization.load_pem_private_key(
                self.private_key_pem.encode(), password=None,
            )
        return self._private_key

    @property
    def public_key(self) -> Ed25519PublicKey:
        if self._public_key is None:
            self._public_key = serialization.load_pem_public_key(
                self.public_key_pem.encode(),
            )
        return self._public_key

    @property
    def public_key_base64url(self) -> str:
        """Raw 32-byte Ed25519 public key, base64url-encoded (no PEM wrapper)."""
        raw = self.public_key.public_bytes(
            Encoding.Raw, PublicFormat.Raw,
        )
        return _base64url_encode(raw)

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceIdentity":
        return cls(
            version=d.get("version", 1),
            device_id=d["deviceId"],
            public_key_pem=d["publicKeyPem"],
            private_key_pem=d["privateKeyPem"],
            created_at_ms=d.get("createdAtMs", 0),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "deviceId": self.device_id,
            "publicKeyPem": self.public_key_pem,
            "privateKeyPem": self.private_key_pem,
            "createdAtMs": self.created_at_ms,
        }


@dataclass
class DeviceToken:
    """A stored auth token for a specific role."""
    token: str
    role: str
    scopes: list[str]
    updated_at_ms: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceToken":
        return cls(
            token=d["token"],
            role=d["role"],
            scopes=d.get("scopes", []),
            updated_at_ms=d.get("updatedAtMs", 0),
        )


@dataclass
class DeviceAuthState:
    """Stored device authentication state (tokens per role)."""
    version: int = 1
    device_id: str = ""
    tokens: dict[str, DeviceToken] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceAuthState":
        tokens = {}
        for role, td in d.get("tokens", {}).items():
            tokens[role] = DeviceToken.from_dict(td)
        return cls(
            version=d.get("version", 1),
            device_id=d.get("deviceId", ""),
            tokens=tokens,
        )


# ── Helpers ────────────────────────────────────────────────────────────────

def _base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(s: str) -> bytes:
    """Base64url decode with padding restoration."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _derive_device_id(public_key: Ed25519PublicKey) -> str:
    """Derive device ID from Ed25519 public key: SHA-256 of raw key bytes, hex-encoded."""
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def _normalize_metadata(value: str) -> str:
    """Normalize platform/deviceFamily for auth payload (lowercase, stripped)."""
    return value.strip().lower() if value else ""


# ── Signature Payload Construction ─────────────────────────────────────────

def build_v3_signature_payload(
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    signed_at_ms: int,
    token: str,
    nonce: str,
    platform: str,
    device_family: str,
) -> str:
    """Build the v3 signature payload string (pipe-delimited).

    Format: v3|deviceId|clientId|clientMode|role|scopes|signedAtMs|token|nonce|platform|deviceFamily
    """
    scopes_str = ",".join(sorted(scopes)) if scopes else ""
    token_str = token or ""
    nonce_str = nonce or ""
    plat = _normalize_metadata(platform)
    fam = _normalize_metadata(device_family)

    parts = [
        "v3",
        device_id,
        client_id,
        client_mode,
        role,
        scopes_str,
        str(signed_at_ms),
        token_str,
        nonce_str,
        plat,
        fam,
    ]
    return "|".join(parts)


def build_v2_signature_payload(
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    signed_at_ms: int,
    token: str,
    nonce: str,
) -> str:
    """Build the v2 signature payload string (pipe-delimited).

    Format: v2|deviceId|clientId|clientMode|role|scopes|signedAtMs|token|nonce
    """
    scopes_str = ",".join(sorted(scopes)) if scopes else ""
    token_str = token or ""
    nonce_str = nonce or ""

    parts = [
        "v2",
        device_id,
        client_id,
        client_mode,
        role,
        scopes_str,
        str(signed_at_ms),
        token_str,
        nonce_str,
    ]
    return "|".join(parts)


def sign_payload(private_key: Ed25519PrivateKey, payload: str) -> str:
    """Sign a payload string with Ed25519 private key, return base64url-encoded signature."""
    signature = private_key.sign(payload.encode("utf-8"))
    return _base64url_encode(signature)


# ── Identity Management ────────────────────────────────────────────────────

def generate_device_identity() -> DeviceIdentity:
    """Generate a new Ed25519 device identity."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    device_id = _derive_device_id(public_key)
    public_key_pem = public_key.public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    private_key_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption(),
    ).decode("ascii")

    identity = DeviceIdentity(
        version=1,
        device_id=device_id,
        public_key_pem=public_key_pem,
        private_key_pem=private_key_pem,
        created_at_ms=int(time.time() * 1000),
    )
    # Pre-load keys
    identity._private_key = private_key
    identity._public_key = public_key

    return identity


def save_device_identity(identity: DeviceIdentity, path: Path = DEVICE_IDENTITY_PATH) -> None:
    """Persist device identity to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write with restricted permissions
    path.write_text(json.dumps(identity.to_dict(), indent=2))
    os.chmod(path, 0o600)
    logger.info(f"Device identity saved to {path}")


def load_device_identity(path: Path = DEVICE_IDENTITY_PATH) -> Optional[DeviceIdentity]:
    """Load device identity from disk, or None if not found."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return DeviceIdentity.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load device identity from {path}: {e}")
        return None


def load_device_auth(path: Path = DEVICE_AUTH_PATH) -> Optional[DeviceAuthState]:
    """Load stored device auth state (tokens) from disk."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return DeviceAuthState.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load device auth from {path}: {e}")
        return None


def save_device_auth(auth: DeviceAuthState, path: Path = DEVICE_AUTH_PATH) -> None:
    """Persist device auth state to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tokens_dict = {}
    for role, tok in auth.tokens.items():
        tokens_dict[role] = {
            "token": tok.token,
            "role": tok.role,
            "scopes": tok.scopes,
            "updatedAtMs": tok.updated_at_ms,
        }
    data = {
        "version": auth.version,
        "deviceId": auth.device_id,
        "tokens": tokens_dict,
    }
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)
    logger.info(f"Device auth state saved to {path}")


def load_gateway_config(path: Path = OPENCLAW_CONFIG_PATH) -> dict:
    """Load the OpenClaw gateway config file."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


# ── Connect Message Builder ───────────────────────────────────────────────

def build_connect_message(
    identity: DeviceIdentity,
    nonce: str,
    role: str = "operator",
    scopes: list[str] | None = None,
    client_id: str = "cli",
    client_version: str = "0.1.0",
    platform: str = "linux",
    device_family: str = "desktop",
    stored_token: str = "",
    protocol_version: int = 3,
    client_mode: str = "cli",
) -> dict:
    """Build a complete `connect` RPC message with v3 device auth.

    Args:
        identity: Device cryptographic identity
        nonce: Server-provided nonce from connect.challenge
        role: Connection role (operator/node)
        scopes: Requested scopes
        client_id: Client identifier (must match gateway allowlist: "cli")
        client_version: Client version string
        platform: Platform identifier (linux/macos/windows)
        device_family: Device family (desktop/mobile)
        stored_token: Previously issued device token (if any)
        protocol_version: Protocol version (2 or 3)
        client_mode: Client mode (must match gateway allowlist: "cli")

    Returns:
        Complete connect RPC message dict
    """
    if scopes is None:
        scopes = ["operator.read", "operator.write"]

    signed_at_ms = int(time.time() * 1000)

    # Build signature payload
    if protocol_version >= 3:
        payload_str = build_v3_signature_payload(
            device_id=identity.device_id,
            client_id=client_id,
            client_mode=client_mode,
            role=role,
            scopes=scopes,
            signed_at_ms=signed_at_ms,
            token=stored_token,
            nonce=nonce,
            platform=platform,
            device_family=device_family,
        )
    else:
        payload_str = build_v2_signature_payload(
            device_id=identity.device_id,
            client_id=client_id,
            client_mode=client_mode,
            role=role,
            scopes=scopes,
            signed_at_ms=signed_at_ms,
            token=stored_token,
            nonce=nonce,
        )

    signature = sign_payload(identity.private_key, payload_str)

    msg = {
        "type": "req",
        "id": str(uuid.uuid4()),
        "method": "connect",
        "params": {
            "minProtocol": protocol_version,
            "maxProtocol": protocol_version,
            "client": {
                "id": client_id,
                "version": client_version,
                "platform": _normalize_metadata(platform),
                "deviceFamily": _normalize_metadata(device_family),
                "mode": client_mode,
            },
            "role": role,
            "scopes": scopes,
            "device": {
                "id": identity.device_id,
                "publicKey": identity.public_key_base64url,
                "signature": signature,
                "signedAt": signed_at_ms,
                "nonce": nonce,
            },
        },
    }

    # Include stored token if available
    if stored_token:
        msg["params"]["auth"] = {"token": stored_token}

    return msg


# ── DeviceAuthManager ──────────────────────────────────────────────────────

class DeviceAuthManager:
    """Manages device identity, tokens, and auth lifecycle."""

    def __init__(self):
        self.identity: Optional[DeviceIdentity] = None
        self.auth_state: Optional[DeviceAuthState] = None
        self.gateway_config: dict = {}
        self._initialized = False

    def initialize(self) -> None:
        """Load or generate device identity and auth state."""
        if self._initialized:
            return

        # Load or generate device identity
        self.identity = load_device_identity()
        if self.identity is None:
            logger.info("No device identity found, generating new one...")
            self.identity = generate_device_identity()
            save_device_identity(self.identity)

        # Load stored auth tokens
        self.auth_state = load_device_auth()
        if self.auth_state is None:
            self.auth_state = DeviceAuthState(
                version=1,
                device_id=self.identity.device_id,
            )
            save_device_auth(self.auth_state)

        # Load gateway config
        self.gateway_config = load_gateway_config()

        self._initialized = True
        logger.info(
            f"Device auth initialized: deviceId={self.identity.device_id[:16]}..."
        )

    @property
    def device_id(self) -> str:
        if self.identity is None:
            self.initialize()
        return self.identity.device_id  # type: ignore

    @property
    def operator_token(self) -> str:
        """Get the stored operator token, if any."""
        if self.auth_state and "operator" in self.auth_state.tokens:
            return self.auth_state.tokens["operator"].token
        return ""

    @property
    def operator_scopes(self) -> list[str]:
        """Get the stored operator scopes."""
        if self.auth_state and "operator" in self.auth_state.tokens:
            return self.auth_state.tokens["operator"].scopes
        return []

    def get_gateway_url(self) -> str:
        """Get gateway WebSocket URL from config or default."""
        gw_config = self.gateway_config.get("gateway", {})
        bind = gw_config.get("bind", "loopback")

        # Check for explicit URL in env/config
        env_url = os.environ.get("MC_GATEWAY_URL", "")
        if env_url:
            return env_url

        # Default based on bind mode
        if bind == "loopback":
            return "ws://127.0.0.1:18789"
        return "ws://127.0.0.1:18789"

    def get_gateway_token(self) -> str:
        """Get gateway auth token from config."""
        gw_config = self.gateway_config.get("gateway", {})
        return gw_config.get("auth", {}).get("token", "")

    def get_auth_mode(self) -> str:
        """Get gateway auth mode from config."""
        gw_config = self.gateway_config.get("gateway", {})
        return gw_config.get("auth", {}).get("mode", "none")

    def update_operator_token(self, token: str, scopes: list[str]) -> None:
        """Update the stored operator token after successful connect."""
        if self.auth_state is None:
            self.auth_state = DeviceAuthState(device_id=self.device_id)

        self.auth_state.tokens["operator"] = DeviceToken(
            token=token,
            role="operator",
            scopes=scopes,
            updated_at_ms=int(time.time() * 1000),
        )
        save_device_auth(self.auth_state)
        logger.info(f"Operator token updated (scopes: {scopes})")

    def build_connect(
        self,
        nonce: str,
        role: str = "operator",
        scopes: list[str] | None = None,
        token_override: str | None = None,
    ) -> dict:
        """Build a connect message using stored identity and tokens.

        Args:
            nonce: Server challenge nonce
            role: Connection role
            scopes: Requested scopes
            token_override: Override the token used in the signature payload.
                Must match auth.token for signature verification to pass.
        """
        if self.identity is None:
            self.initialize()

        # Use stored scopes if none provided and we have them
        if scopes is None:
            if self.operator_scopes:
                scopes = self.operator_scopes
            else:
                scopes = ["operator.read", "operator.write"]

        # The token in the signature must match auth.token
        sig_token = token_override if token_override is not None else self.operator_token

        return build_connect_message(
            identity=self.identity,  # type: ignore
            nonce=nonce,
            role=role,
            scopes=scopes,
            client_id="cli",
            client_version="0.1.0",
            platform="linux",
            device_family="desktop",
            stored_token=sig_token,
            protocol_version=3,
        )

    def status(self) -> dict:
        """Return current device auth status for diagnostics."""
        return {
            "device_id": self.device_id if self.identity else None,
            "has_identity": self.identity is not None,
            "has_operator_token": bool(self.operator_token),
            "operator_scopes": self.operator_scopes,
            "gateway_auth_mode": self.get_auth_mode(),
            "gateway_url": self.get_gateway_url(),
        }


# Singleton
device_auth = DeviceAuthManager()
