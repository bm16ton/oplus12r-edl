#!/usr/bin/env python3
"""Validate Qualcomm NPRG/ENPRG ELF hashes, signature, and certificates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
import struct
import sys

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa


@dataclass
class ValidationReport:
    path: Path
    algorithm: str = ""
    hash_records_offset: int = 0
    load_hash_offset: int = 0
    segment_hashes: int = 0
    signature_mode: str = ""
    certificate_count: int = 0
    pk_hash: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _hash_fn(name: str):
    try:
        return {"SHA256": hashlib.sha256, "SHA384": hashlib.sha384}[name]
    except KeyError as exc:
        raise ValueError(f"unsupported hash algorithm: {name}") from exc


def _crypto_hash(name: str):
    return {"SHA256": hashes.SHA256, "SHA384": hashes.SHA384}[name]()


def _parse_program_headers(data: bytes) -> list[tuple[int, int, int, int, int, int, int, int]]:
    if len(data) < 0x34 or data[:4] != b"\x7fELF" or data[4:6] != b"\x01\x01":
        raise ValueError("not a little-endian ELF32 file")
    phoff = struct.unpack_from("<I", data, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    if phentsize != 32 or phnum == 0:
        raise ValueError(f"unsupported ELF program-header table ({phentsize}, {phnum})")
    if phoff + phentsize * phnum > len(data):
        raise ValueError("program-header table is outside the file")
    return [struct.unpack_from("<IIIIIIII", data, phoff + i * phentsize) for i in range(phnum)]


def _qti_digest(sw_id: int, hw_id: int, message: bytes, digest_fn) -> bytes:
    sw = sw_id.to_bytes(8, "big")
    hw = hw_id.to_bytes(8, "big")
    si = bytes(value ^ 0x36 for value in sw)
    so = bytes(value ^ 0x5C for value in hw)
    return digest_fn(so + digest_fn(si + digest_fn(message).digest()).digest()).digest()


def _subject_id(cert: x509.Certificate, name: str) -> int:
    pattern = re.compile(r"([0-9A-Fa-f]+)\s+" + re.escape(name) + r"(?:$|\s)")
    for attribute in cert.subject:
        match = pattern.search(attribute.value)
        if match:
            return int(match.group(1), 16)
    return 0


def _raw_rsa_matches(public_key, signature: bytes, digest: bytes) -> bool:
    if not isinstance(public_key, rsa.RSAPublicKey):
        return False
    numbers = public_key.public_numbers()
    size = (numbers.n.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    encoded = pow(int.from_bytes(signature, "big"), numbers.e, numbers.n).to_bytes(size, "big")
    expected = b"\x00\x01" + b"\xff" * (size - len(digest) - 3) + b"\x00" + digest
    return encoded == expected


def _verify_certificate(child: x509.Certificate, issuer: x509.Certificate) -> None:
    public_key = issuer.public_key()
    algorithm = child.signature_hash_algorithm
    if algorithm is None:
        raise ValueError("certificate has no signature hash algorithm")
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(child.signature, child.tbs_certificate_bytes, ec.ECDSA(algorithm))
        return
    if child.signature_algorithm_oid._name.lower() == "rsassapss":
        verify_padding = padding.PSS(mgf=padding.MGF1(algorithm), salt_length=algorithm.digest_size)
    else:
        verify_padding = padding.PKCS1v15()
    public_key.verify(child.signature, child.tbs_certificate_bytes, verify_padding, algorithm)


def _der_sequence_length(data: bytes, offset: int) -> int | None:
    """Return the encoded DER length at a SEQUENCE, including its header."""

    if offset + 2 > len(data) or data[offset] != 0x30:
        return None
    first_length = data[offset + 1]
    if first_length < 0x80:
        header_size = 2
        content_size = first_length
    else:
        length_bytes = first_length & 0x7F
        if length_bytes == 0 or length_bytes > 4 or offset + 2 + length_bytes > len(data):
            return None
        header_size = 2 + length_bytes
        content_size = int.from_bytes(data[offset + 2 : offset + header_size], "big")
    total_size = header_size + content_size
    return total_size if offset + total_size <= len(data) else None


def validate_bytes(data: bytes, path: Path = Path("<memory>")) -> ValidationReport:
    report = ValidationReport(path)
    try:
        ph = _parse_program_headers(data)
        if len(ph) < 3:
            raise ValueError("expected hash, signature, and load program headers")
        hash_offset = ph[1][1]
        if hash_offset + 0x28 > len(data):
            raise ValueError("hash segment header is outside the file")

        # Qualcomm MBN v3-v5 header.  The hash segment begins at hash_offset;
        # its first digest record follows the 0x28-byte header.
        mbn = struct.unpack_from("<10I", data, hash_offset)
        version, code_size, signature_size, certificate_size = mbn[1], mbn[5], mbn[7], mbn[9]
        if version not in (3, 4, 5):
            raise ValueError(f"unsupported MBN header version: {version}")
        if code_size % len(ph) != 0:
            raise ValueError(f"hash table size 0x{code_size:x} is not divisible by {len(ph)} segments")
        digest_size = code_size // len(ph)
        if digest_size not in (32, 48):
            raise ValueError(f"unsupported digest width: {digest_size} bytes")
        report.algorithm = "SHA256" if digest_size == 32 else "SHA384"
        digest_fn = _hash_fn(report.algorithm)
        report.hash_records_offset = hash_offset + 0x28
        if len(ph) < 3:
            raise ValueError("expected a load segment program header")
        report.load_hash_offset = report.hash_records_offset + digest_size * 2
        report.segment_hashes = len(ph)

        hash_end = report.hash_records_offset + code_size
        signature_offset = hash_end
        certificate_offset = signature_offset + signature_size
        certificate_end = certificate_offset + certificate_size
        if certificate_end > len(data):
            raise ValueError("signature or certificate chain is outside the file")

        # Segment hash records are ordered exactly like the ELF program
        # headers.  The hash segment itself is represented by zeroes.
        for index, entry in enumerate(ph):
            p_type, file_offset, _vaddr, _paddr, file_size, _mem_size, _flags, _align = entry
            if index == 1 or file_size == 0:
                expected = b"\x00" * digest_size
            else:
                if file_offset + file_size > len(data):
                    raise ValueError(f"segment {index} is outside the file")
                expected = digest_fn(data[file_offset : file_offset + file_size]).digest()
            actual = data[report.hash_records_offset + index * digest_size : report.hash_records_offset + (index + 1) * digest_size]
            if actual != expected:
                report.errors.append(
                    f"segment {index} hash mismatch: expected {expected.hex()}, got {actual.hex()}"
                )

        cert_bytes = data[certificate_offset:certificate_end]
        certificates = []
        certificate_der = []
        position = 0
        while position < len(cert_bytes) and cert_bytes[position] == 0x30:
            der_length = _der_sequence_length(cert_bytes, position)
            if der_length is None:
                raise ValueError("truncated DER certificate")
            der = cert_bytes[position : position + der_length]
            certificates.append(x509.load_der_x509_certificate(der))
            certificate_der.append(der)
            position += der_length
        report.certificate_count = len(certificates)
        if len(certificates) < 3:
            raise ValueError(f"expected a three-certificate chain, found {len(certificates)}")

        report.pk_hash = digest_fn(certificate_der[-1]).hexdigest()
        for chain_index, (child, issuer) in enumerate(zip(certificates, certificates[1:])):
            try:
                _verify_certificate(child, issuer)
            except (InvalidSignature, TypeError, ValueError) as exc:
                report.warnings.append(f"certificate {chain_index} issuer signature did not verify: {exc}")
        try:
            _verify_certificate(certificates[-1], certificates[-1])
        except (InvalidSignature, TypeError, ValueError) as exc:
            report.warnings.append(f"root certificate self-signature did not verify: {exc}")

        message = data[hash_offset:signature_offset]
        signature = data[signature_offset:certificate_offset]
        leaf_key = certificates[0].public_key()
        candidates = [("direct", digest_fn(message).digest())]
        sw_id = _subject_id(certificates[0], "SW_ID")
        hw_id = _subject_id(certificates[0], "HW_ID")
        candidates.append(("QTI", _qti_digest(sw_id, hw_id, message, digest_fn)))

        for mode, candidate in candidates:
            if _raw_rsa_matches(leaf_key, signature, candidate):
                report.signature_mode = mode
                break
        if not report.signature_mode and isinstance(leaf_key, ec.EllipticCurvePublicKey):
            try:
                leaf_key.verify(signature, message, ec.ECDSA(_crypto_hash(report.algorithm)))
                report.signature_mode = "ECDSA/direct"
            except InvalidSignature:
                pass
        if not report.signature_mode and isinstance(leaf_key, rsa.RSAPublicKey):
            for mode, candidate in candidates:
                try:
                    leaf_key.verify(signature, message, padding.PKCS1v15(), _crypto_hash(report.algorithm))
                    report.signature_mode = f"PKCS1/{mode}"
                    break
                except InvalidSignature:
                    pass
        if not report.signature_mode:
            raise ValueError("program signature verification failed")
    except (ValueError, struct.error) as exc:
        report.errors.append(str(exc))
    return report


def validate_path(path: Path) -> ValidationReport:
    return validate_bytes(path.read_bytes(), path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="NPRG/ENPRG ELF to validate")
    args = parser.parse_args()
    report = validate_path(args.file)
    if report.algorithm:
        print(f"hash algorithm:       {report.algorithm}")
        print(
            f"hash records:         0x{report.hash_records_offset:x} "
            f"({report.segment_hashes} segments; load record 0x{report.load_hash_offset:x})"
        )
    if report.signature_mode:
        print(f"program signature:    valid ({report.signature_mode})")
    if report.certificate_count:
        print(f"certificate chain:     parsed ({report.certificate_count} certificates)")
        print(f"root certificate hash: {report.pk_hash}")
    for warning in report.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("validation:            PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
