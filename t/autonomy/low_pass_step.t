t 1
task low_pass_step(prev: int, x: int, num: int, den: int) returns (y: int)
  requires den > 0 and 0 <= num and num <= den
  ensures min(prev, x) <= y and y <= max(prev, x)
  ensures num == 0 ==> y == prev
  ensures num == den ==> y == x
{
  y := prev + ((x - prev) * num) / den;
}
