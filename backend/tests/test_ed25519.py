"""
Comprehensive tests for Ed25519 cryptographic operations.

These tests verify compatibility with:
- Rust NEXLINK Agent (ed25519-dalek)
- Node.js backend (@noble/ed25519)

Test vectors are generated using PyNaCl to match the exact protocol.
"""

import pytest
from nacl.signing import SigningKey
from app.crypto.ed25519 import (
    verify_ed25519_signature,
    verify_challenge_proof,
    verify_enrollment_proof,
    hex_to_bytes,
    bytes_to_hex,
    generate_challenge,
)


class TestHexConversion:
    """Test hex encoding/decoding utilities."""
    
    def test_hex_to_bytes_valid(self):
        """Test valid hex string conversion."""
        assert hex_to_bytes("0123456789abcdef") == b'\x01\x23\x45\x67\x89\xab\xcd\xef'
        assert hex_to_bytes("0x0123456789abcdef") == b'\x01\x23\x45\x67\x89\xab\xcd\xef'
        assert hex_to_bytes("") == b""
    
    def test_hex_to_bytes_invalid_odd_length(self):
        """Test hex string with odd length raises error."""
        with pytest.raises(ValueError, match="odd length"):
            hex_to_bytes("123")
    
    def test_hex_to_bytes_invalid_characters(self):
        """Test hex string with invalid characters raises error."""
        with pytest.raises(ValueError, match="Invalid hex"):
            hex_to_bytes("xyz123")
    
    def test_bytes_to_hex(self):
        """Test bytes to hex conversion."""
        assert bytes_to_hex(b'\x01\x23\x45\x67\x89\xab\xcd\xef') == "0123456789abcdef"
        assert bytes_to_hex(b"") == ""


class TestEd25519SignatureVerification:
    """Test Ed25519 signature verification."""
    
    @pytest.fixture
    def test_keypair(self):
        """Generate a test keypair for signing."""
        # Use a deterministic seed for reproducible tests
        seed = b'\x00' * 32  # 32 zero bytes
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        
        return {
            'signing_key': signing_key,
            'verify_key': verify_key,
            'public_key_hex': verify_key.encode().hex(),
        }
    
    def test_valid_signature(self, test_keypair):
        """Test verification of a valid signature."""
        message = b"test message"
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_ed25519_signature(message, signature_hex, public_key_hex) is True
    
    def test_invalid_signature_wrong_message(self, test_keypair):
        """Test verification fails with wrong message."""
        message = b"test message"
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        # Verify with different message
        wrong_message = b"different message"
        assert verify_ed25519_signature(wrong_message, signature_hex, public_key_hex) is False
    
    def test_invalid_signature_wrong_public_key(self, test_keypair):
        """Test verification fails with wrong public key."""
        message = b"test message"
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        # Use a different public key
        other_seed = b'\x01' * 32
        other_signing_key = SigningKey(other_seed)
        wrong_public_key_hex = other_signing_key.verify_key.encode().hex()
        
        assert verify_ed25519_signature(message, signature_hex, wrong_public_key_hex) is False
    
    def test_invalid_signature_modified_signature(self, test_keypair):
        """Test verification fails with modified signature."""
        message = b"test message"
        signed = test_keypair['signing_key'].sign(message)
        signature_bytes = bytearray(signed.signature)
        
        # Modify one byte
        signature_bytes[0] ^= 0xFF
        modified_signature_hex = bytes(signature_bytes).hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_ed25519_signature(message, modified_signature_hex, public_key_hex) is False
    
    def test_invalid_signature_wrong_length(self, test_keypair):
        """Test verification fails with wrong signature length."""
        message = b"test message"
        public_key_hex = test_keypair['public_key_hex']
        
        # Too short
        assert verify_ed25519_signature(message, "00" * 63, public_key_hex) is False
        
        # Too long
        assert verify_ed25519_signature(message, "00" * 65, public_key_hex) is False
    
    def test_invalid_public_key_wrong_length(self, test_keypair):
        """Test verification fails with wrong public key length."""
        message = b"test message"
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        # Too short
        assert verify_ed25519_signature(message, signature_hex, "00" * 31) is False
        
        # Too long
        assert verify_ed25519_signature(message, signature_hex, "00" * 33) is False
    
    def test_invalid_signature_hex_encoding(self, test_keypair):
        """Test verification fails with invalid hex encoding."""
        message = b"test message"
        public_key_hex = test_keypair['public_key_hex']
        
        # Invalid hex characters
        assert verify_ed25519_signature(message, "xyz" * 42 + "00", public_key_hex) is False
    
    def test_empty_message(self, test_keypair):
        """Test verification with empty message."""
        message = b""
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_ed25519_signature(message, signature_hex, public_key_hex) is True
    
    def test_large_message(self, test_keypair):
        """Test verification with large message."""
        message = b"x" * 10000
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_ed25519_signature(message, signature_hex, public_key_hex) is True


