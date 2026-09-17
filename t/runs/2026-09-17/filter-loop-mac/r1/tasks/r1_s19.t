t 1
task r1_s19(costPrice: int, sellingPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  requires sellingPrice >= 0
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
