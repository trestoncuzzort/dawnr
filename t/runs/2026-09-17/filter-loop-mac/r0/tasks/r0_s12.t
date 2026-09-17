t 1
task r0_s12(baseEdge: int, height: int) returns (area: int)
  requires height > 0
  ensures area == baseEdge * baseEdge * baseEdge + 2 * baseEdge * height
{
  area := baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge * height;
}
