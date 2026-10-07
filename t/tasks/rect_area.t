datatype Shape = Circle(r: int) | Rect(w: int, h: int)
t 1
task rect_area(s: Shape) returns (k: int)
  requires case s { Circle(r) => false, Rect(a, b) => true }
  ensures k == s.w * s.h
{
  k := s.w * s.h;
}
