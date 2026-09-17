t 1
task r0_s393(baseEdge: int, height: int) returns (area: int)
  requires baseEdge >= 0
  ensures area == baseEdge * baseEdge + 2 * baseEdge * height
{
  area := baseEdge + 2 * baseEdge * height / 2;
}
