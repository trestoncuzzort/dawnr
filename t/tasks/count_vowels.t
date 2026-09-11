t 1
gate loops
task count_vowels(s: seq) returns (r: int)
  ensures r == s.count([97]) + s.count([101]) + s.count([105]) + s.count([111]) + s.count([117])
{
  r := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant r == s[0..i].count([97]) + s[0..i].count([101]) + s[0..i].count([105]) + s[0..i].count([111]) + s[0..i].count([117])
    decreases len(s) - i
  {
    if (((s[i] == 97 or s[i] == 101) or s[i] == 105) or s[i] == 111) or s[i] == 117 {
      r := r + 1;
    } else {
    }
    i := i + 1;
  }
}
