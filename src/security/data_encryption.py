"""
TMWS Data Encryption System
Hestia's Paranoid Data Protection Implementation

This module provides comprehensive data encryption for TMWS:
- At-rest encryption for memory data
- In-transit encryption for agent communications
- Field-level encryption for sensitive data
- Key rotation and management
- Secure key derivation and storage
"""

import os
import base64
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
import asyncio
import logging

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import argon2

logger = logging.getLogger(__name__)


class EncryptionLevel(Enum):
    """Data encryption levels based on sensitivity."""
    NONE = "none"              # Public data
    BASIC = "basic"            # Standard symmetric encryption
    ENHANCED = "enhanced"      # Key rotation + stronger algorithms
    MAXIMUM = "maximum"        # Multi-layer encryption + HSM keys
    QUANTUM_SAFE = "quantum_safe"  # Post-quantum cryptography


class DataClassification(Enum):
    """Data classification for encryption policy."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class EncryptionKeyManager:
    """Secure key management and rotation system."""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or self._generate_master_key()
        self.key_cache: Dict[str, Tuple[bytes, datetime]] = {}
        self.key_rotation_interval = timedelta(days=30)
        
        # Argon2 for key derivation (memory-hard, resistant to GPU attacks)
        self.password_hasher = argon2.PasswordHasher(
            time_cost=3,      # Number of iterations
            memory_cost=65536, # Memory usage in KiB (64 MB)
            parallelism=1,    # Number of parallel threads
            hash_len=32,      # Length of hash in bytes
            salt_len=16       # Length of salt in bytes
        )
    
    def _generate_master_key(self) -> str:
        """Generate cryptographically secure master key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
    
    def derive_key(
        self, 
        context: str, 
        agent_id: str,
        key_purpose: str = "data_encryption"
    ) -> bytes:
        """
        Derive encryption key for specific context and agent.
        
        Uses HKDF (HMAC-based Key Derivation Function) for secure key derivation.
        """
        cache_key = f"{context}:{agent_id}:{key_purpose}"
        
        # Check cache first (with expiry)
        if cache_key in self.key_cache:
            key, created_at = self.key_cache[cache_key]
            if datetime.utcnow() - created_at < self.key_rotation_interval:
                return key
            else:
                # Remove expired key
                del self.key_cache[cache_key]
        
        # Derive new key
        salt = hashlib.sha256(f"{context}:{agent_id}:{key_purpose}".encode()).digest()
        
        # Use Scrypt for memory-hard key derivation
        kdf = Scrypt(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            n=2**14,  # CPU/memory cost parameter
            r=8,      # Block size parameter
            p=1,      # Parallelization parameter
            backend=default_backend()
        )
        
        derived_key = kdf.derive(self.master_key.encode())
        
        # Cache the key
        self.key_cache[cache_key] = (derived_key, datetime.utcnow())
        
        return derived_key
    
    def rotate_keys(self, force: bool = False) -> Dict[str, Any]:
        """Rotate encryption keys."""
        rotated_keys = []
        
        for cache_key, (key, created_at) in list(self.key_cache.items()):
            should_rotate = (
                force or 
                datetime.utcnow() - created_at > self.key_rotation_interval
            )
            
            if should_rotate:
                # Generate new key
                context, agent_id, purpose = cache_key.split(':', 2)
                new_key = self.derive_key(context, agent_id, purpose)
                
                rotated_keys.append({
                    "key_id": cache_key,
                    "rotated_at": datetime.utcnow().isoformat(),
                    "old_key_hash": hashlib.sha256(key).hexdigest()[:16]
                })
        
        logger.info(f"Rotated {len(rotated_keys)} encryption keys")
        return {"rotated_keys": rotated_keys}
    
    def get_key_info(self) -> Dict[str, Any]:
        """Get information about managed keys."""
        return {
            "total_keys": len(self.key_cache),
            "rotation_interval_days": self.key_rotation_interval.days,
            "keys_due_rotation": sum(
                1 for _, (_, created) in self.key_cache.items()
                if datetime.utcnow() - created > self.key_rotation_interval
            )
        }


