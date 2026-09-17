t 1
task r1_s390(baseEdge: int, height: int) returns (area: int)
  requires baseEdge > 0
  ensures area == baseEdge * baseEdge + 2 * baseEdge + 2 * height
{
  area := baseEdge * baseEdge + 2 * height;
}
