t 1 gate recursion
task grid_row_sums(m: seq<seq>) returns (r: seq)
  ensures len(r) == len(m)
  ensures forall i in [0, len(m)) . r[i] == row_total(m[i], len(m[i]))
spec fun row_total(row: seq, n: int): int decreases n = if n <= 0 or n > len(row) then 0 else row_total(row, n - 1) + row[n - 1]
{
  var acc: seq := [];
  var i: int := 0;
  while i < len(m)
    invariant 0 <= i and i <= len(m)
    invariant len(acc) == i
    invariant forall j in [0, i) . acc[j] == row_total(m[j], len(m[j]))
    decreases len(m) - i
  {
    acc := acc + [row_total(m[i], len(m[i]))];
    i := i + 1;
  }
  r := acc;
}
