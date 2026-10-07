t 1
task all_pos_set(s: set) returns (b: bool)
  ensures b == (forall x in s . x > 0)
{
  b := forall x in s . x > 0;
}
