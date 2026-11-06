/* Models of the <string.h> functions CBMC 6.11.0 has no model for.
 *
 * Plain C from C11 7.24, and glibc's manual for the GNU functions. Each reads one byte at a time, so a read past the end
 * of an object fails a property. There are no assumptions and no CBMC intrinsics: cross_check.py compiles this file
 * natively and compares every function with the C library.
 */
typedef __SIZE_TYPE__ dawnr_size;
void *malloc(dawnr_size);

dawnr_size strnlen(const char *s, dawnr_size maxlen)
{
    dawnr_size n = 0;
    while (n < maxlen && s[n] != '\0') {
        ++n;
    }
    return n;
}

static int dawnr_in_set(char c, const char *set)
{
    for (dawnr_size i = 0; set[i] != '\0'; ++i) {
        if (set[i] == c) {
            return 1;
        }
    }
    return 0;
}

dawnr_size strspn(const char *s, const char *accept)
{
    dawnr_size n = 0;
    while (s[n] != '\0' && dawnr_in_set(s[n], accept)) {
        ++n;
    }
    return n;
}

dawnr_size strcspn(const char *s, const char *reject)
{
    dawnr_size n = 0;
    while (s[n] != '\0' && !dawnr_in_set(s[n], reject)) {
        ++n;
    }
    return n;
}

char *strpbrk(const char *s, const char *accept)
{
    for (; *s != '\0'; ++s) {
        if (dawnr_in_set(*s, accept)) {
            return (char *)s;
        }
    }
    return 0;
}

char *strstr(const char *haystack, const char *needle)
{
    for (;; ++haystack) {
        dawnr_size i = 0;
        while (needle[i] != '\0' && haystack[i] == needle[i]) {
            ++i;
        }
        if (needle[i] == '\0') {
            return (char *)haystack;
        }
        if (*haystack == '\0') {
            return 0;
        }
    }
}

void *memchr(const void *s, int c, dawnr_size n)
{
    const unsigned char *p = s;
    for (dawnr_size i = 0; i < n; ++i) {
        if (p[i] == (unsigned char)c) {
            return (void *)(p + i);
        }
    }
    return 0;
}

void *memrchr(const void *s, int c, dawnr_size n)
{
    const unsigned char *p = s;
    while (n > 0) {
        --n;
        if (p[n] == (unsigned char)c) {
            return (void *)(p + n);
        }
    }
    return 0;
}

char *strchrnul(const char *s, int c)
{
    while (*s != '\0' && *s != (char)c) {
        ++s;
    }
    return (char *)s;
}

char *strsep(char **stringp, const char *delim)
{
    char *start = *stringp;
    if (start == 0) {
        return 0;
    }
    char *end = start;
    while (*end != '\0' && !dawnr_in_set(*end, delim)) {
        ++end;
    }
    if (*end == '\0') {
        *stringp = 0;
    } else {
        *end = '\0';
        *stringp = end + 1;
    }
    return start;
}

char *strtok_r(char *str, const char *delim, char **saveptr)
{
    char *start = str != 0 ? str : *saveptr;
    while (*start != '\0' && dawnr_in_set(*start, delim)) {
        ++start;
    }
    if (*start == '\0') {
        *saveptr = start;
        return 0;
    }
    char *end = start;
    while (*end != '\0' && !dawnr_in_set(*end, delim)) {
        ++end;
    }
    if (*end == '\0') {
        *saveptr = end;
    } else {
        *end = '\0';
        *saveptr = end + 1;
    }
    return start;
}

char *strtok(char *str, const char *delim)
{
    static char *saved;
    return strtok_r(str, delim, &saved);
}

char *strndup(const char *s, dawnr_size n)
{
    dawnr_size length = strnlen(s, n);
    char *copy = malloc(length + 1);
    if (copy == 0) {
        return 0;
    }
    for (dawnr_size i = 0; i < length; ++i) {
        copy[i] = s[i];
    }
    copy[length] = '\0';
    return copy;
}
