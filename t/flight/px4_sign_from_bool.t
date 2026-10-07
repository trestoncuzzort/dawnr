t 1
task px4_sign_from_bool(positive: bool) returns (r: int)
  ensures positive ==> r == 1
  ensures not positive ==> r == -1
{
  if positive {
    r := 1;
  } else {
    r := -1;
  }
}
