t 1
task r0_s28(char: int, integer: int) returns (r: int)
  ensures r >= char
  ensures r == char or r == integer
{
  var assigns: int := char;
  if assigns >= integer {
    r := assigns;
  } else {
    r := integer;
  }
}
