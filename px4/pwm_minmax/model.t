t 1
task pwm_min_le_max(mn: int, mx: int) returns (r: (int, int))
  requires 0 <= mn and mn <= 65535 and 0 <= mx and mx <= 65535
  ensures r.0 <= r.1
  ensures (mn <= mx) ==> (r.0 == mn and r.1 == mx)
{
  if mn > mx { r := (mx, mn); } else { r := (mn, mx); }
}
