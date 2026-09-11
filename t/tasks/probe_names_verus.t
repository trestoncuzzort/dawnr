t 1
task probe_names_verus(proof: int, ghost: int) returns (r: int)
  ensures r >= proof
  ensures r >= ghost
  ensures r == proof or r == ghost
{
  var exec: int := proof;
  if exec >= ghost {
    r := exec;
  } else {
    r := ghost;
  }
}
