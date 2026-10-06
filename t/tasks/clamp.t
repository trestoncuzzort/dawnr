t 1
task clamp(x: int, lo: int, hi: int) returns (r: int)
  requires lo <= hi
  ensures lo <= r and r <= hi
  ensures lo <= x and x <= hi ==> r == x
{
  r := max(lo, min(hi, x));
}
