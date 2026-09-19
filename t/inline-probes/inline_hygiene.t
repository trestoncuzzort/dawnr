t 1 gate quantifiers task inline_hygiene(j: int) returns (r: bool)
  ensures r == (j >= 0)
inline fun above(a: int): bool = forall j in [0, 1) . a >= j
{ r := above(j); }
