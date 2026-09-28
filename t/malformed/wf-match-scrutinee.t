t 1 task f() returns (r: bool) ensures true
{
  r := case 1 { Red => true, Green => false }
}
