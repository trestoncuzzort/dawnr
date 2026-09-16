t 1
task r1_s434(baseEdge: int, height: int) returns (area: int)
  ensures area == baseEdge * baseEdge + 2 * baseEdge + 2 * baseEdge * baseEdge + 2 * baseEdge * baseEdge + 2 * baseEdge + 2 * baseEdge * baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge * baseEdge + 2 * baseEdge * height
{
  area := baseEdge * baseEdge + 2 * baseEdge + 2 * baseEdge + 2 * baseEdge * baseEdge / 2;
}
