# Instructor tools

Not needed by attendees.

## export_model.py: the USB stick fallback

The room has private Wi-Fi, but 23 laptops pulling a 6.6 GB model at once is about 150 GB. Bring a stick so a stalled download costs a minute, not the morning.

1. Format the stick as **exFAT** (macOS: Disk Utility > Erase > Format: ExFAT). FAT32 cannot hold the 5.6 GB model file.
2. Copy the default model to it:

   ```bash
   source .venv/bin/activate
   python instructor/export_model.py /Volumes/<stick-name>
   ```

   It copies only `qwen3.5:9b` (about 6.6 GB) and checks every file against its sha256. Run it again any time; finished files are skipped. Add `--model qwen2.5-coder:7b` to put the fallback model on the stick too.

3. Attendees follow "Model from the USB stick" in `lab-guide/00-setup.md`.

Tested Oct 17, 2026: a separate Ollama server pointed only at the exported folder listed the model and answered a prompt from it.
