#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <unistd.h>
#include <zlib.h>

namespace {

constexpr int kPasswordDigits = 6;
constexpr int kPasswordSpace = 1000000;
constexpr size_t kEncryptionHeaderSize = 12;

uint16_t read_le16(const uint8_t* value) {
    return static_cast<uint16_t>(value[0] | (value[1] << 8));
}

uint32_t read_le32(const uint8_t* value) {
    return static_cast<uint32_t>(value[0]) |
           (static_cast<uint32_t>(value[1]) << 8) |
           (static_cast<uint32_t>(value[2]) << 16) |
           (static_cast<uint32_t>(value[3]) << 24);
}

std::vector<uint8_t> read_archive(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("Cannot open ZIP archive");

    stream.seekg(0, std::ios::end);
    const std::streamoff length = stream.tellg();
    if (length <= 0) throw std::runtime_error("ZIP archive is empty");
    stream.seekg(0, std::ios::beg);

    std::vector<uint8_t> archive(static_cast<size_t>(length));
    if (!stream.read(reinterpret_cast<char*>(archive.data()), length)) {
        throw std::runtime_error("Cannot read ZIP archive");
    }
    return archive;
}

struct Member {
    uint16_t flags;
    uint16_t method;
    uint16_t modified_time;
    uint32_t crc;
    uint32_t compressed_size;
    uint32_t uncompressed_size;
    uint32_t local_offset;
};

Member select_member(const std::vector<uint8_t>& archive) {
    if (archive.size() < 22) throw std::runtime_error("Truncated ZIP archive");

    const size_t search_start = archive.size() > 65557
        ? archive.size() - 65557
        : 0;
    size_t eocd_offset = archive.size() - 22;
    while (read_le32(&archive[eocd_offset]) != 0x06054b50) {
        if (eocd_offset == search_start) {
            throw std::runtime_error("ZIP end record not found");
        }
        --eocd_offset;
    }

    const uint16_t member_count = read_le16(&archive[eocd_offset + 10]);
    size_t offset = read_le32(&archive[eocd_offset + 16]);
    bool found = false;
    Member selected{};

    for (uint16_t index = 0; index < member_count; ++index) {
        if (offset + 46 > archive.size() ||
            read_le32(&archive[offset]) != 0x02014b50) {
            throw std::runtime_error("Invalid ZIP central directory");
        }

        const uint8_t* record = &archive[offset];
        const uint16_t flags = read_le16(record + 8);
        const uint16_t method = read_le16(record + 10);
        const uint32_t compressed_size = read_le32(record + 20);
        const uint16_t filename_length = read_le16(record + 28);
        const uint16_t extra_length = read_le16(record + 30);
        const uint16_t comment_length = read_le16(record + 32);
        const size_t record_size = 46ULL + filename_length + extra_length + comment_length;
        if (offset + record_size > archive.size()) {
            throw std::runtime_error("Truncated ZIP central directory");
        }

        const bool is_directory = filename_length > 0 &&
            archive[offset + 46 + filename_length - 1] == '/';
        if (!is_directory && (flags & 1U) && (method == 0 || method == 8) &&
            compressed_size >= kEncryptionHeaderSize &&
            (!found || compressed_size < selected.compressed_size)) {
            selected = {
                flags,
                method,
                read_le16(record + 12),
                read_le32(record + 16),
                compressed_size,
                read_le32(record + 24),
                read_le32(record + 42),
            };
            found = true;
        }
        offset += record_size;
    }

    if (!found) {
        throw std::runtime_error(
            "No encrypted ZipCrypto Stored/Deflate member found");
    }
    return selected;
}

struct Keys {
    uint32_t key0 = 0x12345678;
    uint32_t key1 = 0x23456789;
    uint32_t key2 = 0x34567890;

    void update(uint8_t value) {
        key0 = static_cast<uint32_t>(
            crc32(key0 ^ 0xffffffffU, &value, 1)) ^ 0xffffffffU;
        key1 = (key1 + (key0 & 0xffU)) * 134775813U + 1U;
        const uint8_t high_byte = static_cast<uint8_t>(key1 >> 24);
        key2 = static_cast<uint32_t>(
            crc32(key2 ^ 0xffffffffU, &high_byte, 1)) ^ 0xffffffffU;
    }

