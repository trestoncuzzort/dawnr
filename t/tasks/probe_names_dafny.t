t 1
task probe_names_dafny(function: int, method: int) returns (r: int)
  ensures r >= function
  ensures r >= method
  ensures r == function or r == method
{
  var predicate: int := function;
  if predicate >= method {
    r := predicate;
  } else {
    r := method;
  }
}
