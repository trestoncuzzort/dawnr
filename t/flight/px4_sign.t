t 1
task px4_sign(val: int) returns (r: int)
  ensures val > 0 ==> r == 1
  ensures val == 0 ==> r == 0
  ensures val < 0 ==> r == -1
{
  var a: int := 0;
  if 0 < val {
    a := 1;
  }
  var b: int := 0;
  if val < 0 {
    b := 1;
  }
  r := a - b;
}
