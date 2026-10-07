datatype Res = Ok(vals: seq) | Err(code: int)
t 1
task checked_tail(s: seq) returns (r: Res)
  ensures len(s) == 0 ==> r == Res.Err(1)
  ensures len(s) > 0 ==> r == Res.Ok(s[1..])
{
  if len(s) == 0 {
    r := Res.Err(1);
  } else {
    r := Res.Ok(s[1..]);
  }
}
