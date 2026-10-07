#!/usr/bin/env python3
"""framac_lib.py: SPEC.md "The library (v1)" and max/min of one argument ("Reductions (v1)") in the Frama-C lowering
(PREDICT T11, 2026-10-06; internal/RESEARCH-2026-10-06-landscape.md decision D1).

The library is two things here, the pattern the string library already uses (`t_count_c`): ACSL `logic` definitions
for specification positions (recursive ones paired with the termination lemma the lowering emits for a recursive spec
function, so WP proves the measure and nothing is assumed), and, in executable position, small C helper functions
whose loops mirror the logic recursion one step per iteration, each with its own contract, proved by WP once and
called from the task's body. `min`, `max` and `abs` need neither: ACSL's own `\\min`, `\\max`, `\\abs` in a
specification, a C conditional in code. No ACSL `axiom` is emitted. Measured first on two hand probes under the
adapter's own WP flags (scratch p1.c, p2.c, 2026-10-06): every functional goal proved."""
from __future__ import annotations

# "rev" since PREDICT T20 (2026-10-07): no prelude; an element rewrite in ACSL (_seq_at_render) and T19's write loop in
# code (seq_assign_lines), both in lower_framac
FRAMAC_LIB = frozenset({"min", "max", "abs", "gcd", "pow", "isqrt", "sum", "maxs", "in", "rev"})

_TEXT: dict[str, str] = {}

_TEXT["gcd"] = r"""/*@ logic integer t_gcdn(integer a, integer b) = b <= 0 ? a : t_gcdn(b, a % b);
    logic integer t_gcd(integer a, integer b) = t_gcdn(\abs(a), \abs(b));
*/
/*@ lemma t_gcdn_terminates: \forall integer a, b; b > 0 && a >= 0 ==> 0 <= a % b < b;
*/
/*@ requires \true;
    assigns \nothing;
    ensures \result == t_gcd(a, b);
    ensures \result >= 0;
*/
int t_gcd_c(int a, int b) {
  int x = a < 0 ? -a : a;
  int y = b < 0 ? -b : b;
  /*@ loop invariant x >= 0 && y >= 0;
      loop invariant t_gcdn(x, y) == t_gcd(a, b);
      loop assigns x, y;
      loop variant y;
  */
  while (y > 0) {
    int t = x % y;
    x = y;
    y = t;
  }
  return x;
}
"""

_TEXT["pow"] = r"""/*@ logic integer t_pow(integer a, integer n) = n <= 0 ? 1 : a * t_pow(a, n - 1);
*/
/*@ lemma t_pow_terminates: \forall integer n; !(n <= 0) ==> 0 <= n - 1 < n;
*/
/*@ requires n >= 0;
    assigns \nothing;
    ensures \result == t_pow(a, n);
*/
int t_pow_c(int a, int n) {
  int r = 1;
  int k = 0;
  /*@ loop invariant 0 <= k <= n;
      loop invariant r == t_pow(a, k);
      loop assigns r, k;
      loop variant n - k;
  */
  while (k < n) {
    r = a * r;
    k = k + 1;
  }
  return r;
}
"""

_TEXT["isqrt"] = r"""/*@ logic integer t_isqrt(integer n) =
      n <= 0 ? 0 : ((t_isqrt(n - 1) + 1) * (t_isqrt(n - 1) + 1) <= n ? t_isqrt(n - 1) + 1 : t_isqrt(n - 1));
*/
/*@ lemma t_isqrt_terminates: \forall integer n; !(n <= 0) ==> 0 <= n - 1 < n;
*/
/*@ requires n >= 0;
    assigns \nothing;
    ensures \result == t_isqrt(n);
    ensures 0 <= \result && \result * \result <= n && n < (\result + 1) * (\result + 1);
*/
int t_isqrt_c(int n) {
  int r = 0;
  int k = 0;
  /*@ loop invariant 0 <= k <= n;
      loop invariant r == t_isqrt(k);
      loop invariant 0 <= r && r * r <= k && k < (r + 1) * (r + 1);
      loop assigns r, k;
      loop variant n - k;
  */
  while (k < n) {
    k = k + 1;
    if ((r + 1) * (r + 1) <= k) {
      r = r + 1;
    }
  }
  return r;
}
"""

