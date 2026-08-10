# learn_wiki

A personal knowledge-graph wiki. Paste a URL (web page or video); it extracts a
typed entity graph with citations and draws it in your browser.

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    # system dependency for video: ffmpeg (e.g. `brew install ffmpeg`)
    # Claude Code must be logged into your subscription on this machine.

## Run

    python -m learn_wiki
    # open http://127.0.0.1:8000

## Test

    pytest                       # fast unit tests (no network, no subscription)
    pytest tests/smoke -v        # live tests: real Claude extraction and video transcription
