    __CPROVER_assume(size <= 5);
    /* One array per size, so that a write past the given size leaves its object. */
    uint8_t a1[1] = {0xAA}, a2[2] = {0xAA, 0xAA}, a3[3] = {0xAA, 0xAA, 0xAA};
    uint8_t a4[4] = {0xAA, 0xAA, 0xAA, 0xAA}, a5[5] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA};
    uint8_t *p = size <= 1 ? a1 : size == 2 ? a2 : size == 3 ? a3 : size == 4 ? a4 : a5;
    int r = uvarintEncode(val, p, size);
    /* Reference, from the uvarint_t text of the FrSky OSD protocol
       (https://github.com/hydra/FrSkyPixelOSD/blob/master/doc/OSD.md): little endian, seven
       bits per byte, the final byte has its MSB clear and every byte before it has it set. */
    int n = val < 0x80 ? 1 : val < 0x4000 ? 2 : val < 0x200000 ? 3 : val < 0x10000000 ? 4 : 5;
    int fits = n <= (int)size;
    int same = 1;
    if (fits) {
        if (p[0] != (uint8_t)((val & 0x7F) | (n > 1 ? 0x80 : 0))) same = 0;
        if (n > 1 && p[1] != (uint8_t)(((val >> 7) & 0x7F) | (n > 2 ? 0x80 : 0))) same = 0;
        if (n > 2 && p[2] != (uint8_t)(((val >> 14) & 0x7F) | (n > 3 ? 0x80 : 0))) same = 0;
        if (n > 3 && p[3] != (uint8_t)(((val >> 21) & 0x7F) | (n > 4 ? 0x80 : 0))) same = 0;
        if (n > 4 && p[4] != (uint8_t)(val >> 28)) same = 0;
    }
    uint32_t back = 0;
    int read = fits ? uvarintDecode(&back, p, (size_t)n) : 0;
    __CPROVER_assert(r == (fits ? n : -1), "uvarint.length");
    __CPROVER_assert(same, "uvarint.bytes");
    __CPROVER_assert(!fits || (read == n && back == val), "uvarint.decoder_reads_it_back");
    __CPROVER_assert(size != 0 || a1[0] == 0xAA, "uvarint.no_write_without_room");
