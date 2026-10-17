#!/usr/bin/env python3
"""Copy one Ollama model to a USB stick, and nothing else.

The room Wi-Fi is the bottleneck when 20-odd laptops pull a 6.6 GB model
at once. This writes a folder that attendees copy into ~/.ollama/models,
so Ollama finds the model without downloading it.

  python instructor/export_model.py /Volumes/WORKSHOP
  python instructor/export_model.py /Volumes/WORKSHOP --model qwen2.5-coder:7b

Ollama stores each model as a small manifest plus blob files named by
their sha256. This copies the manifest and exactly the blobs it lists,
then checks every blob against its digest. Safe to run again: blobs that
are already on the stick and verify are skipped. Standard library only.

Format the stick as exFAT first. FAT32, the usual factory format, cannot
hold a file over 4 GB, and the model file is 5.6 GB. exFAT works on macOS
and Linux. (macOS: Disk Utility > Erase > Format: ExFAT.)

Attendees then run (with Ollama quit):

  cp -R /Volumes/WORKSHOP/ollama-models/* ~/.ollama/models/
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

DEFAULT_MODELS_DIR = Path(os.environ.get("OLLAMA_MODELS", Path.home() / ".ollama" / "models"))
CHUNK = 8 * 1024 * 1024


def fail(message):
    print("error: %s" % message, file=sys.stderr)
    raise SystemExit(1)


def manifest_path(models_dir, model):
    """qwen3.5:9b -> manifests/registry.ollama.ai/library/qwen3.5/9b"""
    name, _, tag = model.partition(":")
    tag = tag or "latest"
    parts = name.split("/")
    if len(parts) == 1:
        parts = ["registry.ollama.ai", "library"] + parts
    elif len(parts) == 2:
        parts = ["registry.ollama.ai"] + parts
    return models_dir / "manifests" / Path(*parts) / tag


def sha256_of(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def blob_name(digest):
    return digest.replace(":", "-")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Copy one Ollama model to a USB stick.")
    parser.add_argument("destination", help="the stick, for example /Volumes/WORKSHOP")
    parser.add_argument("--model", default="qwen3.5:9b", help="default: qwen3.5:9b")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR,
                        help="where Ollama keeps models (default: $OLLAMA_MODELS or ~/.ollama/models)")
    args = parser.parse_args(argv)

    source_manifest = manifest_path(args.models_dir, args.model)
    if not source_manifest.is_file():
        fail("%s is not in %s. Pull it first: ollama pull %s" % (args.model, args.models_dir, args.model))

    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    entries = [manifest["config"]] + manifest.get("layers", [])
    total = sum(e.get("size", 0) for e in entries)

    destination = Path(args.destination)
    if not destination.is_dir():
        fail("%s is not a folder. Is the stick mounted?" % destination)
    out_root = destination / "ollama-models"
    out_blobs = out_root / "blobs"
    out_blobs.mkdir(parents=True, exist_ok=True)

    free = shutil.disk_usage(destination).free
    if free < total:
        fail("the stick has %.1f GB free and the model needs %.1f GB." % (free / 1e9, total / 1e9))

    print("Copying %s, %d files, %.1f GB, to %s" % (args.model, len(entries), total / 1e9, out_root))
    for entry in entries:
        digest = entry["digest"]
        expected = digest.split(":", 1)[1]
        source = args.models_dir / "blobs" / blob_name(digest)
        target = out_blobs / blob_name(digest)
        if not source.is_file():
            fail("blob %s is missing from %s. Re-pull the model: ollama pull %s"
                 % (blob_name(digest), args.models_dir / "blobs", args.model))

        if target.is_file() and target.stat().st_size == source.stat().st_size and sha256_of(target) == expected:
            print("  ok (already there)  %s" % blob_name(digest)[:24])
            continue

        try:
            shutil.copyfile(source, target)
        except OSError as error:
            if target.exists():
                target.unlink()
            if entry.get("size", 0) >= 4 * 1024**3:
                fail("could not write a %.1f GB file to the stick (%s). The stick is "
                     "probably FAT32, which caps files at 4 GB. Reformat it as exFAT."
                     % (entry["size"] / 1e9, error.strerror))
            fail("copying %s failed: %s" % (blob_name(digest), error))
        if sha256_of(target) != expected:
            target.unlink()
            fail("%s did not verify after copying. Try another stick or port." % blob_name(digest))
        print("  copied and verified  %s  %.1f GB" % (blob_name(digest)[:24], entry.get("size", 0) / 1e9))

    target_manifest = out_root / source_manifest.relative_to(args.models_dir)
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_manifest, target_manifest)

    print("\nDone. On an attendee laptop, quit Ollama, then run:\n")
    print("  cp -R %s/* ~/.ollama/models/" % out_root)
    print("\nStart Ollama again and check with: ollama list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
