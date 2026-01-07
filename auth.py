import logging
from typing import Optional

import requests
from fastapi import HTTPException, Request
from jose import JWTError, jwt

from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


def get_public_key(key_id: str) -> Optional[str]:
    """Get public key from ALB public keys endpoint"""
    try:
        public_key_url = f"https://public-keys.auth.elb.{Config.COGNITO_REGION}.amazonaws.com/{key_id}"
        logger.debug(f"Fetching public key from: {public_key_url}")
        response = requests.get(public_key_url, timeout=10)
        response.raise_for_status()
        public_key = response.text
        logger.debug(f"Public key fetched successfully for key ID: {key_id}")
        return public_key
    except requests.RequestException as e:
        logger.error(f"Failed to fetch public key for {key_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to get public key for {key_id}: {e}")
        return None


def verify_cognito_token(request: Request) -> Optional[dict]:
    """Extract and verify Cognito JWT token from ALB headers"""

    # Debug: Log all headers
    logger.debug(f"Request headers: {dict(request.headers)}")

    # ALB passes the JWT token in this header
    token = request.headers.get("x-amzn-oidc-data")
    if not token:
        logger.warning("No x-amzn-oidc-data header found")
        return None

    logger.debug(f"Found JWT token: {token[:50]}...")

    try:
        # Decode header to get kid, client, and iss
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            client = unverified_header.get("client")
            iss = unverified_header.get("iss")
            signer = unverified_header.get("signer")
            logger.debug(
                f"Token kid: {kid}, client: {client}, iss: {iss}, signer: {signer}"
            )

            # Verify client ID
            if client != Config.COGNITO_CLIENT_ID:
                logger.error(
                    f"Client ID mismatch. Expected: {Config.COGNITO_CLIENT_ID}, Got: {client}"
                )
                return None

            # Verify issuer
            expected_iss = f"https://cognito-idp.{Config.COGNITO_REGION}.amazonaws.com/{Config.COGNITO_USER_POOL_ID}"
            if iss != expected_iss:
                logger.error(f"Issuer mismatch. Expected: {expected_iss}, Got: {iss}")
                return None

        except Exception as e:
            logger.error(f"Failed to decode JWT header: {e}")
            return None

        # Get public key for the kid
        public_key = get_public_key(kid)
        if not public_key:
            logger.error(f"Failed to get public key for kid: {kid}")
            return None

        # Verify and decode token (ALB uses ES256)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[Config.JWT_ALGORITHM],
            options={"verify_aud": False, "verify_iss": False},
        )

        logger.debug(
            f"Token verified successfully for user: {payload.get('email', 'unknown')}"
        )
        return payload

    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in token verification: {e}", exc_info=True)
        return None


def get_current_user(request: Request) -> dict:
    """Get current authenticated user or raise 401"""
    if Config.DISABLE_AUTH:
        logger.debug("Authentication disabled - returning mock user")
        return {
            "name": "Local User",
            "email": "local@example.com",
            "given_name": "Local",
            "family_name": "User",
        }

    logger.debug("Attempting to get current user")
    user = verify_cognito_token(request)
    if not user:
        logger.warning("Authentication failed - no valid user found")
        raise HTTPException(status_code=401, detail="Authentication required")
    logger.debug(f"User authenticated: {user.get('email', 'unknown')}")
    return user
