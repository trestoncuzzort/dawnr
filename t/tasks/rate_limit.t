t 1
task rate_limit(prev: float, target: float, step: float) returns (r: float)
  requires step >= float(0)
  requires abs(prev) <= float(1000000) and abs(target) <= float(1000000) and step <= float(1000000)
  ensures r <= prev + step and r >= prev - step
  ensures target <= prev + step and target >= prev - step ==> r == target
  ensures target > prev + step ==> r == prev + step
  ensures target < prev - step ==> r == prev - step
{
  if target > prev + step {
    r := prev + step;
  } else {
    if target < prev - step {
      r := prev - step;
    } else {
      r := target;
    }
  }
}
