"""
Unit tests for v4.8.0 changes outside media: sampling parameters, output
budget, Gemma routing, quota fallback, embeddings, Antigravity agent,
image tool options. No network.
"""

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import app.tools.text.embed  # noqa: E402,F401
import app.tools.web.agent_task  # noqa: E402,F401
import app.tools.media.generate_image  # noqa: E402,F401
import app.tools.text.ask_gemini  # noqa: E402,F401
from app.services import interactions as ix  # noqa: E402
from app.services import gemini as gemini_mod  # noqa: E402
from app.services.gemini import legacy_sampling  # noqa: E402
from app.core.config import config  # noqa: E402

EMBED = sys.modules["app.tools.text.embed"]
AGENT = sys.modules["app.tools.web.agent_task"]
IMAGE = sys.modules["app.tools.media.generate_image"]
ASK = sys.modules["app.tools.text.ask_gemini"]

try:
    from google.genai._gaos.google_genai import interactions as SDK_I
except Exception:  # pragma: no cover
    SDK_I = None


class TestSampling:
    @pytest.mark.parametrize("model_id", ["gemini-4-argon", "gemini-3.8-flash", "gemini-3.1-pro-preview"])
    def test_gemini_3_plus_gets_no_temperature(self, model_id):
        assert legacy_sampling(model_id, 0.7) == {}

    @pytest.mark.parametrize("model_id", ["gemini-2.5-flash", "gemma-4-31b-it"])
    def test_legacy_models_keep_temperature(self, model_id):
        assert legacy_sampling(model_id, 0.7) == {"temperature": 0.7}

    def test_default_output_budget_is_64k(self):
        assert config.max_output_tokens == 65536

    def test_ask_gemini_sends_no_temperature_and_a_64k_budget(self, monkeypatch):
        seen = {}

        def fake_generate(model_id, contents, config, operation):
            seen["config"] = config
            return SimpleNamespace(text="ok", candidates=[])

        monkeypatch.setattr(ASK, "generate_with_fallback", fake_generate)
        monkeypatch.setattr(ASK, "MODELS", {"pro": "gemini-4-argon", "flash": "gemini-3.8-flash"})
        ASK.ask_gemini("hello", model="pro", temperature=0.9)
        assert seen["config"].temperature is None
        assert seen["config"].max_output_tokens == 65536


class TestQuotaFallback:
    def _client(self, fail_first_with):
        calls = []

        class Models:
            def generate_content(self, model, contents, config=None):
                calls.append(model)
                if len(calls) == 1:
                    raise Exception(fail_first_with)
                return SimpleNamespace(text="from fallback")

        return SimpleNamespace(models=Models()), calls

    def test_argon_falls_back_to_flash_on_rate_limit(self, monkeypatch):
        client, calls = self._client("429 RESOURCE_EXHAUSTED rate limit")
        monkeypatch.setattr(gemini_mod, "client", client)
        monkeypatch.setattr(gemini_mod, "_available", True)
        monkeypatch.setattr(gemini_mod, "MODELS", {"flash": "gemini-3.8-flash"})
        assert gemini_mod.generate_with_fallback("gemini-4-argon", "x").text == "from fallback"
        assert calls == ["gemini-4-argon", "gemini-3.8-flash"]

    def test_spending_cap_is_not_retried_on_flash(self, monkeypatch):
        client, calls = self._client("429 RESOURCE_EXHAUSTED exceeded its monthly spending cap")
        monkeypatch.setattr(gemini_mod, "client", client)
        monkeypatch.setattr(gemini_mod, "_available", True)
        monkeypatch.setattr(gemini_mod, "MODELS", {"flash": "gemini-3.8-flash"})
        with pytest.raises(Exception, match="spending cap"):
            gemini_mod.generate_with_fallback("gemini-4-argon", "x")
        assert calls == ["gemini-4-argon"]


