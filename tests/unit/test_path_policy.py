"""
Path policy (v4.8.2): sandbox + credentials deny-list on every tool input and output.

Covers sensitive_reason, validate_path with the sandbox disabled, safe_input_path,
safe_output_path, default_output_path, the default sandbox root, @file expansion,
analyze_codebase file collection and the media download host checks.
"""

import importlib
import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import config
from app.core.security import (
    default_output_path,
    safe_input_path,
    safe_output_path,
    sensitive_reason,
    validate_path,
)

# app.core re-exports the Config instance as `config`: fetch the module itself
config_module = importlib.import_module("app.core.config")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / "sandbox"
    root.mkdir()
    monkeypatch.setattr(config, "sandbox_root", os.path.realpath(str(root)))
    monkeypatch.setattr(config, "sandbox_enabled", True)
    return root


class TestSensitiveReason:
    @pytest.mark.parametrize("path", [
        "/home/u/.ssh/config",
        "/home/u/.aws/credentials",
        "/home/u/project/.env",
        "/home/u/project/.env.production",
        "/home/u/.claude.json",
        "/home/u/.netrc",
        "/srv/certs/server.pem",
        "/srv/certs/tls.key",
        "/home/u/id_ed25519",
        "/home/u/Library/Keychains/login.keychain-db",
    ])
    def test_credentials_are_flagged(self, path):
        assert sensitive_reason(path)

    @pytest.mark.parametrize("path", [
        "/home/u/project/app.py",
        "/home/u/project/.env.example",
        "/home/u/project/env.py",
        "/home/u/project/keyboard.md",
        "/home/u/project/Dockerfile",
    ])
    def test_ordinary_files_pass(self, path):
        assert sensitive_reason(path) is None

    def test_home_application_data(self):
        home = os.path.realpath(os.path.expanduser("~"))
        assert sensitive_reason(os.path.join(home, ".claude", "settings.json"))
        assert sensitive_reason(os.path.join(home, ".config", "gh", "hosts.yml"))


class TestValidatePath:
    def test_credentials_refused_even_with_sandbox_disabled(self, sandbox, monkeypatch):
        monkeypatch.setattr(config, "sandbox_enabled", False)
        with pytest.raises(ValueError, match="protected"):
            validate_path(str(sandbox / ".env"))

    def test_relative_paths_resolve_against_the_sandbox_root(self, sandbox):
        assert validate_path("a.txt") == os.path.join(config.sandbox_root, "a.txt")

    def test_traversal_is_refused(self, sandbox):
        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_path("../escape.txt")

    def test_symlink_out_of_the_sandbox_is_refused(self, sandbox, tmp_path):
        outside = tmp_path / "outside.txt"
        outside.write_text("x")
        (sandbox / "link.txt").symlink_to(outside)
        with pytest.raises(ValueError, match="outside allowed directory"):
            validate_path(str(sandbox / "link.txt"))


class TestSafeInputPath:
    def test_ok(self, sandbox):
        f = sandbox / "clip.wav"
        f.write_bytes(b"RIFF")
        assert safe_input_path(str(f), {".wav"}) == os.path.realpath(str(f))

    def test_extension_allowlist(self, sandbox):
        f = sandbox / "notes.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="unsupported file type"):
            safe_input_path(str(f), {".wav", ".mp3"})

    def test_missing_file(self, sandbox):
        with pytest.raises(ValueError, match="file not found"):
            safe_input_path(str(sandbox / "nope.wav"))

    def test_empty(self, sandbox):
        with pytest.raises(ValueError, match="empty"):
            safe_input_path("  ")


class TestSafeOutputPath:
    def test_creates_parent_inside_sandbox(self, sandbox):
        out = safe_output_path(str(sandbox / "sub" / "img.png"), {".png"})
        assert out.endswith("img.png") and (sandbox / "sub").is_dir()

    def test_extension_is_mandatory(self, sandbox):
        with pytest.raises(ValueError, match="output must end with"):
            safe_output_path(str(sandbox / ".zshrc"), {".png"})

    def test_outside_sandbox(self, sandbox):
        with pytest.raises(ValueError, match="outside allowed directory"):
            safe_output_path("/etc/evil.png", {".png"})

    def test_refuses_symlink(self, sandbox):
        target = sandbox / "real.png"
        target.write_bytes(b"x")
        (sandbox / "link.png").symlink_to(target)
        with pytest.raises(ValueError, match="symbolic link"):
            safe_output_path(str(sandbox / "link.png"), {".png"})


