t 1
task arm_check(battery_pct: int, gps_fix: bool, imu_ok: bool, mode: int) returns (ok: bool)
  ensures ok == (battery_pct >= 30 and gps_fix and imu_ok and mode == 0)
{
  ok := false;
  if battery_pct >= 30 {
    if gps_fix and imu_ok {
      if mode == 0 {
        ok := true;
      }
    }
  }
}
