t 1
task r1_s59(arr: seq, k: int) returns (result: int)
  requires 1 <= k
  ensures result == arr[k - 1]
{
  result := arr[k - 1];
}