class TestDefaultOutputPath:
    def test_private_folder_and_unique_names(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "output_dir", str(tmp_path / "out"))
        first = default_output_path("speech", ".wav")
        second = default_output_path("speech", ".wav")
        assert first != second
        assert first.endswith(".wav") and os.path.basename(first).startswith("speech_")
        mode = stat.S_IMODE(os.stat(tmp_path / "out").st_mode)
        assert mode == 0o700


class TestDefaultSandboxRoot:
    def test_explicit_env_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_SANDBOX_ROOT", str(tmp_path))
        assert config_module._default_sandbox_root() == os.path.realpath(str(tmp_path))

    def test_project_cwd_is_used(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_SANDBOX_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        assert config_module._default_sandbox_root() == os.path.realpath(str(tmp_path))

    def test_home_cwd_falls_back_to_workspace(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_SANDBOX_ROOT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        root = config_module._default_sandbox_root()
        assert root == os.path.realpath(os.path.join(str(tmp_path), "omni-ai-workspace"))
        assert os.path.isdir(root)


class TestFileReferences:
    def test_file_inside_sandbox_is_expanded(self, sandbox):
        from app.utils.file_refs import expand_file_references
        (sandbox / "main.py").write_text("print('hi')\n")
        assert "print('hi')" in expand_file_references("look @main.py")

    def test_absolute_path_outside_sandbox_is_not_included(self, sandbox, tmp_path):
        from app.utils.file_refs import expand_file_references
        secret = tmp_path / "private.txt"
        secret.write_text("TOP-SECRET")
        out = expand_file_references(f"look @{secret}")
        assert "TOP-SECRET" not in out and "not included" in out

    def test_env_file_is_not_included(self, sandbox):
        from app.utils.file_refs import expand_file_references
        (sandbox / ".env").write_text("API_KEY=abc")
        out = expand_file_references("look @.env")
        assert "API_KEY" not in out and "protected" in out

    def test_glob_skips_credentials_and_listing_hides_them(self, sandbox):
        from app.utils.file_refs import expand_file_references
        (sandbox / "a.pem").write_text("-----BEGIN KEY-----")
        (sandbox / "b.pem.txt").write_text("fine")
        globbed = expand_file_references("@*")
        assert "BEGIN KEY" not in globbed and "fine" in globbed
        listing = expand_file_references("@.")
        assert "a.pem" not in listing.replace("b.pem.txt", "")


class TestAnalyzeCodebaseCollection:
    def test_only_denied_paths_returns_explicit_error(self, sandbox, tmp_path):
        from app.tools.code.analyze_codebase import analyze_codebase
        outside = tmp_path / "outside.py"
        outside.write_text("x = 1")
        result = analyze_codebase("review", [str(outside), str(sandbox / ".env")])
        assert "outside the sandbox" in result

    def test_directory_walk_skips_credentials(self, sandbox):
        module = importlib.import_module("app.tools.code.analyze_codebase")
        (sandbox / "app.py").write_text("x = 1")
        (sandbox / ".ssh").mkdir()
        (sandbox / ".ssh" / "id_rsa").write_text("PRIVATE")
        (sandbox / ".env").write_text("K=V")
        captured = {}

        def fake_generate(model, contents, config):
            captured["prompt"] = contents
            return MagicMock(candidates=[1], text="ok")

        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = fake_generate
        with patch.object(module, "client", fake_client), \
             patch.object(module, "conversation_memory", MagicMock(
                 get_or_create_thread=MagicMock(return_value=("t1", True, None)),
                 get_thread_history=MagicMock(return_value=[]))):
            result = module.analyze_codebase("review", [str(sandbox)])
        assert "x = 1" in captured["prompt"]
        assert "PRIVATE" not in captured["prompt"] and "K=V" not in captured["prompt"]
        assert "Not sent" in result


class TestDownloadHostChecks:
    def test_non_google_url_is_refused(self):
        from app.services import interactions
        with patch.object(interactions, "_client", return_value=MagicMock()):
            with pytest.raises(ValueError, match="non-Google"):
                interactions._download_uri("https://evil.example.com/file.mp4")

    def test_lookalike_host_is_refused(self):
        from app.services import interactions
        assert not interactions._is_google_https("https://googleapis.com.evil.io/x")
        assert not interactions._is_google_https("http://storage.googleapis.com/x")
        assert interactions._is_google_https("https://storage.googleapis.com/x")

    def test_files_uri_uses_the_sdk(self):
        from app.services import interactions
        fake = MagicMock()
        fake.files.download.return_value = b"data"
        with patch.object(interactions, "_client", return_value=fake):
            data = interactions._download_uri(
                "https://generativelanguage.googleapis.com/v1beta/files/abc123:download?alt=media")
        assert data == b"data"
        fake.files.download.assert_called_once_with(file="files/abc123")

    def test_redirect_to_non_google_is_not_followed(self):
        from app.services import interactions
        redirect = MagicMock(is_redirect=True, headers={"location": "https://evil.example.com/x"})
        with patch.object(interactions, "_client", return_value=MagicMock()), \
             patch("httpx.get", return_value=redirect) as get:
            with pytest.raises(ValueError, match="outside Google"):
                interactions._download_uri("https://storage.googleapis.com/bucket/video.mp4")
        assert get.call_count == 1


class TestReviewHardening:
    """Gaps found by the pre-release security review."""

    @pytest.mark.parametrize("name", ["CLAUDE.md", ".claude/settings.json", ".git/hooks/x.json",
                                      ".vscode/tasks.json", "AGENTS.md", ".mcp.json"])
    def test_agent_and_hook_files_are_never_written(self, sandbox, name):
        ext = os.path.splitext(name)[1]
        with pytest.raises(ValueError, match="never written"):
            safe_output_path(str(sandbox / name), {ext})

    def test_generate_code_refuses_git_hooks(self, sandbox):
        from app.tools.code.generate_code import save_generated_files
        results = save_generated_files(
            [{"action": "create", "path": ".git/hooks/pre-commit", "content": "rm -rf ~"},
             {"action": "create", "path": "src/ok.py", "content": "x = 1"}],
            str(sandbox))
        by_path = {r["path"]: r["status"] for r in results}
        assert by_path == {".git/hooks/pre-commit": "error", "src/ok.py": "success"}
        assert not (sandbox / ".git").exists()

    def test_deny_list_ignores_case(self):
        home = os.path.realpath(os.path.expanduser("~"))
        assert sensitive_reason(os.path.join(home, ".SSH", "config"))
        assert sensitive_reason(os.path.join(home, ".Claude", "settings.json"))
        assert sensitive_reason("/x/Credentials")

    def test_absolute_recursive_glob_is_refused_before_walking(self, sandbox):
        from app.utils import file_refs
        with patch.object(file_refs.glob_module, "glob") as globber:
            out = file_refs.expand_file_references("@/**/*")
        globber.assert_not_called()
        assert "not included" in out

    def test_analyze_codebase_absolute_glob_not_walked(self, sandbox):
        module = importlib.import_module("app.tools.code.analyze_codebase")
        with patch.object(module.glob_module, "glob") as globber:
            result = module.analyze_codebase("review", ["/**/*.py"])
        globber.assert_not_called()
        assert "outside the sandbox" in result

    def test_generated_outputs_can_feed_other_tools(self, sandbox, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "output_dir", str(tmp_path / "outputs"))
        out = default_output_path("gemini_image", ".png")
        Path(out).write_bytes(b"png")
        assert safe_input_path(out, {".png"}) == os.path.realpath(out)

    def test_sandbox_root_slash(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "sandbox_root", "/")
        target = tmp_path / "f.txt"
        assert validate_path(str(target)) == os.path.realpath(str(target))

    def test_relative_symlink_output_checked_against_sandbox(self, sandbox, monkeypatch, tmp_path):
        (sandbox / "real.wav").write_bytes(b"x")
        (sandbox / "link.wav").symlink_to(sandbox / "real.wav")
        monkeypatch.chdir(tmp_path)  # cwd != sandbox: the relative path must be joined to the sandbox
        with pytest.raises(ValueError, match="symbolic link"):
            safe_output_path("link.wav", {".wav"})

    def test_relative_redirect_resolved_against_google_host(self):
        from app.services import interactions
        redirect = MagicMock(is_redirect=True, headers={"location": "/download/v.mp4"})
        final = MagicMock(is_redirect=False, content=b"mp4")
        with patch.object(interactions, "_client", return_value=MagicMock()), \
             patch("httpx.get", side_effect=[redirect, final]) as get:
            assert interactions._download_uri("https://storage.googleapis.com/b/v.mp4") == b"mp4"
        assert get.call_args_list[1].args[0] == "https://storage.googleapis.com/download/v.mp4"
        assert "headers" not in get.call_args_list[1].kwargs
