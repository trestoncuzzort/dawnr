t 1
gate loops
task r1_s147(costPrice: int, sellingPrice: int) returns (result: bool)
  requires costPrice >= 0
  ensures result == (costPrice == sellingPrice)
{
  result := costPrice == sellingPrice;
}
