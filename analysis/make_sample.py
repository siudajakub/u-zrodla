"""Recreate the team's synthetic clip with espeak-ng, Pillow and ffmpeg."""
import argparse
from pathlib import Path
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

from .transcribe import MEDIA, ROOT

LINES = [
    "Dzisiaj porozmawiamy o inwestowaniu.",
    "Partnerem programu jest firma Aurora.",
    "Ten materiał powstał we współpracy z firmą Aurora.",
]


def render(directory):
    directory.mkdir(parents=True, exist_ok=True)
    sound = directory / "studio.wav"
    with wave.open(str(sound), "wb") as combined:
        for index, line in enumerate(LINES):
            part = directory / f"voice-{index}.wav"
            subprocess.run(["espeak-ng", "-v", "pl", "-s", "150", "-w", str(part), line], check=True)
            with wave.open(str(part), "rb") as source:
                if index == 0:
                    combined.setparams(source.getparams())
                    combined.writeframes(b'\0\0' * (source.getframerate() // 3))
                combined.writeframes(source.readframes(source.getnframes()))
                combined.writeframes(b'\0\0' * source.getframerate())

    img = Image.new("RGB", (960, 540), "#192f37")
    draw = ImageDraw.Draw(img)
    def font(kind, size):
        return ImageFont.truetype(f"/usr/share/fonts/truetype/freefont/{kind}.ttf", size)
    draw.text((64, 45), "STUDIO AURORA", font=font("FreeSansBold", 21), fill="#9edcca")
    draw.text((64, 136), "Jak działa konto", font=font("FreeSerif", 72), fill="#fff7de")
    draw.text((64, 212), "inwestycyjne?", font=font("FreeSerif", 72), fill="#fff7de")
    for i, y in enumerate([321, 298, 333, 290, 254, 270, 232, 194]):
        x = 620 + i * 31
        draw.line((x, y-36, x, y+44), fill="#a9d3c7", width=2)
        draw.rectangle((x-8, y-16, x+8, y+21), fill="#669f93" if i % 3 else "#d49875")
    draw.line((64, 431, 896, 431), fill="#698284", width=1)
    draw.text((64, 456), "Materiał demonstracyjny  /  głos syntetyczny", font=font("FreeSans", 23), fill="#bbc9bd")
    still = directory / "studio.png"
    img.save(still)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-loop", "1", "-framerate", "8",
                    "-i", str(still), "-i", str(sound), "-c:v", "libx264", "-threads", "1",
                    "-tune", "stillimage", "-pix_fmt", "yuv420p", "-g", "8", "-c:a", "aac",
                    "-b:a", "64k", "-movflags", "+faststart", "-shortest", str(MEDIA / "studio.mp4")], check=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, default=ROOT / ".runtime" / "media-build")
    render(p.parse_args().directory)
