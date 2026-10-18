"""Packaging refuses changed model metadata, missing tensors, and changed bytes."""
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import v6_package_gguf as package


def field(value):
    return SimpleNamespace(types=[1], parts=[str(value).encode()], contents=lambda: value)


def tensor(name, data=b'weights', shape=(7,)):
    return SimpleNamespace(name=name, tensor_type=8, shape=shape, data=data)


def fixture():
    common={'general.name':field('same model'), 'GGUF.version':field(3)}
    original=SimpleNamespace(fields={**common,'GGUF.tensor_count':field(2)},tensors=[tensor('a'),tensor('b')])
    shards=[SimpleNamespace(fields={**(common if i == 0 else {'GGUF.version':field(3)}),'split.no':field(i),'split.count':field(2),
                                    'split.tensors.count':field(2),'GGUF.tensor_count':field(1)},
                            tensors=[tensor(name)]) for i,name in enumerate(('a','b'))]
    return [original,*shards]


def test_split_counts_may_differ_but_all_model_contents_remain_identical():
    readers=fixture()
    assert package.verify_shards(0,[1,2],readers.__getitem__)['tensors']==2


@pytest.mark.parametrize('change',['metadata','secondary-metadata','bytes','shape','missing','duplicate','order'])
def test_a_package_with_any_content_or_order_change_is_refused(change):
    readers=fixture()
    if change=='metadata': readers[1].fields['general.name']=field('another model')
    elif change=='secondary-metadata': readers[2].fields['general.name']=field('unexpected override')
    elif change=='bytes': readers[1].tensors[0]=tensor('a',b'changed')
    elif change=='shape': readers[1].tensors[0]=tensor('a',shape=(1,7))
    elif change=='missing': readers[1].tensors=[]
    elif change=='duplicate': readers[2].tensors=[tensor('a')]
    else: readers[1].fields['split.no']=field(1)
    with pytest.raises(ValueError):
        package.verify_shards(0,[1,2],readers.__getitem__)
