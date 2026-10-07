datatype Point = Point(x: int, y: int)
t 1
task manhattan(p: Point, q: Point) returns (d: int)
  ensures d >= 0
  ensures d == abs(p.x - q.x) + abs(p.y - q.y)
{
  d := abs(p.x - q.x) + abs(p.y - q.y);
}
