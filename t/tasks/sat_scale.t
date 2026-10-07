t 1
task sat_scale(x: float, k: float, lim: float) returns (r: float)
  requires lim >= float(0)
  requires abs(x) <= float(1000) and abs(k) <= float(1000)
  ensures abs(r) <= lim
  ensures abs(x * k) <= lim ==> r == x * k
{
  var v: float := x * k;
  if v > lim {
    r := lim;
  } else {
    if v < -lim {
      r := -lim;
    } else {
      r := v;
    }
  }
}
