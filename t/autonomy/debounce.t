t 1
task debounce(count: int, raw: bool, threshold: int) returns (c: int)
  requires 0 <= count and count <= threshold and threshold > 0
  ensures 0 <= c and c <= threshold
  ensures raw ==> c == min(count + 1, threshold)
  ensures not raw ==> c == 0
{
  if raw {
    c := min(count + 1, threshold);
  } else {
    c := 0;
  }
}
