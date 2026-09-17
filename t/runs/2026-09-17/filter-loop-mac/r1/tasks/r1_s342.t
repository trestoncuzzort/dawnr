t 1
task r1_s342(size: int) returns (r: int)
  ensures r == 5 * size
{
  r := 6 * size;
}
