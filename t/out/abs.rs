use vstd::prelude::*;

verus! {

proof fn abs(x: int) -> (r: int)
    ensures
        (r >= (0int)),
        ((r == x) || (r == (-x))),
{
    if (x < (0int)) { (-x) } else { x }
}

} // verus!

fn main() {}
