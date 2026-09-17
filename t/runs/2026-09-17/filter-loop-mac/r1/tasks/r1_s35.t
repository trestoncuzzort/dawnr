t 1
task r1_s35(costPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  ensures result == (costPrice == sellingPrice - 1)
{
  result := costPrice == sellingPrice;
}
