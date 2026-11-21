#!/usr/bin/env python3
"""Patch and re-sign Qualcomm NPRG/ENPRG ELF programmers.

The code patch is the common MDM9x06/9x65 Thumb patch.  The Qualcomm hash
segment is rebuilt by qc_signer.py, which detects SHA-256 versus SHA-384 from
the existing certificate (or accepts --hash explicitly).

Example:
    ./patch_nprg.py org/quectel/ENPRG9x06_bg96.mbn

The signer uses the test keys in qcpatchtools/keys/edl by default.  Use
--no-sign only when a raw code-patched ELF is deliberately wanted; it will not
be accepted by a target that authenticates the programmer.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

from validate_nprg import validate_path


SIGNER_DEFAULT = Path("/home/bjk/Projects/qcpatchtools/qc_signer.py")

# Thumb function shape used by the known MDM9x06 and MDM9x65 NPRG patches.
# The literal addresses and BL displacement are image-specific, so they are
# deliberately matched with a mask.
PATCH_PATTERN = bytes.fromhex(
    "10 b5 12 20 00 00 08 70 01 20 00 00 08 81 15 20 "
    "00 00 ff f7 00 00 00 20 10 bd"
)
PATCH_MASK = bytes.fromhex(
    "ff ff ff ff 00 00 ff ff ff ff 00 00 ff ff ff ff "
    "00 00 ff ff 00 00 ff ff ff ff"
)


def default_output(path: Path) -> Path:
    """Return the repository's conventional *p output name."""

    match = re.match(r"^(ENPRG|NPRG)(9x[0-9A-Fa-f]+)(.*)$", path.stem)
    if match:
        stem = f"{match.group(1)}{match.group(2)}p{match.group(3)}"
    else:
        stem = f"{path.stem}p"
    output_dir = path.parent.parent.parent if path.parent.parent.name == "org" else path.parent
    return output_dir / (stem + ".bin")


def find_patch(data: bytes) -> int:
    """Find the start of the function; return the offset of its prologue."""

    matches = []
    end = len(data) - len(PATCH_PATTERN) + 1
    for offset in range(end):
        candidate = data[offset : offset + len(PATCH_PATTERN)]
        if all((a & m) == (b & m) for a, b, m in zip(candidate, PATCH_PATTERN, PATCH_MASK)):
            matches.append(offset)
    if len(matches) != 1:
        detail = ", ".join(f"0x{x:x}" for x in matches) or "none"
        raise ValueError(f"expected one NPRG patch site, found {len(matches)} ({detail})")
    return matches[0]


def patch_code(data: bytes) -> tuple[bytes, int]:
    """Apply the common Thumb patch without changing the ELF file length."""

    function = find_patch(data)
    # Keep the function prologue.  The first literal load remains unchanged;
    # the second load now targets r0 and moves two bytes later, so its encoded
    # PC-relative immediate is one word smaller.
    first_ldr = data[function + 4 : function + 6]
    second_ldr = data[function + 10 : function + 12]
    if first_ldr[1] & 0x07 != 0x01 or second_ldr[1] & 0x07 != 0x01:
        raise ValueError(f"unexpected Thumb literal-load encoding at 0x{function:x}")
    replacement = (
        b"\x00\xf2\x08\x00"  # add.w r0, r0, #8
        + first_ldr
        + b"\x07\xee\x15\x1f\x80\x47"  # invalidate/cache operation; blx r0
        + bytes((second_ldr[0] - 1, second_ldr[1] - 1))
        + b"\x04\x81\xef\xe7"  # strh r4,[r0,#8]; branch to caller tail
    )
    if len(replacement) != 18:
        raise AssertionError("internal patch size error")

    output = bytearray(data)
    start = function + 2
    output[start : start + len(replacement)] = replacement
    return bytes(output), function


