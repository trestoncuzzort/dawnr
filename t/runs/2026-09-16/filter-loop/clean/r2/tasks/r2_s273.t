t 1
gate loops
task r2_s273(costPrice: int, sellingPrice: int, sellingPrice: int) returns (result: bool)
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
