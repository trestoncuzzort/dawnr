t 1
task r1_s86(length: int, width: int) returns (r: int)
  ensures r == length * width
{
  r := length / 2;
}
