    __CPROVER_assume(kind <= 1);
    __CPROVER_assume(count <= 2);
    __CPROVER_assume(room <= 24);
    char data[2], want[24], out[24];
    int len = 0, got, i;
    data[0] = (char)b0;
    data[1] = (char)b1;
    /* The expected text. A BIN object is printed as its bytes between two double quotes. An
       EXT object has "(ext: T)" before that, where T is its type as a decimal number. A
       double quote among the bytes is written as \", another printable character of the C
       locale (0x20 to 0x7e) as itself, and every other byte as \x with two lowercase
       hexadecimal digits. msgpack_object_print() writes the same text to a FILE. */
    if (kind == 1) {
        int t = tag < 0 ? -tag : tag;
        want[len++] = '('; want[len++] = 'e'; want[len++] = 'x'; want[len++] = 't';
        want[len++] = ':'; want[len++] = ' ';
        if (tag < 0) want[len++] = '-';
        if (t >= 100) want[len++] = (char)('0' + t / 100);
        if (t >= 10) want[len++] = (char)('0' + t / 10 % 10);
        want[len++] = (char)('0' + t % 10);
        want[len++] = ')';
    }
    want[len++] = '"';
    for (i = 0; i < count; ++i) {
        unsigned char byte = (unsigned char)data[i];
        if (byte == '"') {
            want[len++] = '\\'; want[len++] = '"';
        } else if (byte >= 0x20 && byte <= 0x7e) {
            want[len++] = (char)byte;
        } else {
            want[len++] = '\\'; want[len++] = 'x';
            want[len++] = "0123456789abcdef"[byte >> 4];
            want[len++] = "0123456789abcdef"[byte & 15];
        }
    }
    want[len++] = '"';
    /* One statement for each of the 24 bytes of out in place of a loop, so that the unwinding
       bound stays small. The bytes after the given size are a canary. */
#define EACH(X) X(0) X(1) X(2) X(3) X(4) X(5) X(6) X(7) X(8) X(9) X(10) X(11) X(12) X(13) X(14) X(15) \
                X(16) X(17) X(18) X(19) X(20) X(21) X(22) X(23)
#define FILL(at) out[at] = 0x55;
#define SAME(at) if (at < len && out[at] != want[at]) same = 0;
#define KEPT(at) if (at >= room && out[at] != 0x55) kept = 0;
#define ENDED(at) if (at < room && out[at] == '\0') ended = 1;
    EACH(FILL)
    msgpack_object object = {MSGPACK_OBJECT_NIL};
    if (kind == 1) {
        object.type = MSGPACK_OBJECT_EXT;
        object.via.ext.type = tag;
        object.via.ext.ptr = data;
        object.via.ext.size = count;
        got = msgpack_object_print_buffer(out, room, object);
    } else {
        object.type = MSGPACK_OBJECT_BIN;
        object.via.bin.ptr = data;
        object.via.bin.size = count;
        got = msgpack_object_print_buffer(out, room, object);
    }
    /* The text and its terminator fit in the given size, or the result is 0. */
    int fits = len < room, same = 1, kept = 1, ended = room == 0;
    if (fits) {
        EACH(SAME)
        if (out[len] != '\0') same = 0;
    }
    EACH(KEPT)
    EACH(ENDED)
    __CPROVER_assert(got == (fits ? len : 0), "print.result");
    __CPROVER_assert(same, "print.text");
    __CPROVER_assert(kept, "print.nothing_after_the_given_size");
    __CPROVER_assert(ended, "print.terminated");
