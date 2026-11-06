    __CPROVER_assume(d0 <= 9 && d1 <= 9 && d2 <= 9 && d3 <= 9 && d4 <= 9 && sign <= 2 && (digits == 4 || digits == 5));
    /* The string [+-]YYYY[Y]-01-01T00:00:00Z. One array per length, so that a read past the
       end of the string leaves its object. */
    UA_Byte s20[20], s21[21], s22[22];
    size_t length = (size_t)((sign != 0) + digits + 16);
    UA_Byte *s = length == 20 ? s20 : length == 21 ? s21 : s22;
    size_t n = 0;
    if (sign == 1) s[n++] = '+';
    if (sign == 2) s[n++] = '-';
    s[n++] = (UA_Byte)('0' + d0);
    s[n++] = (UA_Byte)('0' + d1);
    s[n++] = (UA_Byte)('0' + d2);
    s[n++] = (UA_Byte)('0' + d3);
    if (digits == 5) s[n++] = (UA_Byte)('0' + d4);
    s[n + 0] = '-'; s[n + 1] = '0'; s[n + 2] = '1'; s[n + 3] = '-'; s[n + 4] = '0'; s[n + 5] = '1';
    s[n + 6] = 'T'; s[n + 7] = '0'; s[n + 8] = '0'; s[n + 9] = ':'; s[n + 10] = '0'; s[n + 11] = '0';
    s[n + 12] = ':'; s[n + 13] = '0'; s[n + 14] = '0'; s[n + 15] = 'Z';
    UA_String str = {length, s};
    UA_DateTime dt = 0;
    UA_StatusCode res = UA_DateTime_parse(&dt, str);
    /* Reference: days from 1970-01-01 to January 1 of the year in the proleptic Gregorian
       calendar with a year 0, by the count of leap years before it (the count used in
       https://howardhinnant.github.io/date_algorithms.html#days_from_civil). The year is first
       moved forward by 250 periods of 400 years, 36524250 days, so that every division has
       operands that are not negative. 719162 days lie between 0001-01-01 and 1970-01-01. */
    int year = digits == 5 ? 10000 * d0 + 1000 * d1 + 100 * d2 + 10 * d3 + d4 : 1000 * d0 + 100 * d1 + 10 * d2 + d3;
    if (sign == 2) year = -year;
    int before = year + 100000 - 1;
    long long days = 365LL * before + before / 4 - before / 100 + before / 400 - 36524250 - 719162;
    /* Seconds since 1601-01-01, the DateTime epoch. A DateTime counts steps of 100 ns in an
       int64, so a whole second is representable from -922337203685 to 922337203685. */
    long long secs = days * 86400 + 11644473600LL;
    int representable = secs >= -922337203685LL && secs <= 922337203685LL;
    __CPROVER_assert((res == UA_STATUSCODE_GOOD) == representable, "datetime.accepted_iff_representable");
    __CPROVER_assert(res != UA_STATUSCODE_GOOD || !representable || dt == secs * 10000000LL, "datetime.value");
