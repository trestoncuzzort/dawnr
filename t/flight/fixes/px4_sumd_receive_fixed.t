t 1
task px4_sumd_receive_fixed(sumd_data: array, length: int) returns (n: int)
  modifies sumd_data
  requires len(sumd_data) >= 2 and len(sumd_data) % 2 == 0
  requires 1 <= length and 2 * length <= len(sumd_data)
  ensures n == 2 * length and n <= len(sumd_data)
  ensures forall k in [0, n) . sumd_data[k] == k
{
  var rxlen: int := 1;
  while rxlen <= 2 * length
    invariant 1 <= rxlen and rxlen <= 2 * length + 1
    invariant 2 * length <= len(sumd_data)
    invariant forall k in [0, rxlen - 1) . sumd_data[k] == k
    decreases 2 * length + 1 - rxlen
  {
    sumd_data[rxlen - 1] := rxlen - 1;
    rxlen := rxlen + 1;
  }
  n := rxlen - 1;
}
