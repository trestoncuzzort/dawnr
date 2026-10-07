t 1
task evens(s: seq) returns (r: seq)
  ensures r == [x for x in s if x % 2 == 0]
{
  var u: seq := [x for x in s if x % 2 == 0];
  r := u;
}
