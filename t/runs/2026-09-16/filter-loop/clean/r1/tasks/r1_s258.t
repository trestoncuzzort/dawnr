t 1
gate loops
task r1_s258(proof: int, ghost: int) returns (r: int)
  ensures r >= ghost
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
