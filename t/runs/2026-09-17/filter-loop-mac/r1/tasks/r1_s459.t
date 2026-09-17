t 1
task r1_s459(costPrice: int, sellingPrice: int) returns (result: bool)
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
