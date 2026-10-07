t 1
task grid_cell(x: int, y: int, cell: int, cols: int, rows: int) returns (idx: int)
  requires cell > 0 and cols > 0 and rows > 0
  requires 0 <= x and x < cell * cols and 0 <= y and y < cell * rows
  ensures 0 <= idx and idx < cols * rows
  ensures idx == (y / cell) * cols + x / cell
{
  idx := (y / cell) * cols + x / cell;
}