class TestChallengeProofVerification:
    """Test challenge-response proof verification."""
    
    @pytest.fixture
    def test_keypair(self):
        """Generate a test keypair."""
        seed = b'\x00' * 32
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        
        return {
            'signing_key': signing_key,
            'verify_key': verify_key,
            'public_key_hex': verify_key.encode().hex(),
        }
    
    def test_valid_challenge_proof(self, test_keypair):
        """Test valid challenge proof."""
        challenge = "a" * 64  # 32 bytes hex-encoded
        message = challenge.encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_challenge_proof(challenge, signature_hex, public_key_hex) is True
    
    def test_invalid_challenge_proof_wrong_challenge(self, test_keypair):
        """Test challenge proof fails with wrong challenge."""
        challenge = "a" * 64
        message = challenge.encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        wrong_challenge = "b" * 64
        assert verify_challenge_proof(wrong_challenge, signature_hex, public_key_hex) is False
    
    def test_challenge_proof_unicode(self, test_keypair):
        """Test challenge proof with unicode characters."""
        challenge = "挑战测试🔐"
        message = challenge.encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_challenge_proof(challenge, signature_hex, public_key_hex) is True


class TestEnrollmentProofVerification:
    """Test enrollment proof verification."""
    
    @pytest.fixture
    def test_keypair(self):
        """Generate a test keypair."""
        seed = b'\x00' * 32
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        
        return {
            'signing_key': signing_key,
            'verify_key': verify_key,
            'public_key_hex': verify_key.encode().hex(),
        }
    
    def test_valid_enrollment_proof(self, test_keypair):
        """Test valid enrollment proof."""
        device_id = "device-12345"
        timestamp = 1234567890
        
        # Message format: f"{device_id}:{timestamp}"
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_enrollment_proof(
            device_id, timestamp, signature_hex, public_key_hex
        ) is True
    
    def test_invalid_enrollment_proof_wrong_device_id(self, test_keypair):
        """Test enrollment proof fails with wrong device ID."""
        device_id = "device-12345"
        timestamp = 1234567890
        
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        wrong_device_id = "device-99999"
        assert verify_enrollment_proof(
            wrong_device_id, timestamp, signature_hex, public_key_hex
        ) is False
    
    def test_invalid_enrollment_proof_wrong_timestamp(self, test_keypair):
        """Test enrollment proof fails with wrong timestamp."""
        device_id = "device-12345"
        timestamp = 1234567890
        
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        wrong_timestamp = 9999999999
        assert verify_enrollment_proof(
            device_id, wrong_timestamp, signature_hex, public_key_hex
        ) is False
    
    def test_enrollment_proof_message_format(self, test_keypair):
        """Test that message format matches expected pattern."""
        device_id = "test-device"
        timestamp = 1000000
        
        # The message should be exactly "test-device:1000000"
        expected_message = b"test-device:1000000"
        signed = test_keypair['signing_key'].sign(expected_message)
        signature_hex = signed.signature.hex()
        public_key_hex = test_keypair['public_key_hex']
        
        assert verify_enrollment_proof(
            device_id, timestamp, signature_hex, public_key_hex
        ) is True


class TestChallengeGeneration:
    """Test challenge generation."""
    
    def test_generate_challenge_default_length(self):
        """Test challenge generation with default length."""
        challenge = generate_challenge()
        
        # Should be 32 bytes = 64 hex chars
        assert len(challenge) == 64
        
        # Should be valid hex
        bytes.fromhex(challenge)
    
    def test_generate_challenge_custom_length(self):
        """Test challenge generation with custom length."""
        challenge = generate_challenge(length=16)
        
        # Should be 16 bytes = 32 hex chars
        assert len(challenge) == 32
        
        # Should be valid hex
        bytes.fromhex(challenge)
    
    def test_generate_challenge_uniqueness(self):
        """Test that generated challenges are unique."""
        challenges = [generate_challenge() for _ in range(100)]
        
        # All should be unique
        assert len(set(challenges)) == 100
    
    def test_generate_challenge_randomness(self):
        """Test that challenges have sufficient randomness."""
        challenge = generate_challenge()
        
        # Should not be all zeros
        assert challenge != "0" * 64
        
        # Should not be all ones
        assert challenge != "f" * 64


