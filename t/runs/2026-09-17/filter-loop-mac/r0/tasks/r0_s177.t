t 1
gate loops
task r0_s177(length: int, width: int) returns (r: int)
  ensures r == length * width
{
  r := length * width;
}
