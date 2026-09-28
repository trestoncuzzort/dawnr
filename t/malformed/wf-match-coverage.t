datatype Color = Red | Green
t 1 task f(c: Color) returns (r: bool) ensures true
{
  r := case c { Red => true }
}
