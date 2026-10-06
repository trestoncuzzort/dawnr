"""dawnr_warm: the prefix is what two renderings share, cut at a token boundary; warming sends it alone and asks for nothing."""
import dawnr_warm as warm


def test_prefix_cut_at_the_last_special_token():
    a = "<|im_start|>system\nS<|im_end|>\n<|im_start|>user\na<|im_end|>\n"
    b = "<|im_start|>system\nS<|im_end|>\n<|im_start|>user\nb<|im_end|>\n"
    assert warm.prefix_of(a, b) == "<|im_start|>system\nS<|im_end|>\n"


def test_prefix_without_special_tokens_cuts_at_a_line():
    assert warm.prefix_of("System: S\nUser: a\n", "System: S\nUser: b\n") == "System: S\n"


def test_warm_posts_the_prefix_alone():
    sent = []

    def post(url, body, timeout):
        sent.append((url, body))
        if url.endswith("/apply-template"):
            return {"prompt": "<|im_start|>system\n" + body["messages"][0]["content"] + "<|im_end|>\n<|im_start|>user\n"
                              + body["messages"][1]["content"] + "<|im_end|>\n"}
        return {"timings": {"prompt_n": 7, "cache_n": 0}}
    got = warm.warm("h", "S", [{"type": "function", "function": {"name": "t"}}], post=post)
    assert got["prompt_n"] == 7 and got["cache_n"] == 0
    url, body = sent[-1]
    assert url == "http://h/completion" and body["n_predict"] == 0 and body["cache_prompt"] is True
    assert body["prompt"] == "<|im_start|>system\nS<|im_end|>\n"
    assert all(b.get("tools") for u, b in sent[:2])            # the tools are part of the rendered prefix
