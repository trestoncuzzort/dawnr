t 1
task matrix_multiply(A: seq<seq>, B: seq<seq>) returns (C: seq<seq>)
  requires len(A) > 0 and len(B) > 0
  requires len(A[0]) == len(B)
  requires len(A) <= 10
  requires len(B) <= 10
  requires len(B[0]) <= 10
  requires forall i in [0, len(A)) . len(A[i]) == len(B)
  requires forall i in [0, len(B)) . len(B[i]) == len(B[0])
  requires forall i in [0, len(A)) . forall j in [0, len(A[i])) . 0 <= A[i][j] and A[i][j] <= 100
  requires forall i in [0, len(B)) . forall j in [0, len(B[i])) . 0 <= B[i][j] and B[i][j] <= 100
  ensures len(C) == len(A)
  ensures len(C) > 0 ==> len(C[0]) == len(B[0])
  ensures is_valid_matrix(C, len(A), len(B[0]))
  ensures forall i in [0, len(C)) . forall j in [0, len(C[0])) . C[i][j] == dot_product(A[i], B, j, len(B))
spec fun dot_product(row_vals: seq, B_vals: seq<seq>, c: int, k: int): int
  decreases k
= if k <= 0 or k > len(row_vals) or k > len(B_vals) or c < 0 or c >= len(B_vals[k - 1]) then 0
  else row_vals[k - 1] * B_vals[k - 1][c] + dot_product(row_vals, B_vals, c, k - 1)
spec fun is_valid_matrix(m: seq<seq>, rows: int, cols: int): bool
  decreases 0
= len(m) == rows and (forall i in [0, rows) . len(m[i]) == cols)
{
  C := [];
  var i: int := 0;
  while i < len(A)
    invariant 0 <= i and i <= len(A)
    invariant len(C) == i
    invariant forall x in [0, i) . len(C[x]) == len(B[0])
    invariant forall x in [0, i) . forall y in [0, len(B[0])) . C[x][y] == dot_product(A[x], B, y, len(B))
    decreases len(A) - i
  {
    var row: seq := [];
    var j: int := 0;
    while j < len(B[0])
      invariant 0 <= j and j <= len(B[0])
      invariant len(row) == j
      invariant forall y in [0, j) . row[y] == dot_product(A[i], B, y, len(B))
      decreases len(B[0]) - j
    {
      var acc: int := 0;
      var k: int := 0;
      while k < len(B)
        invariant 0 <= k and k <= len(B)
        invariant acc == dot_product(A[i], B, j, k)
        decreases len(B) - k
      {
        acc := acc + A[i][k] * B[k][j];
        k := k + 1;
      }
      row := row + [acc];
      j := j + 1;
    }
    C := C + [row];
    i := i + 1;
  }
}
