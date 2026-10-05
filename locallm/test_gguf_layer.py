"""gguf_layer.py: a model file given the layer its publisher left out, every weight it had left as it was. The files
here are made by hand, a few hundred bytes each, in GGUF's own layout."""
import hashlib
import struct

import pytest

from locallm import gguf_layer as gl


def s(text):
    raw = text.encode()
    return struct.pack("<Q", len(raw)) + raw


def gguf(path, tensors, blocks, extra_keys=b"", n_extra=0, arch="toy"):
    """A small GGUF: an architecture, a block count, an array of strings (to be skipped), and the tensors' bytes."""
    kv = (s("general.architecture") + struct.pack("<I", 8) + s(arch)
          + s(f"{arch}.block_count") + struct.pack("<II", 4, blocks)
          + s("tokenizer.tokens") + struct.pack("<IIQ", 9, 8, 3) + s("a") + s("bb") + s("ccc")
          + s("general.quantization_version") + struct.pack("<II", 4, 2) + extra_keys)
    infos, data = b"", b""
    for name, dims, kind, payload in tensors:
        infos += gl._info(name, dims, kind, len(data))
        data += payload + b"\0" * (-len(payload) % 32)
    head = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), 4 + n_extra) + kv + infos
    path.write_bytes(head + b"\0" * (-len(head) % 32) + data)
    return path


A, B = bytes(range(64)), bytes(range(64, 160))                    # two tensors of the base
X, Y = b"\x07" * 32, b"\x09" * 64                                 # the layer


def manifest(tail_bytes, **changes):
    return dict({"architecture": "toy", "blocks": 3, "layers": 1, "bytes": len(tail_bytes),
                 "sha256": hashlib.sha256(tail_bytes).hexdigest(),
                 "tensors": [("blk.2.w", [4, 8], 0, 32), ("blk.2.nextn.h", [64], 0, 64)]}, **changes)


def test_the_layer_is_appended_and_every_byte_of_the_base_tensors_is_as_it_was(tmp_path):
    base = gguf(tmp_path / "base.gguf", [("blk.0.w", [8, 8], 0, A), ("blk.1.w", [96], 0, B)], blocks=2)
    (tmp_path / "tail.bin").write_bytes(X + Y)
    got = gl.add(base, tmp_path / "tail.bin", tmp_path / "out.gguf", manifest(X + Y))
    before, after = gl.header(base), gl.header(tmp_path / "out.gguf")
    assert got["tensors"] == 4 and got["added"] == 2 and after["n_kv"] == before["n_kv"] + 1
    assert [t[0] for t in after["tensors"]] == ["blk.0.w", "blk.1.w", "blk.2.w", "blk.2.nextn.h"]
    assert after["tensors"][:2] == before["tensors"]              # names, shapes, types and offsets of the base: unchanged
    out = (tmp_path / "out.gguf").read_bytes()
    data = out[after["data"]:]
    assert data[:64] == A and data[64:160] == B                   # the base's tensor bytes, in place
    assert data[after["tensors"][2][3]:][:32] == X and data[after["tensors"][3][3]:][:64] == Y
    assert all(t[3] % 32 == 0 for t in after["tensors"]) and after["data"] % 32 == 0
    kind, at = after["keys"]["toy.block_count"]
    assert struct.unpack("<I", out[at:at + 4]) == (3,) and after["keys"]["toy.nextn_predict_layers"][0] == 4
    assert out[after["keys"]["toy.nextn_predict_layers"][1]:][:4] == struct.pack("<I", 1)


def test_cutting_a_full_file_gives_back_the_layer_and_adding_it_to_the_base_rebuilds_the_full_file(tmp_path):
    full = gguf(tmp_path / "full.gguf", [("blk.0.w", [8, 8], 0, A), ("blk.1.w", [96], 0, B), ("blk.2.w", [4, 8], 0, X), ("blk.2.nextn.h", [64], 0, Y)],
                blocks=3, extra_keys=s("toy.nextn_predict_layers") + struct.pack("<II", 4, 1), n_extra=1)
    cut = gl.tail(full, tmp_path / "tail.bin")
    assert (tmp_path / "tail.bin").read_bytes() == X + Y and cut["bytes"] == 96 and cut["sha256"] == hashlib.sha256(X + Y).hexdigest()
    assert cut["tensors"] == [("blk.2.w", [4, 8], 0, 32), ("blk.2.nextn.h", [64], 0, 64)] and "'blk.2.w'" in gl.json_lines(cut)
    base = gguf(tmp_path / "base.gguf", [("blk.0.w", [8, 8], 0, A), ("blk.1.w", [96], 0, B)], blocks=2)
    gl.add(base, tmp_path / "tail.bin", tmp_path / "out.gguf", manifest(X + Y))
    assert (tmp_path / "out.gguf").read_bytes() == full.read_bytes()


def test_what_it_cannot_extend_is_refused_with_the_reason(tmp_path):
    base = gguf(tmp_path / "base.gguf", [("blk.0.w", [8, 8], 0, A), ("blk.1.w", [96], 0, B)], blocks=2)
    tail = tmp_path / "tail.bin"
    tail.write_bytes(X + Y)
    out = tmp_path / "out.gguf"
    with pytest.raises(gl.Bad, match="is not the layer the manifest names"):
        gl.add(base, tail, out, manifest(X + Y, sha256="0" * 64))
    with pytest.raises(gl.Bad, match="is not a other model"):
        gl.add(base, tail, out, manifest(X + Y, architecture="other"))
    with pytest.raises(gl.Bad, match="has 2 blocks, not the 4"):
        gl.add(base, tail, out, manifest(X + Y, blocks=5))
    gl.add(base, tail, out, manifest(X + Y))
    with pytest.raises(gl.Bad, match="already has its prediction layer"):
        gl.add(out, tail, tmp_path / "twice.gguf", manifest(X + Y))
    (tmp_path / "not.gguf").write_bytes(b"NOPE" + b"\0" * 40)
    with pytest.raises(gl.Bad, match="is not a GGUF file"):
        gl.header(tmp_path / "not.gguf")
    assert gl.main(["add", str(tmp_path / "not.gguf"), str(tail), str(out)]) == 1 and gl.main(["nonsense"]) == 2


def test_the_pinned_layer_of_the_base_model_adds_up():
    m = gl.QWEN35_4B
    assert sum(size for _n, _d, _k, size in m["tensors"]) == m["bytes"] == 81195008 and len(m["tensors"]) == 15
    assert all(size % 32 == 0 and name.startswith("blk.32.") for name, _d, _k, size in m["tensors"]) and len(m["sha256"]) == 64
    assert m["url"].startswith("https://huggingface.co/unsloth/Qwen3.5-4B-MTP-GGUF/resolve/") and "/main/" not in m["url"]
