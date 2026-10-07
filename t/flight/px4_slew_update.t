t 1
task px4_slew_update(value: float, new_value: float, slew_rate: float, dt: float) returns (r: float)
  requires slew_rate >= float(0) and dt >= float(0)
  requires abs(value) <= float(1000000) and abs(new_value) <= float(1000000)
  requires slew_rate <= float(1000) and dt <= float(1000)
  ensures new_value - value > slew_rate * dt ==> r == value + slew_rate * dt
  ensures new_value - value < -(slew_rate * dt) ==> r == value + -(slew_rate * dt)
  ensures new_value - value >= -(slew_rate * dt) and new_value - value <= slew_rate * dt ==> r == value + (new_value - value)
{
  var dvalue_desired: float := new_value - value;
  var dvalue_max: float := slew_rate * dt;
  var dvalue: float := dvalue_desired;
  if dvalue_desired < -dvalue_max {
    dvalue := -dvalue_max;
  } else {
    if dvalue_desired > dvalue_max {
      dvalue := dvalue_max;
    }
  }
  r := value + dvalue;
}
