t 1
task pid_step(err: float, integ: float, kp: float, ki: float, umin: float, umax: float) returns (u: float)
  requires umin <= umax
  requires abs(err) <= float(10000) and abs(integ) <= float(10000)
  requires abs(kp) <= float(1000) and abs(ki) <= float(1000)
  ensures umin <= u and u <= umax
  ensures umin <= kp * err + ki * integ and kp * err + ki * integ <= umax ==> u == kp * err + ki * integ
  ensures kp * err + ki * integ < umin ==> u == umin
  ensures kp * err + ki * integ > umax ==> u == umax
{
  var raw: float := kp * err + ki * integ;
  if raw < umin {
    u := umin;
  } else {
    if raw > umax {
      u := umax;
    } else {
      u := raw;
    }
  }
}
