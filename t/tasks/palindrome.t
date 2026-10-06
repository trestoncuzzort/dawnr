t 1
task palindrome(s: seq) returns (r: bool)
  ensures r == (s == rev(s))
{
  var u: seq := rev(s);
  r := s == u;
}
