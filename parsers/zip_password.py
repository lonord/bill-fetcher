"""Recover fixed-width numeric passwords from traditional ZipCrypto archives."""

from dataclasses import dataclass
import os
from pathlib import Path
import struct
import subprocess
import time
import zipfile
import zlib


PASSWORD_DIGITS = 6
PASSWORD_SPACE = 10**PASSWORD_DIGITS
_LOCAL_FILE_HEADER_SIZE = 30
_ENCRYPTION_HEADER_SIZE = 12
_NATIVE_HELPER = Path(__file__).resolve().parent.parent / "native" / "zip_password"
_NATIVE_TIMEOUT_SECONDS = 120


class PasswordNotFoundError(RuntimeError):
    """Raised when no six-digit numeric password can open an archive."""


@dataclass(frozen=True)
class PasswordSearchResult:
    password: bytes
    attempts: int
    elapsed_seconds: float


def _build_crc_table():
    table = []
    for value in range(256):
        crc = value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
        table.append(crc)
    return tuple(table)


_CRC_TABLE = _build_crc_table()


def _crc32_byte(crc, value):
    return (crc >> 8) ^ _CRC_TABLE[(crc ^ value) & 0xFF]


def _read_encryption_header(archive_path, member):
    with Path(archive_path).open("rb") as archive:
        archive.seek(member.header_offset)
        local_header = archive.read(_LOCAL_FILE_HEADER_SIZE)
        if (
            len(local_header) != _LOCAL_FILE_HEADER_SIZE
            or local_header[:4] != b"PK\x03\x04"
        ):
            raise zipfile.BadZipFile("Invalid local ZIP file header")

        flags = struct.unpack_from("<H", local_header, 6)[0]
        modified_time = struct.unpack_from("<H", local_header, 10)[0]
        filename_length, extra_length = struct.unpack_from("<HH", local_header, 26)
        archive.seek(filename_length + extra_length, 1)
        encrypted_header = archive.read(_ENCRYPTION_HEADER_SIZE)

    if not flags & 0x1:
        raise zipfile.BadZipFile("ZIP member is not encrypted")
    if len(encrypted_header) != _ENCRYPTION_HEADER_SIZE:
        raise zipfile.BadZipFile("Truncated ZipCrypto encryption header")

    check_byte = (
        (modified_time >> 8) & 0xFF if flags & 0x8 else (member.CRC >> 24) & 0xFF
    )
    return encrypted_header, check_byte


def _matches_encryption_header(number, encrypted_header, check_byte):
    key0, key1, key2 = 0x12345678, 0x23456789, 0x34567890
    divisor = 10 ** (PASSWORD_DIGITS - 1)

    for _ in range(PASSWORD_DIGITS):
        password_byte = 48 + (number // divisor) % 10
        divisor //= 10
        key0 = _crc32_byte(key0, password_byte)
        key1 = ((key1 + (key0 & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        key2 = _crc32_byte(key2, key1 >> 24)

    decrypted_byte = 0
    for encrypted_byte in encrypted_header:
        temporary = (key2 | 2) & 0xFFFF
        decrypted_byte = encrypted_byte ^ (
            ((temporary * (temporary ^ 1)) >> 8) & 0xFF
        )
        key0 = _crc32_byte(key0, decrypted_byte)
        key1 = ((key1 + (key0 & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        key2 = _crc32_byte(key2, key1 >> 24)

    return decrypted_byte == check_byte


def _verify_password(archive, member, password):
    try:
        with archive.open(member, pwd=password) as extracted:
            while extracted.read(64 * 1024):
                pass
        return True
    except (EOFError, RuntimeError, zipfile.BadZipFile, zlib.error):
        return False


def _recover_with_native_helper(archive_path, start, stop):
    if not _NATIVE_HELPER.is_file() or not os.access(_NATIVE_HELPER, os.X_OK):
        return None

    read_fd, write_fd = os.pipe()
    started = time.monotonic()
    try:
        try:
            process = subprocess.Popen(
                [
                    str(_NATIVE_HELPER),
                    os.fspath(archive_path),
                    str(start),
                    str(stop),
                    str(write_fd),
                ],
                pass_fds=(write_fd,),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        finally:
            os.close(write_fd)

        try:
            return_code = process.wait(timeout=_NATIVE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return None

        password = os.read(read_fd, PASSWORD_DIGITS + 1)
    finally:
        os.close(read_fd)

    if return_code == 2:
        raise PasswordNotFoundError(
            f"No {PASSWORD_DIGITS}-digit numeric password found after {stop - start} attempts"
        )
    if return_code != 0 or len(password) != PASSWORD_DIGITS or not password.isdigit():
        return None

    number = int(password)
    if not start <= number < stop:
        return None
    return PasswordSearchResult(
        password=password,
        attempts=number - start + 1,
        elapsed_seconds=time.monotonic() - started,
    )


def _recover_with_python(archive_path, start, stop):
    started = time.monotonic()
    with zipfile.ZipFile(archive_path) as archive:
        encrypted_members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.flag_bits & 0x1
        ]
        if not encrypted_members:
            raise zipfile.BadZipFile("ZIP archive has no encrypted files")

        member = min(encrypted_members, key=lambda item: item.compress_size)
        encrypted_header, check_byte = _read_encryption_header(archive_path, member)

        for number in range(start, stop):
            if not _matches_encryption_header(number, encrypted_header, check_byte):
                continue

            password = f"{number:0{PASSWORD_DIGITS}d}".encode("ascii")
            if _verify_password(archive, member, password):
                return PasswordSearchResult(
                    password=password,
                    attempts=number - start + 1,
                    elapsed_seconds=time.monotonic() - started,
                )

    raise PasswordNotFoundError(
        f"No {PASSWORD_DIGITS}-digit numeric password found after {stop - start} attempts"
    )


def recover_numeric_zip_password(archive_path, start=0, stop=PASSWORD_SPACE):
    """Find a six-digit numeric ZipCrypto password without logging its value."""
    if not (0 <= start < stop <= PASSWORD_SPACE):
        raise ValueError(f"Password range must be within 0..{PASSWORD_SPACE}")

    native_result = _recover_with_native_helper(archive_path, start, stop)
    if native_result is not None:
        return native_result
    return _recover_with_python(archive_path, start, stop)