class TestGemmaRouting:
    def test_gemma_is_native_with_openrouter_mirror(self):
        from app.tools.text.ask_model import _is_gemini_model, _to_openrouter_google_id
        assert _is_gemini_model("gemma-4-31b-it")
        assert _to_openrouter_google_id("gemma-4-31b-it") == "google/gemma-4-31b-it"
        assert _to_openrouter_google_id("lyria-3.5") is None


class TestEmbed:
    def test_task_prefixes(self):
        assert EMBED.prepare_text("cats", "search_query") == "task: search result | query: cats"
        assert EMBED.prepare_text("doc", "search_document", "Title") == "title: Title | text: doc"
        assert EMBED.prepare_text("doc", "search_document") == "title: none | text: doc"
        assert EMBED.prepare_text("a", "similarity") == "task: sentence similarity | query: a"
        assert EMBED.prepare_text("a", "none") == "a"

    def test_separate_vs_aggregated_contents(self):
        sep = EMBED.build_embed_call("gemini-embedding-2", ["a", "b"], [], "none", None, False, 768)
        assert len(sep["contents"]) == 2 and all(hasattr(c, "parts") for c in sep["contents"])
        assert sep["config"].output_dimensionality == 768
        agg = EMBED.build_embed_call("gemini-embedding-2", ["a", "b"], [], "none", None, True, None)
        assert len(agg["contents"]) == 2 and all(hasattr(p, "text") for p in agg["contents"]) and agg["config"] is None

    def test_legacy_model_uses_task_type_and_rejects_files(self):
        call = EMBED.build_embed_call("gemini-embedding-001", ["q"], [], "search_query", None, False, None)
        assert call["config"].task_type == "RETRIEVAL_QUERY" and call["contents"][0].parts[0].text == "q"
        with pytest.raises(ValueError, match="text-only"):
            EMBED.build_embed_call("gemini-embedding-001", [], [object()], "none", None, False, None)

    @pytest.mark.parametrize("kwargs, match", [(dict(task="rank"), "task"), (dict(dims=1000), "output_dimensionality"),
                                               (dict(texts=[]), "provide")])
    def test_validation(self, kwargs, match):
        args = dict(model_id="gemini-embedding-2", texts=["a"], file_parts=[], task="none", title=None, aggregate=False, dims=None)
        args.update(kwargs)
        with pytest.raises(ValueError, match=match):
            EMBED.build_embed_call(**args)

    def test_tool_inline_and_file_output(self, monkeypatch, tmp_path):
        monkeypatch.setattr(EMBED, "is_available", lambda: True)
        monkeypatch.setattr(EMBED.model_registry, "resolve", lambda cat: "gemini-embedding-2")
        vectors = [SimpleNamespace(values=[0.1, 0.2]), SimpleNamespace(values=[0.3, 0.4])]
        monkeypatch.setattr(EMBED, "client", SimpleNamespace(models=SimpleNamespace(embed_content=lambda **kw: SimpleNamespace(embeddings=vectors))))
        data = json.loads(EMBED.embed(texts=["a", "b"]))
        assert data["dimensions"] == 2 and [i["values"] for i in data["items"]] == [[0.1, 0.2], [0.3, 0.4]]
        out = EMBED.embed(texts=["a", "b"], output_path=str(tmp_path / "v.json"))
        assert "Saved to" in out and json.loads((tmp_path / "v.json").read_text())["model"] == "gemini-embedding-2"


