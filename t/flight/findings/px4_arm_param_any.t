t 1
task px4_arm_param_any(p: int) returns (r: int)
  requires -2147483648 <= p and p <= 2147483647
  ensures p == 1 ==> r == 1
  ensures p == 0 ==> r == 0
  ensures p != 0 and p != 1 ==> r == -1
{
  var a: int := (p + 128) % 256 - 128;
  if a == 1 {
    r := 1;
  } else {
    if a == 0 {
      r := 0;
    } else {
      r := -1;
    }
  }
}
