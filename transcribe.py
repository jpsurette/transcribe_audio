"""
Personal project using Modulate's batch and streaming transcription tools

File: Upload a pre-recorded file from the inputs/ directory to the BATCH endpoint (velma-2-stt-batch) to get a transcription.

Auth: MODULATE_API_KEY saved locally to a .env file or passed via --api-key.

Usage:
    export MODULATE_API_KEY==...
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
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv
import os

import requests

API_BASE_URL = "https://modulate-developer-apis.com/api"
BATCH_ENDPOINT = f"{API_BASE_URL}/velma-2-stt-batch"
STREAMING_ENDPOINT = "wss://modulate-developer-apis.com/api/velma-2-stt-streaming"

SAMPLE_RATE = 16_000
CHANNELS = 1
BLOCKSIZE = 1_600
OPUS_READ_CHUNK = 4096
METER_WIDTH = 30 # characters in the live input-level bar

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav", ".opus"} #not inclusive of all accepted filetypes

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUTS_DIR = SCRIPT_DIR / "inputs" # defaults to inputs folder for audio files to transcribe
DEFAULT_OUTPUTS_DIR = SCRIPT_DIR / "outputs"

load_dotenv()

api_key = os.getenv("API_KEY")

# ------------------------------------------------------------------------------------- #
# CLI
# ------------------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Return the parser with arguments for file, directory, and microphone use."""
    # Shared options
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", default=None, help="API key. Overrides the MODULATE_API_KEY environment variable.")
    common.add_argument(
        "--no-diarization",
        dest="diarization",
        action="store_false",
        help="Disable speaker diarization (on by default).",
    )
    common.add_argument("--no-emotion", dest="emotion", action="store_false", help="Disable emotion detection")
    common.add_argument("--no-accent", dest="accent", action="store_false", help="Disable accent detection.")
    common.add_argument("--no-pii", dest="pii", action="store_false", help="Disable PII detection")
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
    file_parser.add_argument(
        "--outputs-dir",
        default=str(DEFAULT_OUTPUTS_DIR),
        help=f"Directory to write transcript files to (default: {DEFAULT_OUTPUTS_DIR})",
    )

    # directory mode
    dir_parser = sub.add_parser(
        "directory", parents=[common], help="Transcribe every audio file in a directory."
    )
    dir_parser.add_argument(
        "--inputs-dir",
        default=str(DEFAULT_INPUTS_DIR),
        help=f"Directory of audio files to transcribe (default: {DEFAULT_INPUTS_DIR})",
    )
    dir_parser.add_argument(
        "--outputs-dir",
        default=str(DEFAULT_OUTPUTS_DIR),
        help=f"Directory to write transcript files to (default: {DEFAULT_OUTPUTS_DIR})",
    )

    return parser


# ------------------------------------------------------------------------------------- #
# File mode
# ------------------------------------------------------------------------------------- #

def run_batch(api_key: str, audio_file_path: Path, output_dir: Path, args: argparse.Namespace) -> None:
    """ Transcribes an audio file and saves the transcripts to output_dir """
    start_time = time.perf_counter()
    print(f"Starting transcription at: {start_time}")

    with open(audio_file_path, "rb") as audio_file:
        response = requests.post(
            BATCH_ENDPOINT,
            headers={"X-API-Key": api_key},
            files={"upload_file": audio_file},
            #data=feature_flags(args),
        )

    print(f"Response status: {response.status_code}")
    response.raise_for_status()
    result = response.json()

    print(f"Finished transcription: {time.perf_counter()}")
    print(f"Audio duration: {result['duration_ms']}ms")

    output_dir.mkdir(parents=True, exist_ok=True)

    stem = audio_file_path.stem
    raw_path = output_dir / f"{stem}.raw_transcript.txt"
    cleaned_path = output_dir / f"{stem}.cleaned_transcript.txt"

    with open(raw_path, "w", encoding="utf-8") as file:
        file.write(result["text"])
    print(f"Raw transcript written to: {raw_path}")


def run_directory(api_key: str, inputs_dir: str, output_dir: str, args: argparse.Namespace) -> None:
    """ Transcribes every audio file in inputs_dir, saves transcripts to output_dir,
    then moves each source file to inputs_dir/transcribed/ """
    inputs_path = Path(inputs_dir)
    output_path = Path(output_dir)
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
            run_batch(api_key, audio_file, output_path, args)
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
        run_batch(api_key, Path(args.audio_file), args)
    elif args.mode == "directory":
        if not os.path.isdir(args.inputs_dir):
            sys.exit(f"Error: inputs directory not found: {args.inputs_dir}")
        run_directory(api_key, args.inputs_dir, args.outputs_dir, args)

if __name__ == "__main__":
    main()