def detect_hash(data: bytes) -> str:
    """Infer the digest from the Qualcomm hash-table size field."""

    if data[:4] != b"\x7fELF" or len(data) < 0x1030:
        raise ValueError("input is not a supported ELF programmer")
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    if phentsize == 0 or phnum == 0:
        raise ValueError("ELF has no program headers")
    code_size = struct.unpack_from("<I", data, 0x1000 + 0x14)[0]
    if code_size % phnum:
        raise ValueError(f"hash-table size 0x{code_size:x} is not divisible by {phnum} segments")
    digest_size = code_size // phnum
    if digest_size == 32:
        return "SHA256"
    if digest_size == 48:
        return "SHA384"
    raise ValueError(f"unsupported Qualcomm digest width: {digest_size} bytes")


def prepare_sign_input(data: bytes, rsa_signature_size: int = 256) -> bytes:
    """Make the MBN header compatible with qc_signer's RSA test certificates.

    Some SHA-384 programmers carry a 104-byte ECDSA signature.  The bundled
    qc_signer emits a 2048-bit RSA test signature, so its MBN signature-size
    and certificate-pointer fields must be adjusted before signing.  The
    hash segment has a fixed reserved size, and the existing code/segments are
    otherwise left untouched.
    """

    headers = program_headers(data)
    hash_offset = headers[1][1]
    old_signature_size = struct.unpack_from("<I", data, hash_offset + 0x1C)[0]
    if old_signature_size == rsa_signature_size:
        return data
    output = bytearray(data)
    struct.pack_into("<I", output, hash_offset + 0x1C, rsa_signature_size)
    certificate_pointer = struct.unpack_from("<I", data, hash_offset + 0x20)[0]
    struct.pack_into(
        "<I", output, hash_offset + 0x20, certificate_pointer + rsa_signature_size - old_signature_size
    )
    return bytes(output)


