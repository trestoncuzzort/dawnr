/* What coap_opt_parse needs besides its own text, taken from libcoap
 * (https://github.com/obgm/libcoap) at the pinned revision. The blocks marked "lines a-b"
 * are copied unchanged from the named file.
 *
 * The files carry SPDX-License-Identifier: BSD-2-Clause. include/coap3/coap_option.h has
 * the notice "Copyright (C) 2010-2013,2022-2026 Olaf Bergmann <bergmann@tzi.org>" and
 * include/coap3/coap_pdu_internal.h has the notice "Copyright (C) 2010-2026 Olaf Bergmann
 * <bergmann@tzi.org>". The licence text of the project (file LICENSE) is:
 *
 * Copyright (c) 2010--2026, Olaf Bergmann and others
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *   o Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *
 *   o Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in
 *     the documentation and/or other materials provided with the
 *     distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
#include <assert.h>
#include <stddef.h>
#include <stdint.h>

/* include/coap3/coap_option.h, lines 144-158 */
/**
 * Use byte-oriented access methods here because sliding a complex struct
 * coap_opt_t over the data buffer may cause bus error on certain platforms.
 */
typedef uint8_t coap_opt_t;
#define PCHAR(p) ((coap_opt_t *)(p))

/**
 * Representation of CoAP options.
 */
typedef struct {
  uint16_t delta;
  size_t length;
  const uint8_t *value;
} coap_option_t;

/* include/coap3/coap_pdu_internal.h, line 96 */
#define COAP_PAYLOAD_START 0xFF /* payload marker */

/* Stand-in, not from libcoap: the debug log messages of coap_opt_parse do nothing. */
#define coap_log_debug(...) do { } while (0)

/* Not from libcoap: the buffer that the harness passes when the given length is 6 or more.
 * The longest option header is 5 bytes and the longest value 65804 bytes. */
static unsigned char case_buffer[65809];
