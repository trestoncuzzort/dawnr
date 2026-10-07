t 1
task rev_equal(a: seq, b: seq) returns (r: bool)
  ensures r == (b == rev(a))
{
  var u: seq := rev(a);
  r := u == b;
}
