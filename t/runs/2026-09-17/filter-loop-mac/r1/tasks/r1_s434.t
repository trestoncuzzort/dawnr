t 1
task r1_s434(costPrice: int, sellingPrice: int) returns (loss: int)
  requires costPrice > 0
  ensures costPrice <= sellingPrice ==> loss == 0
{
  if costPrice > sellingPrice {
    loss := costPrice - sellingPrice;
  } else {
    loss := 0;
  }
}
