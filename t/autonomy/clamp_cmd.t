t 1
task clamp_cmd(u: float, lo: float, hi: float) returns (r: float)
  requires lo <= hi
  ensures lo <= r and r <= hi
  ensures lo <= u and u <= hi ==> r == u
  ensures u < lo ==> r == lo
  ensures u > hi ==> r == hi
{
  if u < lo {
    r := lo;
  } else {
    if u > hi {
      r := hi;
    } else {
      r := u;
    }
  }
}
