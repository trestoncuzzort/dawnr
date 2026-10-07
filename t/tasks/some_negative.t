datatype Opt = None | Some(v: int)
t 1
task some_negative(s: seq) returns (r: Opt)
  ensures case r { None => forall k in [0, len(s)) . s[k] >= 0, Some(v) => v < 0 and v in s }
{
  r := Opt.None;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant case r { None => forall k in [0, i) . s[k] >= 0, Some(v) => v < 0 and v in s }
    decreases len(s) - i
  {
    if s[i] < 0 {
      r := Opt.Some(s[i]);
    }
    i := i + 1;
  }
}
