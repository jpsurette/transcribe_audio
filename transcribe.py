"""
Personal project using Modulate's batch and streaming transcription tools

File: Upload a pre-recorded file from the inputs/ directory to the BATCH endpoint (velma-2-stt-batch) to get a transcription.

Auth: API_KEY saved locally to a .env file or passed via --api-key.

Usage:
    export API_KEY=...
    python transcribe.py file 20260907.m4a

TODO:
Implement- 
    Microphone: Stream a live microphone to the streaming endpoint (velma-2-stt-streaming) over a Websocket and get a transcript back.

Usage:
    python transcribe.py microphone --device 2

NOTE: can find the device number for your microphone with:
    python -m sounddevice
"""

import argparse
import os
import sys
import time

import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from config import CLEANED_DIR, INPUTS_DIR, RAW_DIR
from format_dictation import date_from_filename, format_transcript

API_BASE_URL = "https://modulate-developer-apis.com/api"
BATCH_ENDPOINT = f"{API_BASE_URL}/velma-2-stt-batch"
STREAMING_ENDPOINT = "wss://modulate-developer-apis.com/api/velma-2-stt-streaming"

SAMPLE_RATE = 16_000
CHANNELS = 1
BLOCKSIZE = 1_600
OPUS_READ_CHUNK = 4096
METER_WIDTH = 30 # characters in the live input-level bar

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav", ".opus"} #not inclusive of all accepted filetypes

# The API rejects some extensions whose container it does support, so upload them under an accepted name.
# .m4a (iPhone recordings) is an MP4 container.
UPLOAD_EXTENSION_ALIASES = {".m4a": ".mp4"}

api_key = os.getenv("API_KEY")

# ------------------------------------------------------------------------------------- #
# CLI
# ------------------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Return the parser with arguments for file, directory, and microphone use."""
    # Shared options
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", default=None, help="API key. Overrides the API_KEY environment variable.")
    common.add_argument(
        "--no-diarization",
        dest="diarization",
        action="store_false",
        help="Disable speaker diarization (on by default).",
    )
    common.add_argument("--no-emotion", dest="emotion", action="store_false", help="Disable emotion detection")
    common.add_argument("--no-accent", dest="accent", action="store_false", help="Disable accent detection.")
    common.add_argument("--no-pii", dest="pii", action="store_false", help="Disable PII detection")
    common.add_argument(
        "--format",
        choices=["md", "txt"],
        default="md",
        help="File type for the cleaned transcript (default: md).",
    )
    common.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help=f"Directory to write raw transcripts to (default: {RAW_DIR})",
    )
    common.add_argument(
        "--cleaned-dir",
        type=Path,
        default=CLEANED_DIR,
        help=f"Directory to write cleaned transcripts to (default: {CLEANED_DIR})",
    )
    # store_false flags already default to True — no set_defaults needed/desired here.

    parser = argparse.ArgumentParser(
        description="""
            Transcribe audio with Modulate Velma-2 - batch file upload or (IN PROGRESS) live microphone streaming
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="mode", required=False)

    # file mode
    file_parser = sub.add_parser(
        "file", parents=[common], help="Batch transcribe a single recorded file (m4a/mp3/mp4/wav/opus/...)"
    )
    file_parser.add_argument("audio_file", help="Path to the audio file to transcribe.")

    # directory mode
    dir_parser = sub.add_parser(
        "directory", parents=[common], help="Transcribe every audio file in a directory."
    )
    dir_parser.add_argument(
        "--inputs-dir",
        type=Path,
        default=INPUTS_DIR,
        help=f"Directory of audio files to transcribe (default: {INPUTS_DIR})",
    )

    return parser


# ------------------------------------------------------------------------------------- #
# File mode
# ------------------------------------------------------------------------------------- #

def run_batch(api_key: str, audio_file_path: Path, raw_dir: Path, cleaned_dir: Path, args: argparse.Namespace) -> None:
    """ Transcribes an audio file, saves the raw transcript to raw_dir,
    then saves the formatted transcript to cleaned_dir """
    start_time = time.perf_counter()
    print(f"Starting transcription at: {start_time}")

    suffix = audio_file_path.suffix.lower()
    upload_name = audio_file_path.with_suffix(UPLOAD_EXTENSION_ALIASES.get(suffix, suffix)).name

    with open(audio_file_path, "rb") as audio_file:
        response = requests.post(
            BATCH_ENDPOINT,
            headers={"X-API-Key": api_key},
            files={"upload_file": (upload_name, audio_file)},
            #data=feature_flags(args),
        )

    print(f"Response status: {response.status_code}")
    if not response.ok:
        raise RuntimeError(f"{response.status_code} from API: {response.text}")
    result = response.json()

    print(f"Finished transcription: {time.perf_counter()}")
    print(f"Audio duration: {result['duration_ms']}ms")

    raw_dir.mkdir(parents=True, exist_ok=True)

    stem = audio_file_path.stem
    raw_path = raw_dir / f"{stem}.raw_transcript.txt"

    with open(raw_path, "w", encoding="utf-8") as file:
        file.write(result["text"])
    print(f"Raw transcript written to: {raw_path}")

    cleaned_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = cleaned_dir / f"{stem}.{args.format}"

    with open(cleaned_path, "w", encoding="utf-8") as file:
        file.write(format_transcript(result["text"], recorded_on=recording_date(audio_file_path)))
    print(f"Cleaned transcript written to: {cleaned_path}")


def recording_date(audio_file_path: Path) -> date:
    """Date from a YYYYMMDD timestamp in the filename, else the file's modification date."""
    return date_from_filename(audio_file_path.name) or date.fromtimestamp(audio_file_path.stat().st_mtime)


def run_directory(api_key: str, inputs_dir: Path, raw_dir: Path, cleaned_dir: Path, args: argparse.Namespace) -> None:
    """ Transcribes every audio file in inputs_dir, saves raw and cleaned transcripts,
    then moves each source file to inputs_dir/transcribed/ """
    inputs_path = inputs_dir.expanduser()
    transcribed_path = inputs_path / "transcribed"
    transcribed_path.mkdir(exist_ok=True)

    audio_files = sorted(
        f for f in inputs_path.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    )

    if not audio_files:
        print(f"No audio files found in {inputs_path}")
        return

    print(f"Found {len(audio_files)} audio file(s) to transcribe")

    for audio_file in audio_files:
        print(f"\n--- Processing: {audio_file.name} ---")
        try:
            run_batch(api_key, audio_file, raw_dir, cleaned_dir, args)
        except Exception as e:
            print(f"Error transcribing {audio_file.name}: {e}")
            continue

        destination = transcribed_path / audio_file.name
        shutil.move(str(audio_file), str(destination))
        print(f"Moved {audio_file.name} -> {destination}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode is None:
        # No subcommand given — re-parse as "directory" so common defaults still apply
        args = parser.parse_args(["directory"])

    api_key = args.api_key or os.environ.get("API_KEY")
    if not api_key:
        sys.exit("Error: no API key. Pass --api-key or set API_KEY")

    if args.mode == "file":
        if not os.path.isfile(args.audio_file):
            sys.exit(f"Error: audio file not found: {args.audio_file}")
        run_batch(api_key, Path(args.audio_file), args.raw_dir.expanduser(), args.cleaned_dir.expanduser(), args)
    elif args.mode == "directory":
        if not args.inputs_dir.expanduser().is_dir():
            sys.exit(f"Error: inputs directory not found: {args.inputs_dir}")
        run_directory(api_key, args.inputs_dir, args.raw_dir.expanduser(), args.cleaned_dir.expanduser(), args)

if __name__ == "__main__":
    main()
