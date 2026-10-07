datatype Shape = Circle(r: int) | Rect(w: int, h: int) | Dot
t 1
task shape_area(s: Shape) returns (a: int)
  requires case s { Circle(r) => r >= 0, Rect(w, h) => w >= 0 and h >= 0, Dot => true }
  ensures a >= 0
  ensures case s { Circle(r) => a == 3 * r * r, Rect(w, h) => a == w * h, Dot => a == 0 }
{
  a := case s { Circle(r) => 3 * r * r, Rect(w, h) => w * h, Dot => 0 };
}
