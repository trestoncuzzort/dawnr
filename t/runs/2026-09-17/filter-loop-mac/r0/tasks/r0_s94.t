t 1
task r0_s94(length: int, width: int) returns (r: int)
  requires width > 0
  ensures r == length * width
{
  r := length * width;
}
