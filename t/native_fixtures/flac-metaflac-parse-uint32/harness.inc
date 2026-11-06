    /* The string is the bytes b0 to b10 up to the first NUL byte, so its length is 0 to 11 and
       each character is any other byte. Position 11 holds the terminator. */
    char text[12];
    text[0] = (char)b0; text[1] = (char)b1; text[2] = (char)b2; text[3] = (char)b3;
    text[4] = (char)b4; text[5] = (char)b5; text[6] = (char)b6; text[7] = (char)b7;
    text[8] = (char)b8; text[9] = (char)b9; text[10] = (char)b10; text[11] = '\0';
    /* The expected result. The value of a string of decimal digits is the number that the digits
       write in base ten (C11 7.22.1.4, https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf).
       Eleven digits give at most 99999999999, which 64-bit arithmetic holds without wrapping.
       parse_uint32 is to take a string of one or more decimal digits whose value is at most
       4294967295 and to store that value, and to refuse everything else. That follows from its
       callers in the same file: each of them range-checks a FLAC__uint32 (--set-sample-rate
       against FLAC__MAX_SAMPLE_RATE, for example), which holds the value that the user wrote
       only if the stored value is that value. The metaflac manual (man/metaflac.md) describes
       --add-padding=length as a padding block of the given length in bytes, and the length field
       of a metadata block header has 24 bits
       (https://xiph.org/flac/format.html#metadata_block_header), so parse_add_padding is to take
       a length below 2^24 and to store it, and to refuse a larger one. The statements are one for
       each position, in place of a loop, so that the unwinding bound stays small. */
    unsigned long long want = 0;
    int length = 0, digits = 1, live = 1;
#define EACH(X) X(0) X(1) X(2) X(3) X(4) X(5) X(6) X(7) X(8) X(9) X(10)
#define READ(at) if (live) { if (text[at] == '\0') live = 0; else { ++length; \
        if (text[at] >= '0' && text[at] <= '9') want = want * 10u + (unsigned long long)(text[at] - '0'); \
        else digits = 0; } }
    EACH(READ)
    int fits = length > 0 && digits && want <= 0xffffffffull;
    FLAC__uint32 stored = 0x5a5a5a5au;
    FLAC__bool got = parse_uint32(text, &stored);
    /* True exactly for one or more decimal digits with a value of at most 2^32 - 1. */
    __CPROVER_assert((got != 0) == (fits != 0), "uint32.result");
    /* A stored value is the value of the digits. */
    __CPROVER_assert(!(got && length > 0 && digits) || (unsigned long long)stored == want, "uint32.value");
    /* A refused string leaves the destination as it was. */
    __CPROVER_assert(got || stored == 0x5a5a5a5au, "uint32.untouched_on_refusal");
    if (length > 0 && digits) {
        unsigned padding = 0xa5a5a5a5u;
        FLAC__bool taken = parse_add_padding(text, &padding);
        /* True exactly for a length below 2^24. */
        __CPROVER_assert((taken != 0) == (want < (1ull << 24)), "padding.result");
        /* A length that is taken is stored as written. */
        __CPROVER_assert(!taken || (unsigned long long)padding == want, "padding.value");
    }
