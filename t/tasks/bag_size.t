datatype Bag = Bag(items: seq, active: bool)
t 1
task bag_size(b: Bag) returns (n: int)
  ensures b.active ==> n == len(b.items)
  ensures not b.active ==> n == 0
{
  if b.active {
    n := len(b.items);
  } else {
    n := 0;
  }
}