def program_headers(data: bytes) -> list[tuple[int, int, int]]:
    """Return (type, file offset, file size) for each ELF32 program header."""

    if data[:4] != b"\x7fELF" or data[4] != 1:
        raise ValueError("reference is not an ELF32 programmer")
    phoff = struct.unpack_from("<I", data, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    if phentsize != 32:
        raise ValueError(f"unsupported program-header size: {phentsize}")
    return [
        struct.unpack_from("<III", data, phoff + index * phentsize)[:3]
        for index in range(phnum)
    ]


def reference_matches(reference: Path, patched: bytes, digest_name: str) -> bool:
    """Check whether a historical signed output is safe to reuse."""

    try:
        candidate = reference.read_bytes()
        if len(candidate) != len(patched):
            return False
        source_headers = program_headers(patched)
        reference_headers = program_headers(candidate)
    except (OSError, ValueError, struct.error):
        return False
    if len(source_headers) != len(reference_headers) or len(source_headers) < 3:
        return False
    for index, ((source_type, source_offset, source_size), (ref_type, ref_offset, ref_size)) in enumerate(
        zip(source_headers, reference_headers)
    ):
        if (source_type, source_offset) != (ref_type, ref_offset):
            return False
        # qc_signer expands the hash segment to its fixed signature-slot size
        # for some loaders.  Its contents are checked by validate_path below.
        if index != 1 and source_size != ref_size:
            return False
        if source_type == 1 and index != 1 and patched[source_offset : source_offset + source_size] != candidate[
            ref_offset : ref_offset + ref_size
        ]:
            return False

    digest_size = 32 if digest_name == "SHA256" else 48
    hash_offset = source_headers[1][1] + 0x28 + digest_size * 2
    load_type, load_offset, load_size = source_headers[2]
    if load_type != 1:
        return False
    digest = getattr(hashlib, digest_name.lower())(patched[load_offset : load_offset + load_size]).digest()
    return candidate[hash_offset : hash_offset + digest_size] == digest


def sign(input_path: Path, output_path: Path, signer: Path, hash_name: str | None) -> None:
    """Run qc_signer with its existing ``edl`` test-key set."""

    if not signer.is_file():
        raise FileNotFoundError(f"qc_signer.py not found: {signer}")
    key_source = signer.parent / "keys"
    if not (key_source / "rootkey").is_dir() or not (key_source / "edl").is_dir():
        raise FileNotFoundError(f"qc_signer key set not found below {key_source}")

    # qc_signer.py uses an old private cryptography helper and regenerates its
    # key files in the current working directory.  Stage both the tool and
    # keys, then provide the removed helper through sys.modules.  The shim
    # performs the same raw PKCS#1 v1.5 operation used by qc_signer.
    runner = r'''
import runpy
import sys
import types

def _rsa_sig_sign(_backend, _padding, _algorithm, private_key, digest):
    numbers = private_key.private_numbers()
    modulus = numbers.public_numbers.n
    exponent = numbers.d
    size = (modulus.bit_length() + 7) // 8
    encoded = b"\x00\x01" + b"\xff" * (size - len(digest) - 3) + b"\x00" + digest
    return pow(int.from_bytes(encoded, "big"), exponent, modulus).to_bytes(size, "big")

module = types.ModuleType("cryptography.hazmat.backends.openssl.rsa")
module._rsa_sig_sign = _rsa_sig_sign
sys.modules[module.__name__] = module
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
runpy.run_path(script, run_name="__main__")
'''
    with tempfile.TemporaryDirectory(prefix="nprg-qcsigner-") as work:
        root = Path(work)
        staged = root / "qcpatchtools"
        staged.mkdir()
        staged_signer = staged / "qc_signer.py"
        shutil.copy2(signer, staged_signer)
        shutil.copytree(key_source, staged / "keys")
        command = [sys.executable, "-c", runner, str(staged_signer), "-t", "edl", "-in", str(input_path), "-out", str(output_path)]
        if hash_name:
            command += ["-shamode", hash_name]
        subprocess.run(command, cwd=staged, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="original NPRG/ENPRG ELF (.mbn/.bin)")
    parser.add_argument("-o", "--output", type=Path, help="patched output (default: *p.bin)")
    parser.add_argument("--signer", type=Path, default=SIGNER_DEFAULT, help="path to qc_signer.py")
    parser.add_argument("--hash", choices=("SHA256", "SHA384"), help="override certificate hash detection")
    parser.add_argument(
        "--reference",
        type=Path,
        help="historical signed output to reuse (default: output + '.bak' when present)",
    )
    parser.add_argument("--no-sign", action="store_true", help="write only the code patch")
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    if not source.is_file():
        parser.error(f"input does not exist: {source}")
    destination = (args.output or default_output(source)).expanduser().resolve()
    if destination == source:
        parser.error("output must differ from input")
    destination.parent.mkdir(parents=True, exist_ok=True)

    original = source.read_bytes()
    patched, offset = patch_code(original)
    print(f"Patched Thumb site at file offset 0x{offset + 2:x}")

    if args.no_sign:
        destination.write_bytes(patched)
    else:
        hash_name = args.hash or detect_hash(original)
        reference = args.reference.expanduser().resolve() if args.reference else Path(str(destination) + ".bak")
        reference_matches_code = reference.is_file() and reference_matches(reference, patched, hash_name)
        reference_is_valid = reference_matches_code and validate_path(reference).ok
        if reference_is_valid:
            shutil.copyfile(reference, destination)
            print(f"Reused matching signed reference {reference}")
        else:
            if args.reference:
                raise ValueError(f"reference does not match the patched ELF or has an invalid signature: {reference}")
            # qc_signer rewrites the hash/signature segment.  Keep its
            # temporary input outside the repository and atomically publish
            # its final file.
            with tempfile.NamedTemporaryFile(prefix="nprg-patched-", suffix=".mbn", delete=False) as temp:
                sign_input = prepare_sign_input(patched)
                if sign_input != patched:
                    print("Normalizing MBN signature slot to 2048-bit RSA for qc_signer")
                temp.write(sign_input)
                temporary = Path(temp.name)
            try:
                print(f"Rebuilding Qualcomm {hash_name} hash/signature segment")
                sign(temporary, destination, args.signer.expanduser().resolve(), hash_name)
                validation = validate_path(destination)
                if not validation.ok:
                    destination.unlink(missing_ok=True)
                    details = "; ".join(validation.errors)
                    raise ValueError(f"qc_signer output failed validation: {details}")
                print(f"Validated {validation.algorithm} segment hashes and {validation.signature_mode} signature")
            finally:
                temporary.unlink(missing_ok=True)

    print(f"Wrote {destination} ({destination.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
