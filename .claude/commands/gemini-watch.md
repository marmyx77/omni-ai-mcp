---
description: "Understand a video file or YouTube link: summary, key moments with timestamps, Q&A. Usage: /gemini-watch <path or YouTube URL> [question]"
---

Use the `gemini_analyze_video` MCP tool on the video in $ARGUMENTS.

- A YouTube link goes in `youtube_url` (public videos only); a local file goes in `video_path`.
- If the user asked a question, use it as the `prompt`. Otherwise ask for: a short summary, then the key moments as `MM:SS — what happens`, then any people, products or numbers mentioned.
- Use `processing="agentic"` for long videos (over ~10 minutes) or for questions about a specific moment; keep the default `static` for short clips and whole-video summaries.
- Use `model="pro"` only for hard reasoning about the content; `flash` (default) is right for most videos.

Return the analysis as the tool gives it, keeping the timestamps.
