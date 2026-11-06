    __CPROVER_assume(len >= 1 && len <= 5);
    /* one array per length, so that a read past the end of the input leaves its object */
    char s1[1], s2[2], s3[3], s4[4], s5[5];
    char *s = len == 1 ? s1 : len == 2 ? s2 : len == 3 ? s3 : len == 4 ? s4 : s5;
    s[0] = (char)b0;
    if (len > 1) s[1] = (char)b1;
    if (len > 2) s[2] = (char)b2;
    if (len > 3) s[3] = (char)b3;
    if (len > 4) s[4] = (char)b4;
    const char *p = s;
    unsigned r = uv__utf8_decode1(&p, s + len);
    /* Well-formed UTF-8 byte sequences: RFC 3629 section 4 and Unicode table 3-7.
       A byte past the end of the input is not a continuation byte. */
    unsigned c1 = len > 1 ? b1 : 0, c2 = len > 2 ? b2 : 0, c3 = len > 3 ? b3 : 0;
    int t1 = c1 >= 0x80 && c1 <= 0xBF, t2 = c2 >= 0x80 && c2 <= 0xBF, t3 = c3 >= 0x80 && c3 <= 0xBF;
    unsigned n = 0, cp = 0;
    if (b0 <= 0x7F) { n = 1; cp = b0; }
    else if (b0 >= 0xC2 && b0 <= 0xDF && t1) { n = 2; cp = (b0 & 0x1Fu) << 6 | (c1 & 0x3Fu); }
    else if (b0 == 0xE0 && c1 >= 0xA0 && c1 <= 0xBF && t2) n = 3;
    else if (((b0 >= 0xE1 && b0 <= 0xEC) || b0 == 0xEE || b0 == 0xEF) && t1 && t2) n = 3;
    else if (b0 == 0xED && c1 >= 0x80 && c1 <= 0x9F && t2) n = 3;
    else if (b0 == 0xF0 && c1 >= 0x90 && c1 <= 0xBF && t2 && t3) n = 4;
    else if (b0 >= 0xF1 && b0 <= 0xF3 && t1 && t2 && t3) n = 4;
    else if (b0 == 0xF4 && c1 >= 0x80 && c1 <= 0x8F && t2 && t3) n = 4;
    if (n == 3) cp = (b0 & 0x0Fu) << 12 | (c1 & 0x3Fu) << 6 | (c2 & 0x3Fu);
    if (n == 4) cp = (b0 & 0x07u) << 18 | (c1 & 0x3Fu) << 12 | (c2 & 0x3Fu) << 6 | (c3 & 0x3Fu);
    __CPROVER_assert(n == 0 || (r == cp && p == s + n), "utf8.wellformed_decoded");
    __CPROVER_assert(n != 0 || r == (unsigned)-1, "utf8.illformed_rejected");
    __CPROVER_assert(p > s && p <= s + len, "utf8.cursor_in_bounds");
