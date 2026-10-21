from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nexlink_agent.identity import DeviceIdentity


def test_device_identity_encrypted_round_trip(tmp_path):
    identity_file = tmp_path / "identity.json"
    identity = DeviceIdentity.load_or_create(identity_file, "test-passphrase-12")
    restored = DeviceIdentity.load(identity_file, "test-passphrase-12")

    assert restored.device_id == identity.device_id
    assert restored.public_key_hex == identity.public_key_hex
