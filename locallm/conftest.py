# test_baselines.py is a framework-free script (`python test_baselines.py`) that exits at import time, which
# pytest reads as an internal error at collection; it runs as one test through test_baselines_script.py.
# test_detectors.py likewise (its tests take the shingle function as a parameter and return (ok, note)).
collect_ignore = ["test_baselines.py", "test_detectors.py"]
