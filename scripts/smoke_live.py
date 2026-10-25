#!/usr/bin/env python3
"""
Live smoke test: one minimal real call per tool against the Gemini API.

The unit suite is hermetic (no network) and validates every request against the
SDK schema; this script checks what only the live API can tell: that each model
accepts the request and returns what the tool expects.

    GEMINI_API_KEY=... python3 scripts/smoke_live.py                 # cheap calls only
    GEMINI_API_KEY=... python3 scripts/smoke_live.py --expensive     # + video, music, deep research, agent
    GEMINI_API_KEY=... python3 scripts/smoke_live.py --only tts,image

Outputs go to a temporary folder printed at the end. Exit code 1 if any check fails.
Costs: the cheap set is a few cents; --expensive adds a short 360p video, a 30 s
music clip, a standard Deep Research run and a short agent task.
"""

import argparse
import os
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GEMINI_ACTIVITY_LOG", "false")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expensive", action="store_true", help="also run video, music, deep research, agent")
    parser.add_argument("--only", default="", help="comma-separated check names")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set")
        return 2

    # Outputs go to a temp folder: make it the sandbox root before the config loads
    out = tempfile.mkdtemp(prefix="omni_smoke_")
    os.environ["GEMINI_SANDBOX_ROOT"] = out

    from app import __version__
    from app.tools.text.models import list_models
    from app.tools.text.ask_gemini import ask_gemini
    from app.tools.text.ask_model import ask_model
    from app.tools.web.web_search import web_search
    from app.tools.media.generate_image import generate_image
    from app.tools.media.analyze_image import analyze_image
    from app.tools.media.text_to_speech import text_to_speech
    from app.tools.media.transcribe_audio import transcribe_audio
    from app.tools.media.voices import list_voices
    from app.tools.media.analyze_video import analyze_video
    from app.tools.text.embed import embed
    from app.tools.media.generate_video import generate_video
    from app.tools.media.generate_music import generate_music
    from app.tools.web.deep_research import deep_research
    from app.tools.web.agent_task import agent_task

    img = os.path.join(out, "img.png")   # the tool fixes the extension to the returned MIME type (often .jpg)

    def saved_image() -> str:
        for name in sorted(os.listdir(out)):
            if name.startswith("img."):
                return os.path.join(out, name)
        return img
    wav = os.path.join(out, "tts.wav")

    checks = [
        ("models", False, lambda: list_models(include_openrouter=False), "auto-detected"),
        ("pro", False, lambda: ask_gemini("Reply with the single word OK.", model="pro", thinking_level="low"), "OK"),
        ("flash", False, lambda: ask_gemini("Reply with the single word OK.", model="flash", temperature=0.2), "OK"),
        ("gemma", False, lambda: ask_model("Reply with the single word OK.", model="gemma-4-31b-it"), "OK"),
        ("search", False, lambda: web_search("What is the capital of Italy? One word.", model="flash"), "Rom"),
        ("image", False, lambda: generate_image("A flat blue circle on white", model="flash", aspect_ratio="4:1",
                                                output_path=img), "saved"),
        ("image_lite", False, lambda: generate_image("A flat red square on white", model="lite",
                                                     output_path=os.path.join(out, "lite.png")), "saved"),
        ("vision", False, lambda: analyze_image(saved_image(), prompt="What shape and colour? Five words max."), "circle"),
        ("robotics", False, lambda: analyze_image(saved_image(), prompt="Point to the circle. JSON [{\"point\": [y, x], \"label\": ...}]",
                                                  model="robotics"), "point"),
        ("tts", False, lambda: text_to_speech("Buongiorno, questa è una prova.", style="calm", language="it-IT",
                                              output_path=wav), "Audio generated"),
        ("tts_lite", False, lambda: text_to_speech("Ciao.", model="lite", output_path=os.path.join(out, "lite.wav")),
         "Audio generated"),
        ("transcribe", False, lambda: transcribe_audio(wav, word_timestamps=True), "Transcribed"),
        ("voices", False, lambda: list_voices(language_codes=["it-IT"], page_size=3), "`"),
        ("youtube", False, lambda: analyze_video("One sentence summary.", youtube_url="https://www.youtube.com/watch?v=9hE5-98ZeCg",
                                                 model="flash-lite"), "---"),
        ("embed", False, lambda: embed(texts=["cat", "dog"], task="similarity", output_dimensionality=768), "\"dimensions\": 768"),
        ("video", True, lambda: generate_video("A paper boat floating on a calm pond, gentle ambient sound", resolution="360p",
                                               duration=3, output_path=os.path.join(out, "v.mp4")), "Video generated"),
        ("music", True, lambda: generate_music("Cheerful acoustic guitar jingle, instrumental", model="clip",
                                               output_path=os.path.join(out, "m.mp3")), "Music generated"),
        ("research", True, lambda: deep_research("In two sentences: what is the Model Context Protocol? Cite sources.",
                                                 max_wait_minutes=20), "Deep Research Report"),
        ("agent", True, lambda: agent_task("Compute 2**64 with Python and report the number.", tools=["code_execution"],
                                           max_wait_minutes=10), "18446744073709551616"),
    ]
    if os.environ.get("OPENROUTER_API_KEY"):
        checks += [
            ("openrouter", False, lambda: ask_model("Reply with the single word OK.", model="openai/gpt-4o-mini"), "OK"),
            ("or_google", False, lambda: ask_model("Reply with the single word OK.", model="flash",
                                                   provider="openrouter"), "OK"),
            # An error is the expected outcome here: prefixed so the generic "Error" check doesn't fail it
            ("or_bad_id", False, lambda: "expected: " + ask_model("hi", model="nobody/no-such-model-xyz"),
             "gemini_list_models"),
        ]
    only = {c.strip() for c in args.only.split(",") if c.strip()}
    failures = 0
    print(f"omni-ai-mcp {__version__} — live smoke test → {out}\n")
    for name, expensive, fn, expect in checks:
        if only and name not in only:
            continue
        if expensive and not args.expensive and name not in only:
            print(f"  skip  {name:11} (use --expensive)")
            continue
        started = time.time()
        try:
            result = fn() or ""
            ok = expect.lower() in result.lower() and not result.startswith(("Error", "**Error"))
        except Exception:
            result, ok = traceback.format_exc(limit=2), False
        failures += not ok
        first = result.strip().splitlines()[0][:110] if result.strip() else "(empty)"
        print(f"  {'PASS' if ok else 'FAIL'}  {name:11} {time.time() - started:5.1f}s  {first}")
    print(f"\n{'all checks passed' if not failures else f'{failures} check(s) failed'} — outputs in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
