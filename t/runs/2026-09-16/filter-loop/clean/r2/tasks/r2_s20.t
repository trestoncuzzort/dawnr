t 1
gate loops
task r2_s20(costPrice: int, sellingPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  requires sellingPrice >= 0
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