_TEXT["sum"] = r"""/*@ logic integer t_sum{L}(int *s, integer n) = n <= 0 ? 0 : t_sum{L}(s, n - 1) + s[n - 1];
*/
/*@ lemma t_sum_terminates: \forall integer n; !(n <= 0) ==> 0 <= n - 1 < n;
*/
/*@ requires s_n >= 0;
    requires \valid_read(s + (0 .. s_n - 1));
    assigns \nothing;
    ensures \result == t_sum(s, s_n);
*/
int t_sum_c(int *s, int s_n) {
  int r = 0;
  int i = 0;
  /*@ loop invariant 0 <= i <= s_n;
      loop invariant r == t_sum(s, i);
      loop assigns r, i;
      loop variant s_n - i;
  */
  while (i < s_n) {
    r = r + s[i];
    i = i + 1;
  }
  return r;
}
"""

_TEXT["maxs"] = r"""/*@ logic integer t_maxs{L}(int *s, integer n) =
      n <= 1 ? s[0] : (t_maxs{L}(s, n - 1) < s[n - 1] ? s[n - 1] : t_maxs{L}(s, n - 1));
    logic integer t_mins{L}(int *s, integer n) =
      n <= 1 ? s[0] : (s[n - 1] < t_mins{L}(s, n - 1) ? s[n - 1] : t_mins{L}(s, n - 1));
*/
/*@ lemma t_maxs_terminates: \forall integer n; !(n <= 1) ==> 0 <= n - 1 < n;
*/
/*@ lemma t_mins_terminates: \forall integer n; !(n <= 1) ==> 0 <= n - 1 < n;
*/
/*@ requires s_n > 0;
    requires \valid_read(s + (0 .. s_n - 1));
    assigns \nothing;
    ensures \result == t_maxs(s, s_n);
    ensures \exists integer k; 0 <= k < s_n && s[k] == \result;
    ensures \forall integer i; 0 <= i < s_n ==> s[i] <= \result;
*/
int t_maxs_c(int *s, int s_n) {
  int m = s[0];
  int i = 1;
  /*@ loop invariant 1 <= i <= s_n;
      loop invariant m == t_maxs(s, i);
      loop invariant \exists integer k; 0 <= k < i && s[k] == m;
      loop invariant \forall integer j; 0 <= j < i ==> s[j] <= m;
      loop assigns m, i;
      loop variant s_n - i;
  */
  while (i < s_n) {
    if (m < s[i]) {
      m = s[i];
    }
    i = i + 1;
  }
  return m;
}
/*@ requires s_n > 0;
    requires \valid_read(s + (0 .. s_n - 1));
    assigns \nothing;
    ensures \result == t_mins(s, s_n);
    ensures \exists integer k; 0 <= k < s_n && s[k] == \result;
    ensures \forall integer i; 0 <= i < s_n ==> \result <= s[i];
*/
int t_mins_c(int *s, int s_n) {
  int m = s[0];
  int i = 1;
  /*@ loop invariant 1 <= i <= s_n;
      loop invariant m == t_mins(s, i);
      loop invariant \exists integer k; 0 <= k < i && s[k] == m;
      loop invariant \forall integer j; 0 <= j < i ==> m <= s[j];
      loop assigns m, i;
      loop variant s_n - i;
  */
  while (i < s_n) {
    if (s[i] < m) {
      m = s[i];
    }
    i = i + 1;
  }
  return m;
}
"""

_TEXT["in"] = r"""/*@ requires s_n >= 0;
    requires \valid_read(s + (0 .. s_n - 1));
    assigns \nothing;
    ensures \result == 0 || \result == 1;
    ensures (\result == 1) <==> (\exists integer k; 0 <= k < s_n && s[k] == x);
*/
int t_memb_c(int *s, int s_n, int x) {
  int i = 0;
  /*@ loop invariant 0 <= i <= s_n;
      loop invariant \forall integer k; 0 <= k < i ==> s[k] != x;
      loop assigns i;
      loop variant s_n - i;
  */
  while (i < s_n) {
    if (s[i] == x) {
      return 1;
    }
    i = i + 1;
  }
  return 0;
}
"""

_ORDER = ["gcd", "pow", "isqrt", "sum", "maxs", "in"]


def used(x) -> set:
    """The prelude pieces a task part needs ("maxs" for max/min of one argument; min, max and abs need none)."""
    out: set = set()

    def walk(y):
        if isinstance(y, dict):
            op = y.get("op")
            if op in ("min", "max") and len(y.get("args", [])) == 1:
                out.add("maxs")
            elif op in ("gcd", "pow", "isqrt", "sum", "in"):
                out.add(op)
            for v in y.values():
                walk(v)
        elif isinstance(y, list):
            for v in y:
                walk(v)
    walk(x)
    return out


def prelude(pieces: set) -> str:
    return "\n".join(_TEXT[p] for p in _ORDER if p in pieces)
