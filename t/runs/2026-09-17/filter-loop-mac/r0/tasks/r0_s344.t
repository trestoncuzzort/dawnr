t 1
gate loops
task r0_s344(baseEdge: int, height: int) returns (area: int)
  requires baseEdge > 0
  ensures area == baseEdge + 2 * baseEdge * height
{
  area := baseEdge * baseEdge + 2 * baseEdge * height;
}
