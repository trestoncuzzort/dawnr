t 1
task swap_ends(p: ((int, int), (int, int))) returns (r: ((int, int), (int, int)))
  ensures r.0 == p.1
  ensures r.1 == p.0
{
  r := (p.1, p.0);
}
