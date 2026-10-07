t 1
task battery_level(mv: int) returns (level: int)
  requires mv >= 0
  ensures 0 <= level and level <= 3
  ensures mv < 3300 ==> level == 0
  ensures mv >= 3300 and mv < 3600 ==> level == 1
  ensures mv >= 3600 and mv < 3900 ==> level == 2
  ensures mv >= 3900 ==> level == 3
{
  if mv < 3300 {
    level := 0;
  } else {
    if mv < 3600 {
      level := 1;
    } else {
      if mv < 3900 {
        level := 2;
      } else {
        level := 3;
      }
    }
  }
}
