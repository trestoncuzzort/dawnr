datatype Color = Red
t 1 task f() returns (r: bool) ensures true
{
  r := Color.Red(1) == Color.Red
}
