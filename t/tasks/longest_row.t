t 1
task longest_row(rows: seq<seq>) returns (r: seq)
  requires len(rows) > 0
  ensures r in rows
  ensures forall i in [0, len(rows)) . len(rows[i]) <= len(r)
{
  r := max_by(rows, w => len(w));
}
