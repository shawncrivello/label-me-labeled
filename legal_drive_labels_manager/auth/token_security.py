"""Security utilities for OAuth token storage and management."""

import os
import base64
import pickle
import logging
import platform
import getpass
from pathlib import Path
from typing import Any, Optional, Union

# Import cryptography if available
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class TokenSecurity:
    """
    Security manager for OAuth token storage.
    
    This class provides methods for securely storing and retrieving
    OAuth tokens, with optional encryption if the cryptography
    package is available.
    """

    def __init__(self, token_dir: Optional[Path] = None) -> None:
        """
        Initialize the token security manager.
        
        Args:
            token_dir: Optional directory for token storage
        """
        self.token_dir = token_dir
        if self.token_dir is not None:
            self.token_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_machine_id(self) -> str:
        """
        Get a unique identifier for the current machine.
        
        Returns:
            Machine identifier string
        """
        machine_id = ""
        
        # Try to get a unique machine identifier
        try:
            if platform.system() == "Windows":
                # On Windows, use the machine GUID
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Cryptography") as key:
                    machine_id = winreg.QueryValueEx(key, "MachineGuid")[0]
            elif platform.system() == "Darwin":
                # On macOS, use the hardware UUID
                import subprocess
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True, text=True, check=True
                )
                for line in result.stdout.splitlines():
                    if "IOPlatformUUID" in line:
                        machine_id = line.split('"')[-2]
                        break
            else:
                # On Linux, use machine-id
                machine_id_file = Path("/etc/machine-id")
                if machine_id_file.exists():
                    machine_id = machine_id_file.read_text().strip()
        except Exception as e:
            logger.warning(f"Could not get machine ID: {e}")
        
        # If we couldn't get a machine ID, fall back to hostname + username
        if not machine_id:
            machine_id = f"{platform.node()}-{getpass.getuser()}"
        
        return machine_id
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive an encryption key from machine-specific information.
        
        Args:
            salt: Salt for key derivation
            
        Returns:
            Derived key
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography package is not available")
        
        # Get a unique machine identifier
        machine_id = self._get_machine_id()
        
        # Create a PBKDF2HMAC key derivation function
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        # Derive a key from the machine ID
        key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
        
        return key
    
    def save_token(self, token: Any, token_path: Path) -> bool:
        """
        Save a token to a file, optionally with encryption.
        
        Args:
            token: Token to save
            token_path: Path to save the token
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize the token
            token_data = pickle.dumps(token)
            
            # Encrypt the token if cryptography is available
            if CRYPTO_AVAILABLE:
                try:
                    # Generate a random salt
                    salt = os.urandom(16)
                    
                    # Derive a key from the machine ID
                    key = self._derive_key(salt)
                    
                    # Create a Fernet cipher
                    cipher = Fernet(key)
                    
                    # Encrypt the token data
                    encrypted_data = cipher.encrypt(token_data)
                    
                    # Save the salt and encrypted data
                    with open(token_path, "wb") as f:
                        f.write(salt)
                        f.write(encrypted_data)
                    
                    logger.debug(f"Saved encrypted token to {token_path}")
                    return True
                except Exception as e:
                    logger.warning(f"Could not encrypt token: {e}")
                    logger.warning("Falling back to unencrypted storage")
            
            # If encryption failed or is not available, save unencrypted
            with open(token_path, "wb") as f:
                pickle.dump(token, f)
            
            logger.debug(f"Saved unencrypted token to {token_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving token: {e}")
            return False
    
    def load_token(self, token_path: Path) -> Optional[Any]:
        """
        Load a token from a file, handling encryption if necessary.
        
        Args:
            token_path: Path to the token file
            
        Returns:
            Token object or None if loading failed
        """
        if not token_path.exists():
            logger.debug(f"Token file not found: {token_path}")
            return None
        
        try:
            # Try to load as an encrypted token first
            if CRYPTO_AVAILABLE:
                try:
                    with open(token_path, "rb") as f:
                        # Read the salt (first 16 bytes)
                        salt = f.read(16)
                        
                        # Read the encrypted data
                        encrypted_data = f.read()
                    
                    if len(salt) == 16 and encrypted_data:
                        # Derive the key
                        key = self._derive_key(salt)
                        
                        # Create a Fernet cipher
                        cipher = Fernet(key)
                        
                        # Decrypt the data
                        token_data = cipher.decrypt(encrypted_data)
                        
                        # Deserialize the token
                        token = pickle.loads(token_data)
                        
                        logger.debug(f"Loaded encrypted token from {token_path}")
                        return token
                except Exception as e:
                    logger.debug(f"Could not decrypt token, trying unencrypted format: {e}")
            
            # If decryption failed or is not available, try loading unencrypted
            with open(token_path, "rb") as f:
                token = pickle.load(f)
            
            logger.debug(f"Loaded unencrypted token from {token_path}")
            return token
            
        except Exception as e:
            logger.error(f"Error loading token: {e}")
            return None
    
    def rotate_token(self, token_path: Path) -> bool:
        """
        Re-encrypt a token with a new key.
        
        Args:
            token_path: Path to the token file
            
        Returns:
            True if successful, False otherwise
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography package is not available, cannot rotate token")
            return False
        
        token = self.load_token(token_path)
        if token is None:
            return False
        
        return self.save_token(token, token_path)