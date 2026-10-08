"""RXPGuides export format: zlib-compressed guides, RC4-encrypted with a key
derived from the BattleTag, base64-encoded.

File layout: ``<nGuides>|<adler32>:<base64>%|<version>``
"""

from __future__ import annotations

import base64
import re
import zlib
from dataclasses import dataclass
from functools import lru_cache

_VERSION_RE = re.compile(r"\|(\d+)$")
_CHUNK_RE = re.compile(r"(-?\d+)(\D)([A-Za-z0-9+/=]+)%")
_DEFAULT_VERSION = 40000


def derive_key(battletag: str) -> bytes:
    """Derive the 16-byte RC4 key from a BattleTag (UTF-8 bytes, like the Lua addon)."""
    data = battletag.lower().encode("utf-8")[-16:]
    k = 16 - len(data)
    buf = bytearray(16)

    for i in range(16):
        j = (i - k) & 0xF
        if j < len(data):
            buf[i] = data[j]

    for i in range(16):
        buf[(-i) & 0xF] = (
            buf[(15 - i) & 0xF]
            ^ buf[(13 - i) & 0xF]
            ^ buf[(12 - i) & 0xF]
            ^ buf[(10 - i) & 0xF]
        )

    return bytes(buf)


def rc4_ksa(key16: bytes) -> bytearray:
    """RC4 key scheduling."""
    S = bytearray(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key16[i & 0xF]) & 0xFF
        S[i], S[j] = S[j], S[i]
    return S


class _Keystream:
    """RC4 keystream for one key, generated lazily and kept for reuse.

    Every chunk/file is encrypted from a fresh S-box, so the keystream prefix
    is identical for all files of the same BattleTag — computing it once per
    tag is what makes pure-Python RC4 fast enough here.
    """

    def __init__(self, key16: bytes) -> None:
        self._S = rc4_ksa(key16)
        self._i = 0
        self._j = 0
        self._buf = bytearray()

    def take(self, n: int) -> bytes:
        if n > len(self._buf):
            self._extend(n - len(self._buf))
        return bytes(self._buf[:n])

    def _extend(self, n: int) -> None:
        S, i, j = self._S, self._i, self._j
        out = bytearray(n)
        for k in range(n):
            i = (i + 1) & 0xFF
            si = S[i]
            j = (j + si) & 0xFF
            sj = S[j]
            S[i] = sj
            S[j] = si
            out[k] = S[(si + sj) & 0xFF]
        self._i, self._j = i, j
        self._buf += out


@lru_cache(maxsize=32)
def _keystream(battletag_lower: str) -> _Keystream:
    return _Keystream(derive_key(battletag_lower))


def rc4_crypt(battletag: str, data: bytes) -> bytes:
    """RC4 encrypt/decrypt (symmetric) with the key of ``battletag``."""
    n = len(data)
    ks = _keystream(battletag.lower()).take(n)
    return (int.from_bytes(data, "little") ^ int.from_bytes(ks, "little")).to_bytes(n, "little")


@dataclass
class DecryptResult:
    plaintext: str
    version: int
    guide_count: int


def decrypt_guide_file(raw: str, battletag: str) -> DecryptResult:
    """Decrypt an RXPGuides export file. Raises (zlib.error, ...) on a wrong BattleTag."""
    raw = raw.strip()
    m = _VERSION_RE.search(raw)
    version = int(m.group(1)) if m else _DEFAULT_VERSION

    guides: list[str] = []
    for chunk in _CHUNK_RE.finditer(raw):
        if chunk.group(2) != ":":
            continue
        decrypted = rc4_crypt(battletag, base64.b64decode(chunk.group(3)))
        text = zlib.decompress(decrypted).decode("utf-8", errors="replace")
        guides.extend(g for g in text.split("\x00") if g.strip())

    if not guides:
        raise ValueError("no guides found in file")

    return DecryptResult("\x00".join(guides), version, len(guides))


def encrypt_for_battletag(plaintext: str, battletag: str, version: int) -> str:
    """Encrypt plaintext guides (NUL-separated) for ``battletag``."""
    data = plaintext.encode("utf-8")
    n_guides = plaintext.count("\x00") + 1
    checksum = zlib.adler32(data)
    encrypted = rc4_crypt(battletag, zlib.compress(data, 6))
    encoded = base64.b64encode(encrypted).decode("ascii")
    return f"{n_guides}|{checksum}:{encoded}%|{version}"
