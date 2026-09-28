t 1
task set_toggle(a: set, x: int) returns (r: set)
  ensures x in a ==> card(r) == card(a) - 1
  ensures not (x in a) ==> card(r) == card(a) + 1
  ensures x in a ==> not (x in r)
  ensures not (x in a) ==> x in r
{
  if x in a {
    r := setminus(a, {x});
  } else {
    r := union(a, {x});
  }
}
