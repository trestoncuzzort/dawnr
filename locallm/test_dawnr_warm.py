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


def test_a_bad_rounds_or_steps_setting_is_said_and_refused_and_nothing_is_asked_of_the_server(tmp_path, monkeypatch, capsys):
    # dawnr_warm builds the assistant's own configuration, so it reads DAWNR_MAX_ROUNDS and DAWNR_MAX_STEPS; a cold
    # start is slower, not wrong, but a setting dawnr will not guess is not a cold start
    import pytest

    import dawnr_cli as cli
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.setenv("DAWNR_MAX_STEPS", "0")
    monkeypatch.setattr(cli, "build_agent", lambda *a, **kw: pytest.fail("a harness was built with DAWNR_MAX_STEPS=0"))
    monkeypatch.setattr(warm, "warm", lambda *a, **kw: pytest.fail("the server was asked with DAWNR_MAX_STEPS=0"))
    assert warm.main(["--host", "nowhere:1", "--cwd", str(tmp_path), "Read it."]) == 2
    assert capsys.readouterr().err == ("warm: DAWNR_MAX_STEPS='0' is not a whole number above 0; set it to one, or unset "
                                       "it for the default of 40\n")
