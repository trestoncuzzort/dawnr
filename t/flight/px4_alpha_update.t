t 1
task px4_alpha_update(state: float, sample: float, alpha: float) returns (r: float)
  requires abs(state) <= float(1000000) and abs(sample) <= float(1000000)
  requires float(0) <= alpha and alpha <= float(1)
  ensures alpha == float(0) ==> r == state
  ensures r == state + alpha * (sample - state)
{
  r := state + alpha * (sample - state);
}
