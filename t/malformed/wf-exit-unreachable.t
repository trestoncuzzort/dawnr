t 1 task f(x: int) returns (r: int)
ensures true
{
  var i: int := 0;
  while i < x invariant true decreases x - i {
    break;
    i := i + 1;
  }
  r := i;
}
