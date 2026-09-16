t 1
task r2_s98(costPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  requires sellingPrice >= 0
  requires sellingPrice >= 0
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
