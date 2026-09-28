datatype Color = Red | Green | Blue
t 1
task color_code(c: Color) returns (r: int)
  ensures r >= 0
  ensures r <= 2
  ensures c == Color.Red ==> r == 0
  ensures c == Color.Green ==> r == 1
  ensures c == Color.Blue ==> r == 2
{
  r := case c { Red => 0, Green => 1, Blue => 2 };
}
