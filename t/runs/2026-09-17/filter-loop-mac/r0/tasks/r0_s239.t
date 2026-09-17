t 1
task r0_s239(baseEdge: int, height: int) returns (area: int)
  requires height > 0
  ensures area == baseEdge * baseEdge * baseEdge + 2 * baseEdge * height
{
  area := baseEdge * baseEdge * baseEdge + 2 * baseEdge * height;
}
