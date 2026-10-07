t 1
task px4_constrain_f(val: float, min_val: float, max_val: float) returns (r: float)
  requires min_val <= max_val
  ensures min_val <= r and r <= max_val
  ensures min_val <= val and val <= max_val ==> r == val
  ensures val < min_val ==> r == min_val
  ensures val > max_val ==> r == max_val
{
  if val < min_val {
    r := min_val;
  } else {
    if val > max_val {
      r := max_val;
    } else {
      r := val;
    }
  }
}
