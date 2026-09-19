# usage: repin-census.py <lifted> <sweep_rows> <all_seven> <all_seven_infrag>
import sys,re
lifted, rows, a7, a7in = map(int, sys.argv[1:5])
p='$HOME/tup/t/test_mbpp_lifter_census.py'; s=open(p).read()
s=re.sub(r'assert len\(sweep\) == len\(row_lines\) == \d+', f'assert len(sweep) == len(row_lines) == {rows}', s)
s=re.sub(r'assert all_seven == \d+, f"all-seven count \{all_seven\}, expected \d+"', f'assert all_seven == {a7}, f"all-seven count {{all_seven}}, expected {a7}"', s)
s=re.sub(r'    assert lifted == \d+, lifted', f'    assert lifted == {lifted}, lifted', s)
s=re.sub(r'    assert all_seven == \d+, all_seven', f'    assert all_seven == {a7}, all_seven', s)
s=re.sub(r'    assert all_seven_infrag == \d+, all_seven_infrag', f'    assert all_seven_infrag == {a7in}, all_seven_infrag', s)
s=re.sub(r'    assert covered0 == \d+, covered0', f'    assert covered0 == {a7in}, covered0', s)
open(p,'w').write(s); print("re-pinned", lifted, rows, a7, a7in)
