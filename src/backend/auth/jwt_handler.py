"""
JWT Authentication Handler
Handles JWT token creation, verification, and user authentication
"""

import jwt
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from ..config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """
    Handles JWT token operations for authentication
    """
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.expiration_hours = settings.JWT_EXPIRATION_HOURS
        
        logger.info(f"Initialized JWT handler with algorithm: {self.algorithm}")
    
    def create_access_token(self, user_id: str, email: str, role: str = "student") -> str:
        """
        Create a JWT access token
        
        Args:
            user_id: User's unique identifier
            email: User's email
            role: User's role (student/teacher)
        
        Returns:
            JWT token string
        """
        try:
            # Calculate expiration time
            expiration = datetime.now(timezone.utc) + timedelta(hours=self.expiration_hours)
            
            # Create payload
            payload = {
                "sub": user_id,  # Standard JWT claim for subject (user ID)
                "user_id": user_id,  # Keep for backwards compatibility
                "email": email,
                "role": role,
                "exp": expiration,
                "iat": datetime.now(timezone.utc),
                "type": "access"
            }
            
            # Encode token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Created access token for user: {email}")
            return token
        
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict or None if invalid
        """
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Verify token type
            if payload.get("type") != "access":
                logger.warning("Invalid token type")
                return None
            
            logger.debug(f"Verified token for user: {payload.get('email')}")
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, str]]:
        """
        Extract user information from token
        
        Args:
            token: JWT token string
        
        Returns:
            Dict with user_id, email, role or None
        """
        payload = self.verify_token(token)
        
        if not payload:
            return None
        
        return {
            "user_id": payload.get("sub") or payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role", "student")
        }
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to compare against
        
        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_refresh_token(self, user_id: str) -> str:
        """
        Create a refresh token (longer expiration)
        
        Args:
            user_id: User's unique identifier
        
        Returns:
            JWT refresh token string
        """
        try:
            # Refresh tokens last longer (30 days)
            expiration = datetime.now(timezone.utc) + timedelta(days=30)
            
            payload = {
                "sub": user_id,  # Standard JWT claim for subject (user ID)
                "user_id": user_id,  # Keep for backwards compatibility
                "exp": expiration,
                "iat": datetime.now(timezone.utc),
                "type": "refresh"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Created refresh token for user: {user_id}")
            return token
        
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise


# Global JWT handler instance
_jwt_handler: Optional[JWTHandler] = None


def get_jwt_handler() -> JWTHandler:
    """Get or create global JWT handler instance"""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler


# Convenience functions that use the global handler
def create_access_token(data: Dict[str, Any]) -> str:
    """Create an access token using the global JWT handler"""
    handler = get_jwt_handler()
    user_id = data.get("sub") or data.get("user_id")
    email = data.get("email", "")
    role = data.get("role", "student")
    return handler.create_access_token(user_id, email, role)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify an access token using the global JWT handler"""
    handler = get_jwt_handler()
    return handler.verify_token(token)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return JWTHandler.verify_password(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return JWTHandler.hash_password(password)

