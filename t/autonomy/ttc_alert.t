t 1
task ttc_alert(range: float, closing: float, twarn: float) returns (alert: bool)
  requires range >= float(0) and range <= float(100000)
  requires abs(closing) <= float(1000) and twarn >= float(0) and twarn <= float(100)
  ensures alert == (closing > float(0) and range <= closing * twarn)
{
  alert := false;
  if closing > float(0) {
    if range <= closing * twarn {
      alert := true;
    }
  }
}