class FieldEncryption:
    """Field-level encryption for sensitive data."""
    
    def __init__(self, key_manager: EncryptionKeyManager):
        self.key_manager = key_manager
        self.encryption_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def encrypt_field(
        self,
        data: Union[str, bytes, Dict, List],
        field_name: str,
        agent_id: str,
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> Dict[str, Any]:
        """
        Encrypt individual field with metadata.
        
        Returns:
            dict: Contains encrypted data and metadata for decryption
        """
        # Convert data to bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
            data_type = "string"
        elif isinstance(data, bytes):
            data_bytes = data
            data_type = "bytes"
        elif isinstance(data, (dict, list)):
            data_bytes = json.dumps(data).encode('utf-8')
            data_type = "json"
        else:
            data_bytes = str(data).encode('utf-8')
            data_type = "string"
        
        # Derive encryption key
        context = f"field:{field_name}:{classification.value}"
        encryption_key = self.key_manager.derive_key(context, agent_id)
        
        # Create Fernet cipher
        fernet = Fernet(base64.urlsafe_b64encode(encryption_key))
        
        # Encrypt data
        encrypted_data = fernet.encrypt(data_bytes)
        
        # Create metadata
        metadata = {
            "encrypted_at": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "field_name": field_name,
            "data_type": data_type,
            "classification": classification.value,
            "encryption_version": "1.0",
            "key_context": context
        }
        
        # Store metadata for decryption
        field_id = hashlib.sha256(f"{agent_id}:{field_name}:{metadata['encrypted_at']}".encode()).hexdigest()[:16]
        self.encryption_metadata[field_id] = metadata
        
        return {
            "field_id": field_id,
            "encrypted_data": base64.urlsafe_b64encode(encrypted_data).decode('utf-8'),
            "metadata": metadata
        }
    
    async def decrypt_field(
        self,
        encrypted_field: Dict[str, Any],
        requesting_agent: str
    ) -> Union[str, bytes, Dict, List]:
        """
        Decrypt field data with access control.
        
        Args:
            encrypted_field: Result from encrypt_field()
            requesting_agent: Agent requesting decryption
            
        Returns:
            Decrypted data in original format
        """
        field_id = encrypted_field["field_id"]
        metadata = encrypted_field["metadata"]
        encrypted_data = base64.urlsafe_b64decode(encrypted_field["encrypted_data"])
        
        # Access control check
        if metadata["agent_id"] != requesting_agent:
            # TODO: Implement cross-agent access policies
            logger.warning(f"Agent {requesting_agent} attempted to decrypt data owned by {metadata['agent_id']}")
            raise PermissionError("Access denied: Cannot decrypt data from different agent")
        
        # Derive decryption key
        encryption_key = self.key_manager.derive_key(
            metadata["key_context"],
            metadata["agent_id"]
        )
        
        # Decrypt
        fernet = Fernet(base64.urlsafe_b64encode(encryption_key))
        decrypted_bytes = fernet.decrypt(encrypted_data)
        
        # Convert back to original type
        data_type = metadata["data_type"]
        if data_type == "string":
            return decrypted_bytes.decode('utf-8')
        elif data_type == "bytes":
            return decrypted_bytes
        elif data_type == "json":
            return json.loads(decrypted_bytes.decode('utf-8'))
        else:
            return decrypted_bytes.decode('utf-8')


class MemoryEncryption:
    """Specialized encryption for TMWS memory data."""
    
    def __init__(self, key_manager: EncryptionKeyManager):
        self.key_manager = key_manager
        self.field_encryption = FieldEncryption(key_manager)
    
    async def encrypt_memory(
        self,
        memory_data: Dict[str, Any],
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Encrypt sensitive memory fields.
        
        Encrypts:
        - content (memory content)
        - metadata (if contains sensitive info)
        - embeddings (if present)
        """
        encrypted_memory = memory_data.copy()
        
        # Encrypt main content
        if "content" in memory_data and memory_data["content"]:
            encrypted_content = await self.field_encryption.encrypt_field(
                memory_data["content"],
                "content",
                agent_id,
                DataClassification.CONFIDENTIAL
            )
            encrypted_memory["encrypted_content"] = encrypted_content
            encrypted_memory.pop("content", None)  # Remove plaintext
        
        # Encrypt sensitive metadata
        if "metadata" in memory_data:
            metadata = memory_data["metadata"]
            sensitive_keys = ["notes", "internal_data", "debug_info"]
            
            for key in sensitive_keys:
                if key in metadata:
                    encrypted_meta = await self.field_encryption.encrypt_field(
                        metadata[key],
                        f"metadata_{key}",
                        agent_id,
                        DataClassification.INTERNAL
                    )
                    if "encrypted_metadata" not in encrypted_memory:
                        encrypted_memory["encrypted_metadata"] = {}
                    encrypted_memory["encrypted_metadata"][key] = encrypted_meta
                    metadata.pop(key, None)
        
        # Encrypt embeddings if present
        if "embeddings" in memory_data and memory_data["embeddings"]:
            encrypted_embeddings = await self.field_encryption.encrypt_field(
                memory_data["embeddings"],
                "embeddings",
                agent_id,
                DataClassification.INTERNAL
            )
            encrypted_memory["encrypted_embeddings"] = encrypted_embeddings
            encrypted_memory.pop("embeddings", None)
        
        # Add encryption markers
        encrypted_memory["is_encrypted"] = True
        encrypted_memory["encryption_timestamp"] = datetime.utcnow().isoformat()
        
        return encrypted_memory
    
    async def decrypt_memory(
        self,
        encrypted_memory: Dict[str, Any],
        requesting_agent: str
    ) -> Dict[str, Any]:
        """Decrypt memory data for authorized agent."""
        if not encrypted_memory.get("is_encrypted", False):
            return encrypted_memory  # Already decrypted or never encrypted
        
        decrypted_memory = encrypted_memory.copy()
        
        # Decrypt main content
        if "encrypted_content" in encrypted_memory:
            content = await self.field_encryption.decrypt_field(
                encrypted_memory["encrypted_content"],
                requesting_agent
            )
            decrypted_memory["content"] = content
            decrypted_memory.pop("encrypted_content", None)
        
        # Decrypt metadata
        if "encrypted_metadata" in encrypted_memory:
            if "metadata" not in decrypted_memory:
                decrypted_memory["metadata"] = {}
            
            for key, encrypted_field in encrypted_memory["encrypted_metadata"].items():
                decrypted_value = await self.field_encryption.decrypt_field(
                    encrypted_field,
                    requesting_agent
                )
                decrypted_memory["metadata"][key] = decrypted_value
            
            decrypted_memory.pop("encrypted_metadata", None)
        
        # Decrypt embeddings
        if "encrypted_embeddings" in encrypted_memory:
            embeddings = await self.field_encryption.decrypt_field(
                encrypted_memory["encrypted_embeddings"],
                requesting_agent
            )
            decrypted_memory["embeddings"] = embeddings
            decrypted_memory.pop("encrypted_embeddings", None)
        
        # Remove encryption markers
        decrypted_memory.pop("is_encrypted", None)
        decrypted_memory.pop("encryption_timestamp", None)
        
        return decrypted_memory


class TransportEncryption:
    """End-to-end encryption for agent communications."""
    
    def __init__(self):
        # Generate ephemeral keys for session
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()
        
        self.peer_keys: Dict[str, rsa.RSAPublicKey] = {}
    
    def get_public_key_pem(self) -> str:
        """Get public key for key exchange."""
        return self._public_key.serialize(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def add_peer_key(self, agent_id: str, public_key_pem: str):
        """Add peer's public key for secure communication."""
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        self.peer_keys[agent_id] = public_key
    
    async def encrypt_message(
        self,
        message: Dict[str, Any],
        recipient_agent: str
    ) -> Dict[str, Any]:
        """Encrypt message for specific recipient agent."""
        if recipient_agent not in self.peer_keys:
            raise ValueError(f"No public key available for agent {recipient_agent}")
        
        # Serialize message
        message_bytes = json.dumps(message).encode('utf-8')
        
        # Generate symmetric key for this message
        symmetric_key = secrets.token_bytes(32)
        
        # Encrypt message with symmetric key
        fernet = Fernet(base64.urlsafe_b64encode(symmetric_key))
        encrypted_message = fernet.encrypt(message_bytes)
        
        # Encrypt symmetric key with recipient's public key
        recipient_public_key = self.peer_keys[recipient_agent]
        encrypted_key = recipient_public_key.encrypt(
            symmetric_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return {
            "encrypted_message": base64.urlsafe_b64encode(encrypted_message).decode('utf-8'),
            "encrypted_key": base64.urlsafe_b64encode(encrypted_key).decode('utf-8'),
            "timestamp": datetime.utcnow().isoformat(),
            "recipient": recipient_agent
        }
    
    async def decrypt_message(
        self,
        encrypted_envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Decrypt received message."""
        # Decrypt symmetric key with our private key
        encrypted_key = base64.urlsafe_b64decode(encrypted_envelope["encrypted_key"])
        symmetric_key = self._private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt message with symmetric key
        encrypted_message = base64.urlsafe_b64decode(encrypted_envelope["encrypted_message"])
        fernet = Fernet(base64.urlsafe_b64encode(symmetric_key))
        decrypted_bytes = fernet.decrypt(encrypted_message)
        
        # Parse message
        message = json.loads(decrypted_bytes.decode('utf-8'))
        
        return message


class EncryptionService:
    """Main encryption service orchestrator."""
    
    def __init__(self, master_key: Optional[str] = None):
        self.key_manager = EncryptionKeyManager(master_key)
        self.field_encryption = FieldEncryption(self.key_manager)
        self.memory_encryption = MemoryEncryption(self.key_manager)
        self.transport_encryption = TransportEncryption()
        
        # Encryption policies by data classification
        self.encryption_policies = {
            DataClassification.PUBLIC: EncryptionLevel.NONE,
            DataClassification.INTERNAL: EncryptionLevel.BASIC,
            DataClassification.CONFIDENTIAL: EncryptionLevel.ENHANCED,
            DataClassification.RESTRICTED: EncryptionLevel.MAXIMUM,
            DataClassification.TOP_SECRET: EncryptionLevel.QUANTUM_SAFE
        }
    
    def get_encryption_level(self, classification: DataClassification) -> EncryptionLevel:
        """Get required encryption level for data classification."""
        return self.encryption_policies.get(classification, EncryptionLevel.BASIC)
    
    async def encrypt_agent_data(
        self,
        data: Dict[str, Any],
        data_type: str,
        agent_id: str,
        classification: DataClassification = DataClassification.CONFIDENTIAL
    ) -> Dict[str, Any]:
        """
        Encrypt agent data based on type and classification.
        
        Args:
            data: Data to encrypt
            data_type: Type of data (memory, task, workflow, etc.)
            agent_id: Owner agent ID
            classification: Data sensitivity classification
            
        Returns:
            Encrypted data structure
        """
        encryption_level = self.get_encryption_level(classification)
        
        if encryption_level == EncryptionLevel.NONE:
            return data  # No encryption needed
        
        if data_type == "memory":
            return await self.memory_encryption.encrypt_memory(data, agent_id)
        else:
            # Generic field-level encryption
            encrypted_fields = {}
            for field_name, field_value in data.items():
                if field_value and not field_name.startswith("_"):  # Skip private/system fields
                    encrypted_field = await self.field_encryption.encrypt_field(
                        field_value,
                        field_name,
                        agent_id,
                        classification
                    )
                    encrypted_fields[f"encrypted_{field_name}"] = encrypted_field
                else:
                    encrypted_fields[field_name] = field_value
            
            return encrypted_fields
    
    async def decrypt_agent_data(
        self,
        encrypted_data: Dict[str, Any],
        data_type: str,
        requesting_agent: str
    ) -> Dict[str, Any]:
        """Decrypt agent data with access control."""
        if data_type == "memory":
            return await self.memory_encryption.decrypt_memory(
                encrypted_data,
                requesting_agent
            )
        else:
            # Generic field-level decryption
            decrypted_data = {}
            for field_name, field_value in encrypted_data.items():
                if field_name.startswith("encrypted_"):
                    original_field_name = field_name[10:]  # Remove "encrypted_" prefix
                    decrypted_value = await self.field_encryption.decrypt_field(
                        field_value,
                        requesting_agent
                    )
                    decrypted_data[original_field_name] = decrypted_value
                else:
                    decrypted_data[field_name] = field_value
            
            return decrypted_data
    
    async def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption system statistics."""
        key_info = self.key_manager.get_key_info()
        
        return {
            "key_management": key_info,
            "encryption_policies": {
                cls.value: level.value 
                for cls, level in self.encryption_policies.items()
            },
            "transport_encryption": {
                "peer_keys_count": len(self.transport_encryption.peer_keys),
                "public_key_available": True
            },
            "field_encryption": {
                "metadata_entries": len(self.field_encryption.encryption_metadata)
            }
        }


# Factory function
def create_encryption_service(master_key: Optional[str] = None) -> EncryptionService:
    """Create configured encryption service."""
    return EncryptionService(master_key)


__all__ = [
    "EncryptionLevel",
    "DataClassification",
    "EncryptionKeyManager",
    "FieldEncryption", 
    "MemoryEncryption",
    "TransportEncryption",
    "EncryptionService",
    "create_encryption_service"
]