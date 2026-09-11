t 1
task probe_names_framac(char: int, integer: int) returns (r: int)
  ensures r >= char
  ensures r >= integer
  ensures r == char or r == integer
{
  var assigns: int := char;
  if assigns >= integer {
    r := assigns;
  } else {
    r := integer;
  }
}
