t 1
task aabb_overlap(ax: int, ay: int, aw: int, ah: int, bx: int, by: int, bw: int, bh: int) returns (hit: bool)
  requires aw >= 0 and ah >= 0 and bw >= 0 and bh >= 0
  ensures hit == (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah)
{
  hit := ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah;
}
