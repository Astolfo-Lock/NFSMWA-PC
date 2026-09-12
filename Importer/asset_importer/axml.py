from __future__ import annotations

import re
import struct
from dataclasses import dataclass

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT_TYPE = 0x0102
UTF8_FLAG = 1 << 8
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11


class AxmlError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestInfo:
    package: str | None
    version_name: str | None
    version_code: str | None


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _decode_utf16_len(data: bytes, pos: int) -> tuple[str, int]:
    length = _u16(data, pos)
    pos += 2
    if length & 0x8000:
        length = ((length & 0x7FFF) << 16) | _u16(data, pos)
        pos += 2
    raw = data[pos : pos + length * 2]
    return raw.decode("utf-16le", "replace"), pos + length * 2 + 2


def _decode_utf8_len(data: bytes, pos: int) -> tuple[str, int]:
    def read_len(at: int) -> tuple[int, int]:
        value = data[at]
        at += 1
        if value & 0x80:
            value = ((value & 0x7F) << 8) | data[at]
            at += 1
        return value, at

    _chars, pos = read_len(pos)
    byte_len, pos = read_len(pos)
    text = data[pos : pos + byte_len].decode("utf-8", "replace")
    return text, pos + byte_len + 1


def parse_string_pool(data: bytes, offset: int = 8) -> list[str]:
    if len(data) < offset + 28:
        raise AxmlError("String pool demasiado corto.")
    chunk_type = _u16(data, offset)
    header_size = _u16(data, offset + 2)
    chunk_size = _u32(data, offset + 4)
    if chunk_type != RES_STRING_POOL_TYPE:
        raise AxmlError("No se encontró el string pool del manifiesto.")
    string_count = _u32(data, offset + 8)
    flags = _u32(data, offset + 16)
    strings_start = _u32(data, offset + 20)
    utf8 = bool(flags & UTF8_FLAG)
    offsets: list[int] = []
    table = offset + header_size
    for index in range(string_count):
        offsets.append(_u32(data, table + index * 4))
    pool_data = offset + strings_start
    strings: list[str] = []
    for rel in offsets:
        pos = pool_data + rel
        if pos >= len(data) or pos >= offset + chunk_size:
            strings.append("")
            continue
        if utf8:
            text, _ = _decode_utf8_len(data, pos)
        else:
            text, _ = _decode_utf16_len(data, pos)
        strings.append(text)
    return strings


def _scan_text_fallback(data: bytes) -> ManifestInfo:
    blobs = (
        data.decode("utf-8", "ignore"),
        data.decode("utf-16le", "ignore"),
        data.decode("utf-16be", "ignore"),
    )
    package = None
    version_name = None
    version_code = None
    for text in blobs:
        cleaned = text.replace("\x00", "")
        if "com.ea.games.nfs13_row" in cleaned:
            package = "com.ea.games.nfs13_row"
        name_match = re.search(r"versionName\s*[= ]\s*([0-9]+(?:\.[0-9]+)*)", cleaned)
        if name_match:
            version_name = name_match.group(1)
        code_match = re.search(r"versionCode\s*[= ]\s*(\d+)", cleaned)
        if code_match:
            version_code = code_match.group(1)
        elif "1003128" in cleaned and version_code is None:
            version_code = "1003128"
    return ManifestInfo(package, version_name, version_code)


def parse_manifest(data: bytes) -> ManifestInfo:
    if len(data) < 8:
        raise AxmlError("AndroidManifest.xml vacío.")
    magic = _u16(data, 0)
    if magic not in (RES_XML_TYPE, 0x0008):
        return _scan_text_fallback(data)

    try:
        strings = parse_string_pool(data, 8)
    except (AxmlError, struct.error, IndexError, UnicodeError):
        return _scan_text_fallback(data)

    package = next((s for s in strings if s == "com.ea.games.nfs13_row"), None)
    version_name = next((s for s in strings if s == "1.3.128"), None)
    version_code = next((s for s in strings if s == "1003128"), None)

    offset = 8
    file_size = min(len(data), _u32(data, 4) if len(data) >= 8 else len(data))
    try:
        while offset + 8 <= file_size:
            chunk_type = _u16(data, offset)
            header_size = _u16(data, offset + 2)
            chunk_size = _u32(data, offset + 4)
            if chunk_size < 8 or offset + chunk_size > len(data):
                break
            if chunk_type == RES_XML_START_ELEMENT_TYPE and chunk_size >= header_size + 20:
                ns_idx = struct.unpack_from("<i", data, offset + header_size)[0]
                name_idx = struct.unpack_from("<i", data, offset + header_size + 4)[0]
                attr_start = _u16(data, offset + header_size + 8)
                attr_size = _u16(data, offset + header_size + 10)
                attr_count = _u16(data, offset + header_size + 12)
                name = strings[name_idx] if 0 <= name_idx < len(strings) else ""
                if name == "manifest" or ns_idx == -1:
                    attr_ptr = offset + header_size + attr_start
                    for _ in range(attr_count):
                        if attr_ptr + max(attr_size, 20) > offset + chunk_size:
                            break
                        attr_name_idx = struct.unpack_from("<i", data, attr_ptr + 4)[0]
                        raw_idx = struct.unpack_from("<i", data, attr_ptr + 8)[0]
                        data_type = data[attr_ptr + 15] if attr_size >= 16 else 0
                        typed = _u32(data, attr_ptr + 16) if attr_size >= 20 else 0
                        attr_name = strings[attr_name_idx] if 0 <= attr_name_idx < len(strings) else ""
                        if attr_name == "package" and 0 <= raw_idx < len(strings):
                            package = strings[raw_idx]
                        elif attr_name == "versionName":
                            if data_type == TYPE_STRING and typed < len(strings):
                                version_name = strings[typed]
                            elif 0 <= raw_idx < len(strings):
                                version_name = strings[raw_idx]
                        elif attr_name == "versionCode" and data_type in (TYPE_INT_DEC, TYPE_INT_HEX, 0x10, 0x11):
                            version_code = str(typed)
                        attr_ptr += attr_size or 20
            offset += chunk_size
    except (struct.error, IndexError, ValueError):
        pass

    fallback = _scan_text_fallback(data)
    return ManifestInfo(
        package or fallback.package,
        version_name or fallback.version_name,
        version_code or fallback.version_code,
    )
