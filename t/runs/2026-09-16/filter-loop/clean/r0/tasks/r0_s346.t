t 1
task r0_s346(costPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