class TestAgent:
    def test_request_shape_and_sdk_validation(self):
        req = AGENT.build_agent_request("antigravity-preview-09-2026", "build a chart", [], ["google_search"], "flash", None)
        assert req == {"agent": "antigravity-preview-09-2026", "input": "build a chart", "environment": "remote",
                       "background": True, "tools": [{"type": "google_search"}]}
        if SDK_I is not None:
            SDK_I.CreateAgentInteraction.model_validate(req)

    def test_pro_brain_and_continuation(self, monkeypatch):
        monkeypatch.setattr(AGENT, "MODELS", {"pro": "gemini-4-argon"})
        req = AGENT.build_agent_request("a", "next step", [], None, "pro", "v1_prev")
        assert req["agent_config"] == {"type": "antigravity", "model": "gemini-4-argon"}
        assert req["previous_interaction_id"] == "v1_prev"

    def test_unknown_tool_rejected(self):
        with pytest.raises(ValueError, match="unknown tools"):
            AGENT.build_agent_request("a", "x", [], ["rm_rf"], "flash", None)

    def test_retrieve_mode_and_timeout(self, monkeypatch):
        monkeypatch.setattr(AGENT, "is_available", lambda: True)
        monkeypatch.setattr(ix, "cleanup", lambda n: None)
        done = {"id": "v1_a", "status": "completed",
                "steps": [{"type": "user_input", "content": []}, {"type": "model_output", "content": [{"type": "text", "text": "Report ready"}]}]}
        monkeypatch.setattr(ix, "wait", lambda iid, t, p=10: done)
        assert "Report ready" in AGENT.agent_task(task="", continuation_id="v1_a")
        assert AGENT.agent_task(task="").startswith("Error: nothing to do")

        def boom(req, t, p=10):
            raise ix.InteractionTimeout("v1_long", 1800)
        monkeypatch.setattr(ix, "run", boom)
        monkeypatch.setattr(AGENT.model_registry, "resolve", lambda c: "antigravity-preview-09-2026")
        assert "continuation_id='v1_long' and an EMPTY task" in AGENT.agent_task(task="long job")

    def test_returned_documents_are_saved(self, tmp_path):
        doc = {"type": "document", "data": base64.b64encode(b"%PDF").decode(), "mime_type": "application/pdf", "name": "report.pdf"}
        interaction = {"id": "v1", "steps": [{"type": "user_input", "content": []}, {"type": "model_output", "content": [doc]}]}
        saved = AGENT._save_outputs(interaction, str(tmp_path))
        assert len(saved) == 1 and Path(saved[0]).read_bytes() == b"%PDF"


class TestImageOptions:
    def test_size_resolution_rules(self):
        assert IMAGE.resolve_image_size("pro", "auto") == "2K"
        assert IMAGE.resolve_image_size("flash", "auto") is None
        assert IMAGE.resolve_image_size("lite", "4K") == "4K"

    def test_config_has_search_thinking_and_panoramic_ratio(self, monkeypatch):
        seen = {}

        class Models:
            def generate_content(self, model, contents, config):
                seen.update(model=model, config=config)
                return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]))])

        monkeypatch.setattr(IMAGE, "client", SimpleNamespace(models=Models()))
        monkeypatch.setattr(IMAGE, "IMAGE_MODELS", {"pro": "p", "flash": "gemini-nano-banana-2.1", "lite": "l"})
        IMAGE.generate_image("panorama of the Alps", model="flash", aspect_ratio="8:1", image_size="4K",
                             google_search=True, thinking_level="high")
        cfg = seen["config"]
        assert seen["model"] == "gemini-nano-banana-2.1"
        assert cfg.image_config.aspect_ratio == "8:1" and cfg.image_config.image_size == "4K"
        assert cfg.tools and cfg.tools[0].google_search is not None
        assert str(cfg.thinking_config.thinking_level).lower().endswith("high")

    def test_more_than_14_references_rejected(self):
        assert "at most 14" in IMAGE.generate_image("x", input_images=["a.png"] * 15)


class TestRuntimeDefaults:
    def test_conversation_db_follows_gemini_log_dir(self):
        from app.services import persistence
        from pathlib import Path
        assert persistence.DB_DIR == Path(config.log_dir).expanduser()
        assert persistence.DB_PATH.name == "conversations.db"

    def test_startup_log_counts_registered_tools(self):
        import inspect
        import app.server as server
        src = inspect.getsource(server.main)
        assert "len(mcp._tool_manager._tools)" in src and "Tools available: 20" not in src
