from pathlib import Path

from locallm import model_memory as memory


def test_all_shards_count_toward_loading_memory(tmp_path):
    for index, size in enumerate([10, 20, 30], 1):
        (tmp_path / f'model-{index:05d}-of-00003.gguf').write_bytes(b'x' * size)
    assert memory.model_bytes(tmp_path/'model-00001-of-00003.gguf') == 60


def test_parent_container_limit_wins_over_host_memory(tmp_path):
    proc, groups = tmp_path/'proc', tmp_path/'cgroups'
    (proc/'self').mkdir(parents=True)
    (proc/'meminfo').write_text('MemAvailable: 67108864 kB\n')
    (proc/'self/cgroup').write_text('0::/container/worker\n')
    leaf = groups/'container/worker'
    leaf.mkdir(parents=True)
    (leaf/'memory.max').write_text('max\n')
    (leaf.parent/'memory.max').write_text(str(8 * 1024**3))
    (leaf.parent/'memory.current').write_text(str(1024**3))
    assert memory.available_bytes(proc, groups) == 7 * 1024**3


def test_missing_container_metadata_keeps_the_host_measurement(tmp_path):
    (tmp_path/'meminfo').write_text('MemAvailable: 1234 kB\n')
    assert memory.available_bytes(tmp_path, tmp_path/'absent') == 1234 * 1024


def test_unknown_memory_or_missing_weights_do_not_invent_a_limit(tmp_path):
    assert memory.available_bytes(tmp_path, tmp_path/'absent') is None
    assert not memory.prefer_small_buffers([tmp_path/'missing.gguf'], None)
    assert not memory.prefer_small_buffers([tmp_path/'missing.gguf'], 1)


def test_small_machine_uses_smaller_buffers_and_large_machine_keeps_default(tmp_path):
    model = tmp_path/'model.gguf'
    model.write_bytes(b'weights')
    assert memory.prefer_small_buffers([model], memory.RESERVE)
    assert not memory.prefer_small_buffers([model], memory.RESERVE + 100)
