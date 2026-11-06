    /* Reference: RFC 7252 section 3.1 (https://www.rfc-editor.org/rfc/rfc7252#section-3.1).
       An option starts with one byte: the delta in the high nibble and the length in the
       low nibble. A nibble of 13 is followed by one extra byte, and the value is the nibble
       plus that byte (so the extra byte plus 13). A nibble of 14 is followed by two extra
       bytes in network order, and the value is that number plus 269. A nibble of 15 is
       reserved. The extra bytes of the delta come before those of the length, and the
       option value follows them. The option number is the sum of the deltas. Option
       numbers are 16 bits wide (section 12.2 lists 0 to 65535), so a delta above 65535
       cannot belong to a valid option. The header size, the delta and the length are
       computed here from the input bytes with 32-bit arithmetic only.
       The given length is 0 to 65809. For a length of 0 to 5 the buffer is a local array
       that ends where the given length ends, so any read past the end is out of bounds.
       For a length of 6 or more the header (at most 5 bytes) always fits, and the buffer
       is a static array of the longest header and value. */
    __CPROVER_assume(room <= 65809u);
    unsigned char hb[5] = {h0, h1, h2, h3, h4};
    uint32_t dn = (uint32_t)(h0 >> 4), ln = (uint32_t)(h0 & 15u);
    uint32_t pos = 1u, delta = dn, vlen = ln;
    if (dn == 13u) {
        delta = 13u + hb[pos];
        pos = pos + 1u;
    } else if (dn == 14u) {
        delta = 269u + 256u * hb[pos] + hb[pos + 1u];
        pos = pos + 2u;
    }
    if (ln == 13u) {
        vlen = 13u + hb[pos];
        pos = pos + 1u;
    } else if (ln == 14u) {
        vlen = 269u + 256u * hb[pos] + hb[pos + 1u];
        pos = pos + 2u;
    }
    uint32_t hsize = pos;
    /* The option is invalid when a nibble is reserved, when the header does not fit in the
       given length, when the value does not fit after the header, or when the delta is
       above 65535. */
    int invalid = dn == 15u || ln == 15u || hsize > room || vlen > room - hsize || delta > 65535u;

    struct {
        unsigned char before[4];
        coap_option_t option;
        unsigned char after[4];
    } cell;
    cell.before[0] = cell.before[1] = cell.before[2] = cell.before[3] = 0x5a;
    cell.after[0] = cell.after[1] = cell.after[2] = cell.after[3] = 0xa5;

    unsigned char tiny[5] = {0, 0, 0, 0, 0};
    const unsigned char *base = case_buffer;
    size_t got = 0;
    if (room == 0u) {
        base = tiny + 5;
        got = coap_opt_parse(base, 0, &cell.option);
    } else if (room == 1u) {
        tiny[4] = h0;
        base = tiny + 4;
        got = coap_opt_parse(base, 1, &cell.option);
    } else if (room == 2u) {
        tiny[3] = h0; tiny[4] = h1;
        base = tiny + 3;
        got = coap_opt_parse(base, 2, &cell.option);
    } else if (room == 3u) {
        tiny[2] = h0; tiny[3] = h1; tiny[4] = h2;
        base = tiny + 2;
        got = coap_opt_parse(base, 3, &cell.option);
    } else if (room == 4u) {
        tiny[1] = h0; tiny[2] = h1; tiny[3] = h2; tiny[4] = h3;
        base = tiny + 1;
        got = coap_opt_parse(base, 4, &cell.option);
    } else if (room == 5u) {
        tiny[0] = h0; tiny[1] = h1; tiny[2] = h2; tiny[3] = h3; tiny[4] = h4;
        base = tiny;
        got = coap_opt_parse(base, 5, &cell.option);
    } else {
        case_buffer[0] = h0; case_buffer[1] = h1; case_buffer[2] = h2; case_buffer[3] = h3; case_buffer[4] = h4;
        base = case_buffer;
        got = coap_opt_parse(base, room, &cell.option);
    }

    __CPROVER_assert((got == 0) == (invalid != 0), "opt.zero_exactly_when_invalid");
    __CPROVER_assert(got == 0 || cell.option.delta == delta, "opt.delta");
    __CPROVER_assert(got == 0 || cell.option.length == (size_t)vlen, "opt.length");
    __CPROVER_assert(got == 0 || cell.option.value == base + hsize, "opt.value");
    __CPROVER_assert(got == 0 || got == (size_t)hsize + (size_t)vlen, "opt.size");
    __CPROVER_assert(cell.before[0] == 0x5a && cell.before[1] == 0x5a && cell.before[2] == 0x5a && cell.before[3] == 0x5a
                     && cell.after[0] == 0xa5 && cell.after[1] == 0xa5 && cell.after[2] == 0xa5 && cell.after[3] == 0xa5,
                     "opt.nothing_else_written");
