t 1
task r1_s30(arr: seq, k: int, k: int) returns (result: int)
  requires 1 <= k
  ensures result == arr[k - 1]
  ensures result == arr[k - 1]
{
  result := arr[k - 1];
}
