t 1
task px4_sumd_receive_any(sumd_data: array, length: int) returns (n: int)
  modifies sumd_data
  requires len(sumd_data) >= 2 and len(sumd_data) % 2 == 0
  requires 1 <= length and 2 * length <= len(sumd_data)
  ensures n == 2 * length
  ensures forall j in [1, n + 1) . j < len(sumd_data) ==> sumd_data[j] == j - 1
{
  var rxlen: int := 1;
  while rxlen <= 2 * length
    invariant 1 <= rxlen and rxlen <= 2 * length + 1
    invariant forall j in [1, rxlen) . j < len(sumd_data) ==> sumd_data[j] == j - 1
    decreases 2 * length + 1 - rxlen
  {
    sumd_data[rxlen] := rxlen - 1;
    rxlen := rxlen + 1;
  }
  n := rxlen - 1;
}
