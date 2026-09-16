t 1
task r2_s111(size: int) returns (volume: int)
  ensures volume == size * size * size
{
  volume := size * size;
}
