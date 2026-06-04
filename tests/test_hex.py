from pathlib import Path
from tempfile import TemporaryDirectory

from demodapk.hex import update_bin_with_patch


def test_hex_patching():
    """Verify search/replace and offset-based hex patching with wildcard support."""

    with TemporaryDirectory() as temp_dir:
        # Arrange
        apk_root = Path(temp_dir)
        binary_file = apk_root / "test.bin"

        # 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
        binary_file.write_bytes(bytes(range(16)))

        config = {
            "hex": [
                {
                    "path": "test.bin",
                    "verbose": True,
                    "patch": [
                        # Search-and-replace patch
                        "01 02 ?? 04 | FF EE DD CC",
                        # Offset patch with wildcard preservation
                        "0x0A | AA ?? BB",
                    ],
                }
            ]
        }

        # Act
        update_bin_with_patch(config, apk_root)

        # Assert
        assert binary_file.exists()

        patched_content = binary_file.read_bytes()

        expected_content = bytes.fromhex(
            "00 FF EE DD CC 05 06 07 08 09 AA 0B BB 0D 0E 0F"
        )

        assert patched_content == expected_content, (
            f"\nExpected: {expected_content.hex().upper()}"
            f"\nActual:   {patched_content.hex().upper()}"
        )
