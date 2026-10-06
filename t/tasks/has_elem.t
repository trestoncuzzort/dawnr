t 1
task has_elem(s: seq, x: int) returns (r: int)
  ensures r == 1 or r == 0
  ensures (r == 1) == (x in s)
{
  if x in s {
    r := 1;
  } else {
    r := 0;
  }
}
