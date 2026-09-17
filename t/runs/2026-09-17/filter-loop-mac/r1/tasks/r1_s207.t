t 1
task r1_s207(baseEdge: int, height: int) returns (area: int)
  requires baseEdge > 0
  ensures area == baseEdge * height
{
  area := baseEdge * baseEdge + 2 * height;
}
