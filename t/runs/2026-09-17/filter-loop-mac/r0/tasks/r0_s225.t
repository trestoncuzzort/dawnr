t 1
gate loops
task r0_s225(baseEdge: int, height: int) returns (area: int)
  requires baseEdge > 0
  requires height > 0
  ensures area == baseEdge * baseEdge + 2 * baseEdge * height
{
  area := baseEdge * height * baseEdge + 2 * baseEdge * height / 2;
}
