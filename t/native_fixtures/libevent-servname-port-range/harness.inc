    /* The string is count characters (0 to 11) of any value except the terminator, then the
       terminator. The characters after it are not part of the string and can have any value. */
    __CPROVER_assume(count <= 11);
    __CPROVER_assume(count <= 0 || ch0 != 0);
    __CPROVER_assume(count <= 1 || ch1 != 0);
    __CPROVER_assume(count <= 2 || ch2 != 0);
    __CPROVER_assume(count <= 3 || ch3 != 0);
    __CPROVER_assume(count <= 4 || ch4 != 0);
    __CPROVER_assume(count <= 5 || ch5 != 0);
    __CPROVER_assume(count <= 6 || ch6 != 0);
    __CPROVER_assume(count <= 7 || ch7 != 0);
    __CPROVER_assume(count <= 8 || ch8 != 0);
    __CPROVER_assume(count <= 9 || ch9 != 0);
    __CPROVER_assume(count <= 10 || ch10 != 0);
    char text[12];
    int pos = 0, negative = 0, digits = 0, shown, up;
    long long magnitude = 0, number;
    text[11] = '\0';
    text[0] = (char)ch0; text[1] = (char)ch1; text[2] = (char)ch2; text[3] = (char)ch3;
    text[4] = (char)ch4; text[5] = (char)ch5; text[6] = (char)ch6; text[7] = (char)ch7;
    text[8] = (char)ch8; text[9] = (char)ch9; text[10] = (char)ch10;
    text[count] = '\0';
    /* The expected result. A port number is an integer from 0 to 65535 (RFC 6335 section 6,
       https://www.rfc-editor.org/rfc/rfc6335#section-6). parse_numeric_servname returns the
       port for a numeric service name and -1 for anything else. The text is read as C11 7.22.1.4
       (https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf) reads the text for strtol in
       base 10: white space (space, \t \n \v \f \r), an optional + or -, one or more decimal
       digits. The value is computed here in 64 bits from the characters, 11 digits at most, so it
       cannot overflow. White space and a sign are what strtol accepts, and the function takes them
       today, so the expected result for them is the value of the number: " 80" and "+80" give 80
       and "-0" gives 0. The case does not say that they should be accepted, only what the number
       is. */
    while (pos < count && (text[pos] == ' ' || (text[pos] >= '\t' && text[pos] <= '\r'))) {
        ++pos;
    }
    if (pos < count && (text[pos] == '+' || text[pos] == '-')) {
        negative = text[pos] == '-';
        ++pos;
    }
    while (pos < count && text[pos] >= '0' && text[pos] <= '9') {
        magnitude = magnitude * 10 + (text[pos] - '0');
        ++pos;
        ++digits;
    }
    number = negative ? -magnitude : magnitude;
    shown = parse_numeric_servname(text);
    up = digits > 0 && pos == count;
    /* The result is -1 or a port number. */
    __CPROVER_assert(shown == -1 || (shown >= 0 && shown <= 65535), "servname.range");
    /* A string of decimal digits and nothing else gives its value when that is at most 65535
       and -1 otherwise. Leading zeros do not matter. */
    __CPROVER_assert(!(count > 0 && digits == count) || (long long)shown == (magnitude <= 65535 ? magnitude : -1),
                     "servname.digits");
    /* A whole string that is white space, a sign and digits gives its value when that is a port
       number and -1 otherwise. */
    __CPROVER_assert(!up || (long long)shown == (number >= 0 && number <= 65535 ? number : -1), "servname.value");
    /* The empty string gives -1. */
    __CPROVER_assert(count != 0 || shown == -1, "servname.empty");
    /* A number followed by any other character, also white space, gives -1. */
    __CPROVER_assert(!(digits > 0 && pos < count) || shown == -1, "servname.trailing");
    /* A string without a digit after the optional white space and sign gives -1. */
    __CPROVER_assert(digits > 0 || shown == -1, "servname.no_digits");
