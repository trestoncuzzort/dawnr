t 1 task f(x: int) returns (r: int)
ensures true
{
  var i: int := 0;
  while true invariant true decreases x - i {
    i := i + 1;
  }
  r := i;
}
