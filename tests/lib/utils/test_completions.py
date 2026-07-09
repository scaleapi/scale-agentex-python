from __future__ import annotations

from agentex.lib.utils.completions import concat_completion_chunks
from agentex.lib.types.llm_messages import Delta, Usage, Choice, Completion


def _delta_chunk(content: str, role: str | None = None) -> Completion:
    return Completion(choices=[Choice(index=0, delta=Delta(content=content, role=role))])


def _usage_only_chunk(prompt: int, completion: int) -> Completion:
    # stream_options.include_usage: litellm/OpenAI send a final chunk that has
    # usage but an empty choices list
    return Completion(
        choices=[],
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion),
    )


class TestConcatCompletionChunks:
    def test_concatenates_delta_content(self):
        result = concat_completion_chunks([_delta_chunk("Hel", role="assistant"), _delta_chunk("lo!")])

        assert result.choices[0].message.content == "Hello!"

    def test_trailing_usage_only_chunk_keeps_choices_and_usage(self):
        result = concat_completion_chunks(
            [_delta_chunk("Hel", role="assistant"), _delta_chunk("lo!"), _usage_only_chunk(10, 5)]
        )

        assert result.choices[0].message.content == "Hello!"
        assert result.usage is not None
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.total_tokens == 15

    def test_usage_summed_across_chunks(self):
        chunk_a = _delta_chunk("a", role="assistant")
        chunk_a.usage = Usage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        chunk_b = _delta_chunk("b")
        chunk_b.usage = Usage(prompt_tokens=4, completion_tokens=5, total_tokens=9)

        result = concat_completion_chunks([chunk_a, chunk_b])

        assert result.usage.prompt_tokens == 5
        assert result.usage.completion_tokens == 7
        assert result.usage.total_tokens == 12

    def test_no_usage_chunks_leave_usage_none(self):
        result = concat_completion_chunks([_delta_chunk("x", role="assistant")])

        assert result.usage is None
