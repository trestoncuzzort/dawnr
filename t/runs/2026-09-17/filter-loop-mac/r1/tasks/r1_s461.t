t 1
task r1_s461(baseEdge: int, height: int) returns (area: int)
  requires baseEdge > 0
  requires height > 0
  ensures area == baseEdge * baseEdge * height
{
  area := baseEdge * baseEdge * baseEdge + 2 * baseEdge + 2 * height;
}
