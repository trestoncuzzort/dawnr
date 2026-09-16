t 1
gate quantifiers
task r1_s42(val: int) returns (val2: int)
  ensures val2 == double(val)
spec fun double(val_v: int): int
  decreases val_v
= 2 * val_v
{
  val2 := 2 * val;
}
