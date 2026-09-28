datatype Color = Red | Green
t 1 task f(c: Color) returns (r: int) ensures true
{
  r := case c { Red => 1, Green => false }
}
