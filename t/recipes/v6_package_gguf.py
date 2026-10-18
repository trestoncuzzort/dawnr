"""Split a checked Q8 export and prove its tensor and metadata contents unchanged.

Prior artifacts: release/MODEL-CARD-student-v5.md and its GGUF shards.
Sources: pinned llama.cpp tools/gguf-split and gguf-py/gguf/gguf_reader.py;
https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

from v6_export import CONVERTER, digest

BOOKKEEPING = {'GGUF.tensor_count', 'GGUF.kv_count', 'split.no', 'split.count', 'split.tensors.count'}


def metadata(reader):
    result = {}
    for key, field in reader.fields.items():
        if key in BOOKKEEPING:
            continue
        h = hashlib.sha256(json.dumps([int(t) for t in field.types]).encode())
        for part in field.parts:
            raw = memoryview(part).cast('B')
            h.update(struct.pack('<Q', len(raw)))
            h.update(raw)
        result[key] = h.hexdigest()
    return result


def tensors(reader):
    result = {}
    for tensor in reader.tensors:
        if tensor.name in result:
            raise ValueError('duplicate tensor: '+tensor.name)
        raw = memoryview(tensor.data).cast('B')
        result[tensor.name] = {'type': int(tensor.tensor_type), 'shape': list(map(int, tensor.shape)),
                               'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def verify_shards(original, shards, reader_class):
    reader = reader_class(original)
    expected_metadata, expected_tensors = metadata(reader), tensors(reader)
    del reader
    gc.collect()
    actual = {}
    for index, path in enumerate(shards):
        reader = reader_class(path)
        if (reader.fields['split.no'].contents() != index
                or reader.fields['split.count'].contents() != len(shards)
                or reader.fields['split.tensors.count'].contents() != len(expected_tensors)):
            raise ValueError('split bookkeeping differs: '+str(path))
        # The pinned splitter writes model metadata in the first shard only
        # (gguf-split.cpp, new_ctx). Later shards carry the file version and
        # split bookkeeping. No other metadata may be added or changed there.
        expected_here = expected_metadata if index == 0 else {'GGUF.version': expected_metadata['GGUF.version']}
        if metadata(reader) != expected_here:
            raise ValueError('model metadata changed: '+str(path))
        values = tensors(reader)
        if actual.keys() & values.keys():
            raise ValueError('duplicate tensor across shards')
        actual.update(values)
        del reader
        gc.collect()
    if actual != expected_tensors:
        raise ValueError('tensor names, dimensions, types, or bytes changed')
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return {'tensors': len(expected_tensors),
            'tensor_contents_sha256': hashlib.sha256(canonical(expected_tensors)).hexdigest(),
            'model_metadata_sha256': hashlib.sha256(canonical(expected_metadata)).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', required=True, type=Path)
    parser.add_argument('--llama-dir', required=True, type=Path)
    parser.add_argument('--stem', required=True)
    parser.add_argument('--verify-existing', action='store_true',
                        help='verify preserved shards after an interrupted or refused packaging check')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.stem):
        parser.error('the shard stem must be a plain filename')
    exported = json.loads((args.export/'export.json').read_text())
    original = args.export/'model-Q8_0.gguf'
    if exported['converter_commit'] != CONVERTER or exported['quantization'] != 'Q8_0':
        parser.error('export differs from the registered converter and format')
    if digest(original) != exported['output']['sha256']:
        parser.error('export checksum changed')
    revision = subprocess.check_output(['git','-C',str(args.llama_dir),'rev-parse','HEAD'],text=True).strip()
    if revision != CONVERTER:
        parser.error('splitter checkout differs from the registered revision')
    if subprocess.check_output(['git','-C',str(args.llama_dir),'status','--porcelain','--untracked-files=no'],text=True).strip():
        parser.error('splitter tracked source files are modified')
    out = args.export/'release'
    splitter = args.llama_dir/'build/bin/llama-gguf-split'
    if args.verify_existing:
        if not out.is_dir() or (out/'package.json').exists():
            parser.error('verify-existing needs preserved shards without a completed package receipt')
    else:
        if out.exists():
            parser.error('release output already exists; preserve it and inspect before retrying')
        out.mkdir()
        subprocess.run([str(splitter),'--split','--split-max-size','1900M',str(original),str(out/args.stem)],check=True)
    shards = sorted(out.glob(args.stem+'-*-of-*.gguf'))
    if not shards or any(p.name != f'{args.stem}-{i:05d}-of-{len(shards):05d}.gguf'
                         for i,p in enumerate(shards,1)):
        raise RuntimeError('missing or unexpected shard filenames')
    if any(not 0 < p.stat().st_size < 2*1024**3 for p in shards):
        raise RuntimeError('a shard exceeds the release asset limit or is empty')
    sys.path.insert(0,str(args.llama_dir/'gguf-py'))
    from gguf import GGUFReader
    equivalence = verify_shards(original, shards, GGUFReader)
    files = {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in shards}
    manifest = out/'dawnr-student.sha256'
    manifest.write_text(''.join(value['sha256']+'  '+name+'\n' for name,value in files.items()))
    record = {'schema': 1, 'source_gguf_sha256': exported['output']['sha256'],
              'adapter_step': exported['adapter'].get('step'),
              'adapter': exported['adapter'], 'converter_commit': CONVERTER,
              'packager_sha256': digest(Path(__file__)),
              'splitter_sha256': digest(splitter), 'manifest_sha256': digest(manifest),
              'first_shard': shards[0].name, 'files': files, 'equivalence': equivalence}
    (out/'package.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