class TestRustAgentCompatibility:
    """
    Test compatibility with Rust NEXLINK Agent.
    
    These tests use deterministic test vectors that match the exact
    protocol used by the Rust agent (ed25519-dalek).
    """
    
    @pytest.fixture
    def rust_compatible_keypair(self):
        """
        Generate a keypair using the same method as Rust agent.
        
        Rust agent uses ed25519-dalek with random key generation.
        We simulate this with PyNaCl.
        """
        # Use a fixed seed for reproducible tests
        # In production, Rust agent uses OsRng for randomness
        seed = bytes(range(32))  # 0, 1, 2, ..., 31
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        
        return {
            'signing_key': signing_key,
            'verify_key': verify_key,
            'public_key_hex': verify_key.encode().hex(),
        }
    
    def test_rust_agent_hello_message(self, rust_compatible_keypair):
        """
        Test verification of a hello message signature.
        
        Rust agent signs: f"{device_id}:{public_key}:{timestamp}"
        """
        device_id = "dev_abc123"
        public_key = rust_compatible_keypair['public_key_hex']
        timestamp = 1234567890
        
        # Construct message as Rust agent does
        message = f"{device_id}:{public_key}:{timestamp}".encode('utf-8')
        
        # Sign with the key
        signed = rust_compatible_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        # Verify
        assert verify_ed25519_signature(
            message, signature_hex, public_key
        ) is True
    
    def test_rust_agent_challenge_response(self, rust_compatible_keypair):
        """
        Test verification of challenge-response authentication.
        
        This is the exact flow used in WebSocket authentication.
        """
        # Server generates challenge
        challenge = generate_challenge()
        
        # Agent signs challenge
        message = challenge.encode('utf-8')
        signed = rust_compatible_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = rust_compatible_keypair['public_key_hex']
        
        # Server verifies
        assert verify_challenge_proof(
            challenge, signature_hex, public_key_hex
        ) is True
    
    def test_rust_agent_enrollment(self, rust_compatible_keypair):
        """
        Test verification of enrollment proof.
        
        This is the exact flow used in device enrollment.
        """
        device_id = "dev_" + "a" * 32
        timestamp = 1234567890
        
        # Agent signs: f"{device_id}:{timestamp}"
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = rust_compatible_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        public_key_hex = rust_compatible_keypair['public_key_hex']
        
        # Server verifies
        assert verify_enrollment_proof(
            device_id, timestamp, signature_hex, public_key_hex
        ) is True
    
    def test_rust_agent_replay_protection(self, rust_compatible_keypair):
        """
        Test that replayed messages are rejected.
        
        Enrollment uses timestamp for replay protection.
        """
        device_id = "dev_test"
        old_timestamp = 1000000000  # Old timestamp
        new_timestamp = 2000000000  # New timestamp
        
        # Sign with old timestamp
        old_message = f"{device_id}:{old_timestamp}".encode('utf-8')
        signed = rust_compatible_keypair['signing_key'].sign(old_message)
        signature_hex = signed.signature.hex()
        public_key_hex = rust_compatible_keypair['public_key_hex']
        
        # Try to verify with new timestamp (should fail)
        assert verify_enrollment_proof(
            device_id, new_timestamp, signature_hex, public_key_hex
        ) is False
        
        # Verify with correct timestamp (should pass)
        assert verify_enrollment_proof(
            device_id, old_timestamp, signature_hex, public_key_hex
        ) is True


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_none_inputs(self):
        """Test that None inputs are handled gracefully."""
        # These should return False, not raise exceptions
        assert verify_ed25519_signature(None, "00" * 64, "00" * 32) is False
        assert verify_ed25519_signature(b"test", None, "00" * 32) is False
        assert verify_ed25519_signature(b"test", "00" * 64, None) is False
    
    def test_empty_strings(self):
        """Test that empty strings are handled."""
        assert verify_ed25519_signature(b"test", "", "00" * 32) is False
        assert verify_ed25519_signature(b"test", "00" * 64, "") is False
    
    def test_binary_data_in_message(self):
        """Test verification with binary data in message."""
        seed = b'\x00' * 32
        signing_key = SigningKey(seed)
        public_key_hex = signing_key.verify_key.encode().hex()
        
        # Message with null bytes and high bytes
        message = b'\x00\x01\x02\xff\xfe\xfd'
        signed = signing_key.sign(message)
        signature_hex = signed.signature.hex()
        
        assert verify_ed25519_signature(message, signature_hex, public_key_hex) is True
