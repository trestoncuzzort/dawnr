t 1
task px4_arm_param_fixed(p: int) returns (r: int)
  requires -2147483648 <= p and p <= 2147483647
  ensures p == 1 ==> r == 1
  ensures p == 0 ==> r == 0
  ensures p != 0 and p != 1 ==> r == -1
{
  var a: int := -1;
  if -128 <= p and p <= 127 {
    a := p;
  }
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