    uint8_t decrypt(uint8_t encrypted) {
        const uint16_t temporary = static_cast<uint16_t>(key2 | 2U);
        const uint8_t plain = encrypted ^ static_cast<uint8_t>(
            (temporary * (temporary ^ 1U)) >> 8);
        update(plain);
        return plain;
    }
};

std::array<uint8_t, kPasswordDigits> password_digits(int number) {
    std::array<uint8_t, kPasswordDigits> password{};
    for (int index = kPasswordDigits - 1; index >= 0; --index) {
        password[index] = static_cast<uint8_t>('0' + number % 10);
        number /= 10;
    }
    return password;
}

Keys initialize_keys(int number) {
    Keys keys;
    for (const uint8_t digit : password_digits(number)) keys.update(digit);
    return keys;
}

bool encryption_header_matches(
    int number, const uint8_t* encrypted, uint8_t check_byte) {
    Keys keys = initialize_keys(number);
    uint8_t last_byte = 0;
    for (size_t index = 0; index < kEncryptionHeaderSize; ++index) {
        last_byte = keys.decrypt(encrypted[index]);
    }
    return last_byte == check_byte;
}

bool validate_stored(
    const std::vector<uint8_t>& compressed,
    uint32_t expected_size,
    uint32_t expected_crc) {
    if (compressed.size() != expected_size) return false;
    return crc32(0L, compressed.data(), compressed.size()) == expected_crc;
}

bool validate_deflate(
    const std::vector<uint8_t>& compressed,
    uint32_t expected_size,
    uint32_t expected_crc) {
    if (compressed.size() > std::numeric_limits<uInt>::max()) return false;

    z_stream stream{};
    if (inflateInit2(&stream, -MAX_WBITS) != Z_OK) return false;
    stream.next_in = const_cast<Bytef*>(compressed.data());
    stream.avail_in = static_cast<uInt>(compressed.size());

    std::array<uint8_t, 64 * 1024> output{};
    uint32_t crc = crc32(0L, Z_NULL, 0);
    uint64_t total_size = 0;
    int status = Z_OK;
    while (status == Z_OK) {
        stream.next_out = output.data();
        stream.avail_out = static_cast<uInt>(output.size());
        status = inflate(&stream, Z_NO_FLUSH);
        const size_t produced = output.size() - stream.avail_out;
        crc = static_cast<uint32_t>(crc32(crc, output.data(), produced));
        total_size += produced;
    }
    inflateEnd(&stream);
    return status == Z_STREAM_END && total_size == expected_size &&
           crc == expected_crc;
}

bool validate_password(
    int number,
    const uint8_t* encrypted,
    const Member& member) {
    Keys keys = initialize_keys(number);
    for (size_t index = 0; index < kEncryptionHeaderSize; ++index) {
        keys.decrypt(encrypted[index]);
    }

    std::vector<uint8_t> compressed(
        member.compressed_size - kEncryptionHeaderSize);
    for (size_t index = kEncryptionHeaderSize;
         index < member.compressed_size;
         ++index) {
        compressed[index - kEncryptionHeaderSize] = keys.decrypt(encrypted[index]);
    }

    if (member.method == 0) {
        return validate_stored(compressed, member.uncompressed_size, member.crc);
    }
    return validate_deflate(compressed, member.uncompressed_size, member.crc);
}

int parse_integer(const char* value, const char* name) {
    char* end = nullptr;
    errno = 0;
    const long parsed = std::strtol(value, &end, 10);
    if (errno || !end || *end != '\0' || parsed < 0 ||
        parsed > std::numeric_limits<int>::max()) {
        throw std::runtime_error(std::string("Invalid ") + name);
    }
    return static_cast<int>(parsed);
}

void write_password(int file_descriptor, int number) {
    const auto password = password_digits(number);
    size_t written = 0;
    while (written < password.size()) {
        const ssize_t result = write(
            file_descriptor, password.data() + written, password.size() - written);
        if (result < 0) {
            if (errno == EINTR) continue;
            throw std::runtime_error("Cannot return recovered password");
        }
        written += static_cast<size_t>(result);
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 5) {
            throw std::runtime_error(
                "Usage: zip_password ARCHIVE START STOP RESULT_FD");
        }
        const int start = parse_integer(argv[2], "start");
        const int stop = parse_integer(argv[3], "stop");
        const int result_fd = parse_integer(argv[4], "result file descriptor");
        if (start >= stop || stop > kPasswordSpace) {
            throw std::runtime_error("Invalid password search range");
        }

        const std::vector<uint8_t> archive = read_archive(argv[1]);
        const Member member = select_member(archive);
        if (member.local_offset + 30 > archive.size() ||
            read_le32(&archive[member.local_offset]) != 0x04034b50) {
            throw std::runtime_error("Invalid ZIP local header");
        }

        const uint8_t* local_header = &archive[member.local_offset];
        const size_t payload_offset = member.local_offset + 30ULL +
            read_le16(local_header + 26) + read_le16(local_header + 28);
        if (payload_offset + member.compressed_size > archive.size()) {
            throw std::runtime_error("Truncated encrypted ZIP member");
        }

        const uint8_t* encrypted = &archive[payload_offset];
        const uint8_t check_byte = member.flags & 8U
            ? static_cast<uint8_t>(member.modified_time >> 8)
            : static_cast<uint8_t>(member.crc >> 24);

        for (int number = start; number < stop; ++number) {
            if (!encryption_header_matches(number, encrypted, check_byte)) continue;
            if (validate_password(number, encrypted, member)) {
                write_password(result_fd, number);
                return 0;
            }
        }
        return 2;
    } catch (const std::exception&) {
        return 1;
    }
}
