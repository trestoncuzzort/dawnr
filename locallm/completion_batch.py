"""Completion-only batches for the owned core; one example per sequence.

The inference prompt must be exactly the prompt passed to encode_example.
Prompt and completion are tokenized separately so their boundary cannot merge
and serving sees exactly the training prompt IDs. No implicit template is added.
"""
import torch

IGNORE_INDEX = -1  # model.GPT.forward convention


def encode_example(tokenizer, prompt, completion, *, block_size):
    prefix = list(tokenizer.encode(prompt))
    answer = list(tokenizer.encode(completion))
    if not prefix or not answer:
        raise ValueError("nonempty tokenized prompt and completion required")
    if tokenizer.decode(prefix) != prompt or tokenizer.decode(answer) != completion:
        raise ValueError("tokenizer does not round-trip example")
    sequence = prefix + answer
    if len(sequence) - 1 > block_size:
        raise ValueError("example exceeds context; truncation is not permitted")
    inputs = sequence[:-1]
    targets = sequence[1:]
    targets[:len(prefix) - 1] = [IGNORE_INDEX] * (len(prefix) - 1)
    return {"inputs": inputs, "targets": targets,
            "prompt_tokens": len(prefix), "completion_tokens": len(answer)}


def encode_segments(tokenizer, prompt, parts, *, block_size, supervise_execution):
    """Parts are (text, role): 'execution' or 'answer'.

    Tokenize the same parts regardless of treatment. Unsupervised execution
    remains visible context; only its loss mask changes. Part boundaries are
    explicit encoding boundaries, so dataset generation must keep them fixed.
    """
    prefix = list(tokenizer.encode(prompt))
    if not prefix or tokenizer.decode(prefix) != prompt:
        raise ValueError("prompt must round-trip and have tokens")
    sequence = list(prefix)
    labels = [IGNORE_INDEX] * len(prefix)
    has_answer = False
    for text, role in parts:
        if role not in ("execution", "answer"):
            raise ValueError("unknown supervision role")
        ids = list(tokenizer.encode(text))
        if not ids or tokenizer.decode(ids) != text:
            raise ValueError("each part must round-trip and have tokens")
        sequence.extend(ids)
        supervised = role == "answer" or supervise_execution
        labels.extend(ids if supervised else [IGNORE_INDEX] * len(ids))
        has_answer |= role == "answer"
    if not has_answer:
        raise ValueError("example needs a supervised answer")
    if len(sequence) - 1 > block_size:
        raise ValueError("example exceeds context; truncation is not permitted")
    return {"inputs": sequence[:-1], "targets": labels[1:],
            "prompt_tokens": len(prefix), "completion_tokens": len(sequence) - len(prefix)}


def collate(examples, *, pad_id=0, device="cpu"):
    if not examples:
        raise ValueError("empty batch")
    length = max(len(e["inputs"]) for e in examples)
    inputs = torch.full((len(examples), length), pad_id, dtype=torch.long, device=device)
    targets = torch.full_like(inputs, IGNORE_INDEX)
    segments = torch.full_like(inputs, -1)
    for i, example in enumerate(examples):
        n = len(example["inputs"])
        if n == 0 or n != len(example["targets"]):
            raise ValueError("invalid example length")
        if not any(t != IGNORE_INDEX for t in example["targets"]):
            raise ValueError("example has no supervised completion tokens")
        inputs[i, :n] = torch.tensor(example["inputs"], device=device)
        targets[i, :n] = torch.tensor(example["targets"], device=device)
        segments[i, :n] = i
    return inputs, targets, segments
