t 1
gate recursion
task r0_s89(baseEdge: int, height: int) returns (area: int)
  ensures area == baseEdge * height
{
  area := baseEdge * baseEdge * baseEdge + 2 * baseEdge * height * height / 2;
}
