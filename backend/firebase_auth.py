"""Server-side verification of Firebase ID tokens.

Firebase ID tokens are ordinary RS256 JWTs signed by Google. Rather than pull
in the whole ``firebase-admin`` SDK — which would require provisioning and
storing a service-account private key — we verify them directly against
Google's published public keys.

That means the only configuration needed is ``FIREBASE_PROJECT_ID``, which is
not a secret (it already ships in the frontend bundle). No new credential has
to be created, stored or rotated.

Verification follows Google's documented requirements for ID tokens:
  * RS256, signed by a current securetoken@system key
  * ``aud``  == the Firebase project id
  * ``iss``  == https://securetoken.google.com/<project id>
  * ``exp`` in the future, ``iat`` in the past (PyJWT enforces both)
  * ``sub``  non-empty — this is the Firebase UID

If ``firebase-admin`` is ever preferred, swap out verify_id_token(); nothing
else in the codebase depends on how the check is performed.
"""

import logging
import os

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "").strip()

_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/"
    "securetoken@system.gserviceaccount.com"
)
_ISSUER_PREFIX = "https://securetoken.google.com/"

# PyJWKClient caches fetched signing keys, so this is one HTTP call per key
# rotation rather than one per login.
_jwk_client: PyJWKClient | None = None


class FirebaseAuthError(Exception):
    """Raised when an ID token is missing, malformed, expired or untrusted."""


def is_configured() -> bool:
    """False when FIREBASE_PROJECT_ID is unset, so callers can fall back."""
    return bool(FIREBASE_PROJECT_ID)


def _client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(_JWKS_URL, cache_keys=True)
    return _jwk_client


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its claims.

    Raises FirebaseAuthError on anything that is not a valid, current token
    issued for this project.
    """
    if not is_configured():
        raise FirebaseAuthError("Firebase sign-in is not configured on the server")
    if not id_token or not isinstance(id_token, str):
        raise FirebaseAuthError("Missing sign-in token")

    try:
        signing_key = _client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            issuer=f"{_ISSUER_PREFIX}{FIREBASE_PROJECT_ID}",
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise FirebaseAuthError("Your sign-in session expired. Please try again.") from exc
    except jwt.InvalidTokenError as exc:
        # Covers bad signature, wrong audience/issuer, malformed token.
        logger.warning("Rejected Firebase ID token: %s", exc)
        raise FirebaseAuthError("Could not verify your sign-in. Please try again.") from exc
    except Exception as exc:
        # Network failure reaching Google's JWKS endpoint, etc.
        logger.error("Firebase ID token verification failed: %s", exc)
        raise FirebaseAuthError("Sign-in service is temporarily unavailable.") from exc

    uid = (claims.get("sub") or "").strip()
    if not uid:
        raise FirebaseAuthError("Sign-in token is missing a user id")

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise FirebaseAuthError("This sign-in method did not provide an email address")

    return {
        "uid": uid,
        "email": email,
        "email_verified": bool(claims.get("email_verified")),
        "name": (claims.get("name") or "").strip() or None,
    }
