t 1
task cheapest(items: seq<(int, int)>) returns (r: (int, int))
  requires len(items) > 0
  ensures r in items
  ensures forall i in [0, len(items)) . r.1 <= items[i].1
{
  r := min_by(items, p => p.1);
}
