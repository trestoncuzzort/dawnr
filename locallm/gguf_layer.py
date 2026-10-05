#!/usr/bin/env python3
"""gguf_layer.py: give a model file the layer its publisher left out, without touching one of its weights
(2026-10-05).

    python3 locallm/gguf_layer.py add BASE.gguf TAIL.bin OUT.gguf       # the installer's step
    python3 locallm/gguf_layer.py tail FULL.gguf TAIL.bin               # how TAIL.bin was cut (the last bytes of FULL)
    python3 locallm/gguf_layer.py show FILE.gguf

Qwen3.5-4B was trained with one multi-token-prediction layer: a small extra block that guesses the next few tokens
from the state the model is already in. llama.cpp can draft with it (`--spec-type draft-mtp`), the model itself then
checks the draft in one pass, and what is written is the model's own, sooner. The 4-bit file dawnr installs
(unsloth/Qwen3.5-4B-GGUF) was converted without that layer; the same publisher's other conversion
(unsloth/Qwen3.5-4B-MTP-GGUF) keeps it, but quantises 248 of the other 426 tensors differently, so swapping files
would swap the base model every measurement here was made on.

The layer is 15 tensors, 81 MB, and they are the last bytes of that other file. `add` writes a new file that is the
installed one, every tensor byte for byte, with those 15 appended, the block count raised by one and the key that
says a prediction layer is there. Nothing is requantised and nothing else is read from the other file.

Measured on a 12-core desktop CPU, the assistant's own tasks (2026-10-05): 16.1 tokens a second as installed, 27.3
drafting with this layer on the publisher's own file.

The format is GGUF's (github.com/ggml-org/ggml, docs/gguf.md, fetched; research receipt 5a76eea8c674): a header, the
metadata as key-value pairs, one record per tensor with its offset into the data, padding to the alignment, the
data. Standard library only: the installer runs this with whatever Python is on the machine.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

MAGIC = b"GGUF"
SCALAR = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}      # value type -> bytes
STRING, ARRAY, UINT32 = 8, 9, 4
CHUNK = 1 << 24

# The prediction layer of Qwen3.5-4B as unsloth/Qwen3.5-4B-MTP-GGUF publishes it at 4 bits (Apache-2.0), pinned by
# revision: where its bytes are in that file, their checksum, and each tensor's record. `python3 gguf_layer.py tail`
# on a full download reproduces the bytes and prints these lines.
QWEN35_4B = {
    "url": "https://huggingface.co/unsloth/Qwen3.5-4B-MTP-GGUF/resolve/86835bf9949e4d14d6860f7910b1340ad4f271a9/Qwen3.5-4B-Q4_K_M.gguf",
    "first": 2753780032, "bytes": 81195008,
    "sha256": "e2fe19553cd1620dad236f794b11cbeb251b2c41dd2e2bfd34ec394cc2f03bb7",
    "architecture": "qwen35", "blocks": 33, "layers": 1,
    "tensors": [                                               # name, dimensions, ggml type, bytes
        ("blk.32.attn_k.weight", [2560, 1024], 12, 1474560),
        ("blk.32.attn_k_norm.weight", [256], 0, 1024),
        ("blk.32.attn_norm.weight", [2560], 0, 10240),
        ("blk.32.attn_output.weight", [4096, 2560], 12, 5898240),
        ("blk.32.attn_q.weight", [2560, 8192], 12, 11796480),
        ("blk.32.attn_q_norm.weight", [256], 0, 1024),
        ("blk.32.attn_v.weight", [2560, 1024], 14, 2150400),
        ("blk.32.ffn_down.weight", [9216, 2560], 14, 19353600),
        ("blk.32.ffn_gate.weight", [2560, 9216], 12, 13271040),
        ("blk.32.ffn_up.weight", [2560, 9216], 12, 13271040),
        ("blk.32.nextn.eh_proj.weight", [5120, 2560], 8, 13926400),
        ("blk.32.nextn.enorm.weight", [2560], 0, 10240),
        ("blk.32.nextn.hnorm.weight", [2560], 0, 10240),
        ("blk.32.nextn.shared_head_norm.weight", [2560], 0, 10240),
        ("blk.32.post_attention_norm.weight", [2560], 0, 10240),
    ],
}


class Bad(Exception):
    """The file is not what this can extend; the message says why."""


def _string(f) -> bytes:
    (n,) = struct.unpack("<Q", f.read(8))
    if n > 1 << 30:
        raise Bad("a string in the header is implausibly long")
    return f.read(n)


def _skip(f, kind: int) -> None:
    if kind in SCALAR:
        f.seek(SCALAR[kind], 1)
    elif kind == STRING:
        _string(f)
    elif kind == ARRAY:
        inner, count = struct.unpack("<IQ", f.read(12))
        if inner in SCALAR:
            f.seek(SCALAR[inner] * count, 1)
        else:
            for _ in range(count):
                _skip(f, inner)
    else:
        raise Bad(f"metadata value type {kind} is not one GGUF defines")


def header(path) -> dict:
    """Where a GGUF file's parts are: {"version", "tensors": [(name, dims, type, offset)], "kv": (start, end),
    "infos": (start, end), "data", "alignment", "keys": {name: (value type, position of the value)}}."""
    with open(path, "rb") as f:
        if f.read(4) != MAGIC:
            raise Bad(f"{Path(path).name} is not a GGUF file")
        version, n_tensors, n_kv = struct.unpack("<IQQ", f.read(20))
        if version not in (2, 3):
            raise Bad(f"GGUF version {version} is not one this reads")
        kv_start, keys, alignment = f.tell(), {}, 32
        for _ in range(n_kv):
            key = _string(f).decode("utf-8")
            (kind,) = struct.unpack("<I", f.read(4))
            keys[key] = (kind, f.tell())
            if key == "general.alignment" and kind == UINT32:
                (alignment,) = struct.unpack("<I", f.read(4))
            else:
                _skip(f, kind)
        kv_end, tensors = f.tell(), []
        for _ in range(n_tensors):
            name = _string(f).decode("utf-8")
            (n_dims,) = struct.unpack("<I", f.read(4))
            dims = list(struct.unpack(f"<{n_dims}Q", f.read(8 * n_dims)))
            kind, offset = struct.unpack("<IQ", f.read(12))
            tensors.append((name, dims, kind, offset))
        infos_end = f.tell()
        data = (infos_end + alignment - 1) // alignment * alignment
        return {"version": version, "tensors": tensors, "n_kv": n_kv, "kv": (kv_start, kv_end), "infos": (kv_end, infos_end),
                "data": data, "alignment": alignment, "keys": keys, "size": Path(path).stat().st_size}


def _info(name: str, dims: list, kind: int, offset: int) -> bytes:
    raw = name.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw + struct.pack(f"<I{len(dims)}QIQ", len(dims), *dims, kind, offset)


def _sha256(path, first: int = 0, count: int | None = None) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        f.seek(first)
        left = count
        while left is None or left > 0:
            block = f.read(CHUNK if left is None else min(CHUNK, left))
            if not block:
                break
            digest.update(block)
            left = None if left is None else left - len(block)
    return digest.hexdigest()


def tail(full, out, base_tensors: set | None = None) -> dict:
    """Cut the tensors a full file has past `base_tensors` (default: its last block's) as its last bytes, and say
    what a manifest needs: where they start, how many bytes, their checksum, their records."""
    h = header(full)
    ordered = sorted(h["tensors"], key=lambda t: t[3])
    if base_tensors is None:
        last = max(int(t[0].split(".")[1]) for t in ordered if t[0].startswith("blk."))
        extra = [t for t in ordered if t[0].startswith(f"blk.{last}.")]
    else:
        extra = [t for t in ordered if t[0] not in base_tensors]
    if not extra or ordered[-len(extra):] != extra:
        raise Bad("the tensors to cut are not the last bytes of the file")
    first = h["data"] + extra[0][3]
    with open(full, "rb") as f, open(out, "wb") as o:
        f.seek(first)
        while block := f.read(CHUNK):
            o.write(block)
    count = h["size"] - first
    sizes = [b[3] - a[3] for a, b in zip(extra, extra[1:])] + [h["size"] - h["data"] - extra[-1][3]]
    return {"first": first, "bytes": count, "sha256": _sha256(out),
            "tensors": [(name, dims, kind, size) for (name, dims, kind, _o), size in zip(extra, sizes)]}


def add(base, tail_path, out, manifest: dict = QWEN35_4B) -> dict:
    """Write `out`: `base` with the manifest's tensors appended from `tail_path`. Every tensor of `base` is copied
    as it is. Refuses a base of another architecture, one that already has the layer, and a tail that is not the
    manifest's bytes."""
    h = header(base)
    arch = manifest["architecture"]
    blocks_key, layers_key = f"{arch}.block_count", f"{arch}.nextn_predict_layers"
    if blocks_key not in h["keys"] or h["keys"][blocks_key][0] != UINT32:
        raise Bad(f"{Path(base).name} is not a {arch} model")
    if layers_key in h["keys"] or any(t[0] == manifest["tensors"][0][0] for t in h["tensors"]):
        raise Bad(f"{Path(base).name} already has its prediction layer")
    if Path(tail_path).stat().st_size != manifest["bytes"] or _sha256(tail_path) != manifest["sha256"]:
        raise Bad(f"{Path(tail_path).name} is not the layer the manifest names (its size or checksum differs)")
    if sum(size for _n, _d, _k, size in manifest["tensors"]) != manifest["bytes"]:
        raise Bad("the manifest's tensors do not add up to its bytes")
    align = h["alignment"]
    if any(size % align for _n, _d, _k, size in manifest["tensors"]):
        raise Bad("a tensor of the layer is not a whole number of alignment blocks")
    with open(base, "rb") as f:
        f.seek(h["keys"][blocks_key][1])
        (blocks,) = struct.unpack("<I", f.read(4))
        if blocks != manifest["blocks"] - manifest["layers"]:
            raise Bad(f"{Path(base).name} has {blocks} blocks, not the {manifest['blocks'] - manifest['layers']} the layer follows")
        f.seek(h["kv"][0])
        kv = bytearray(f.read(h["kv"][1] - h["kv"][0]))
        at = h["keys"][blocks_key][1] - h["kv"][0]
        kv[at:at + 4] = struct.pack("<I", manifest["blocks"])
        raw = layers_key.encode("utf-8")
        kv += struct.pack("<Q", len(raw)) + raw + struct.pack("<II", UINT32, manifest["layers"])
        f.seek(h["infos"][0])
        infos = bytearray(f.read(h["infos"][1] - h["infos"][0]))
        old_data = h["size"] - h["data"]
        offset = (old_data + align - 1) // align * align        # the new tensors follow the old data, aligned
        for name, dims, kind, size in manifest["tensors"]:
            infos += _info(name, dims, kind, offset)
            offset += size
        head = MAGIC + struct.pack("<IQQ", h["version"], len(h["tensors"]) + len(manifest["tensors"]), h["n_kv"] + 1) + kv + infos
        with open(out, "wb") as o:
            o.write(head)
            o.write(b"\0" * (-len(head) % align))
            f.seek(h["data"])
            copied = hashlib.sha256()
            while block := f.read(CHUNK):
                o.write(block)
                copied.update(block)
            o.write(b"\0" * (-old_data % align))
            with open(tail_path, "rb") as t:
                while block := t.read(CHUNK):
                    o.write(block)
    after = header(out)
    if after["size"] - after["data"] != (old_data + align - 1) // align * align + manifest["bytes"]:
        raise Bad("the file written is not the size it should be")
    return {"tensors": len(after["tensors"]), "added": len(manifest["tensors"]), "bytes": after["size"],
            "base data sha256": copied.hexdigest()}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) == 4 and argv[0] == "add":
            got = add(argv[1], argv[2], argv[3])
            print(f"{Path(argv[3]).name}: {got['tensors']} tensors ({got['added']} added), {got['bytes']:,} bytes; "
                  "every tensor of the base copied as it was")
        elif len(argv) == 3 and argv[0] == "tail":
            got = tail(argv[1], argv[2])
            print(json_lines(got))
        elif len(argv) == 2 and argv[0] == "show":
            h = header(argv[1])
            print(f"{Path(argv[1]).name}: GGUF v{h['version']}, {len(h['tensors'])} tensors, {h['n_kv']} keys, data at {h['data']}, "
                  f"{h['size']:,} bytes")
        else:
            print(__doc__.split("\n\n")[1], file=sys.stderr)
            return 2
    except (Bad, OSError, struct.error) as e:
        print(f"gguf_layer: {e}", file=sys.stderr)
        return 1
    return 0


def json_lines(got: dict) -> str:
    lines = [f'    "first": {got["first"]}, "bytes": {got["bytes"]},', f'    "sha256": "{got["sha256"]}",', '    "tensors": [']
    lines += [f"        ({name!r}, {dims}, {kind}, {size})," for name, dims, kind, size in got["tensors"]]
    return "\n".join(lines + ["    ],"])


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
