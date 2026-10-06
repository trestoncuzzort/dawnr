t 1 gate recursion
task average(s: seq) returns (r: real)
  requires len(s) > 0
  ensures r * real(len(s)) == real(sum_of(s, len(s)))
spec fun sum_of(row: seq, n: int): int decreases n = if n <= 0 or n > len(row) then 0 else sum_of(row, n - 1) + row[n - 1]
{
  r := real(sum_of(s, len(s))) / real(len(s));
}
