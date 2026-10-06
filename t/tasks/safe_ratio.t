t 1
task safe_ratio(a: real, b: real) returns (r: real)
  ensures b != 0.0 ==> r * b == a
  ensures b == 0.0 ==> r == 0.0
{
  if b != 0.0 {
    r := a / b;
  } else {
    r := 0.0;
  }
}
