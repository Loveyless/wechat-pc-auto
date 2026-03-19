from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int
    alpha: int = 255


@dataclass(frozen=True)
class RoundedRect:
    left: float
    top: float
    right: float
    bottom: float
    radius: float
    color: Color

    def contains(self, px: float, py: float) -> bool:
        if px < self.left or px > self.right or py < self.top or py > self.bottom:
            return False
        if self.left + self.radius <= px <= self.right - self.radius:
            return True
        if self.top + self.radius <= py <= self.bottom - self.radius:
            return True
        nearestX = self.left + self.radius if px < self.left + self.radius else self.right - self.radius
        nearestY = self.top + self.radius if py < self.top + self.radius else self.bottom - self.radius
        dx = px - nearestX
        dy = py - nearestY
        return dx * dx + dy * dy <= self.radius * self.radius


def alpha_blend(bottom: tuple[float, float, float, float], top: Color) -> tuple[float, float, float, float]:
    topAlpha = top.alpha / 255.0
    bottomAlpha = bottom[3]
    outAlpha = topAlpha + bottomAlpha * (1.0 - topAlpha)
    if outAlpha <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    outRed = (top.red / 255.0 * topAlpha + bottom[0] * bottomAlpha * (1.0 - topAlpha)) / outAlpha
    outGreen = (top.green / 255.0 * topAlpha + bottom[1] * bottomAlpha * (1.0 - topAlpha)) / outAlpha
    outBlue = (top.blue / 255.0 * topAlpha + bottom[2] * bottomAlpha * (1.0 - topAlpha)) / outAlpha
    return (outRed, outGreen, outBlue, outAlpha)


def clamp_channel(value: float) -> int:
    return max(0, min(255, round(value * 255.0)))


def render_icon(size: int) -> bytes:
    shellBlue = Color(37, 105, 199)
    panelCream = Color(251, 247, 239)
    ink = Color(29, 38, 50)
    accentAmber = Color(184, 120, 25)
    accentBlue = Color(24, 82, 166)

    shapes = [
        RoundedRect(18.0, 18.0, 238.0, 238.0, 54.0, shellBlue),
        RoundedRect(46.0, 52.0, 164.0, 168.0, 28.0, panelCream),
        RoundedRect(72.0, 82.0, 140.0, 96.0, 7.0, ink),
        RoundedRect(72.0, 108.0, 126.0, 120.0, 6.0, ink),
        RoundedRect(72.0, 130.0, 136.0, 142.0, 6.0, ink),
        RoundedRect(170.0, 62.0, 214.0, 188.0, 22.0, accentAmber),
        RoundedRect(180.0, 138.0, 186.0, 166.0, 3.0, accentBlue),
        RoundedRect(192.0, 118.0, 198.0, 166.0, 3.0, accentBlue),
        RoundedRect(204.0, 126.0, 210.0, 166.0, 3.0, accentBlue),
    ]

    sampleGrid = 4
    scale = 256.0 / float(size)
    image = bytearray()
    for py in range(size):
        for px in range(size):
            pixelRed = 0.0
            pixelGreen = 0.0
            pixelBlue = 0.0
            pixelAlpha = 0.0
            for sampleY in range(sampleGrid):
                for sampleX in range(sampleGrid):
                    iconX = (px + (sampleX + 0.5) / sampleGrid) * scale
                    iconY = (py + (sampleY + 0.5) / sampleGrid) * scale
                    color = (0.0, 0.0, 0.0, 0.0)
                    for shape in shapes:
                        if shape.contains(iconX, iconY):
                            color = alpha_blend(color, shape.color)
                    pixelRed += color[0]
                    pixelGreen += color[1]
                    pixelBlue += color[2]
                    pixelAlpha += color[3]
            sampleCount = float(sampleGrid * sampleGrid)
            image.extend(
                [
                    clamp_channel(pixelRed / sampleCount),
                    clamp_channel(pixelGreen / sampleCount),
                    clamp_channel(pixelBlue / sampleCount),
                    clamp_channel(pixelAlpha / sampleCount),
                ]
            )
    return bytes(image)


def png_chunk(chunkType: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunkType + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunkType + payload + struct.pack(">I", checksum)


def build_png(size: int, rgbaBytes: bytes) -> bytes:
    rows = []
    stride = size * 4
    for index in range(size):
        rowStart = index * stride
        rows.append(b"\x00" + rgbaBytes[rowStart : rowStart + stride])
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", header),
            png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9)),
            png_chunk(b"IEND", b""),
        ]
    )


def build_ico(iconSizes: list[int]) -> bytes:
    pngBlobs = [build_png(size, render_icon(size)) for size in iconSizes]
    header = struct.pack("<HHH", 0, 1, len(iconSizes))
    entries = []
    offset = 6 + len(iconSizes) * 16
    for size, pngBlob in zip(iconSizes, pngBlobs, strict=True):
        encodedSize = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                encodedSize,
                encodedSize,
                0,
                0,
                1,
                32,
                len(pngBlob),
                offset,
            )
        )
        offset += len(pngBlob)
    return header + b"".join(entries) + b"".join(pngBlobs)


def build_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-labelledby="title desc">
  <title id="title">WeChat Auto Shell Icon</title>
  <desc id="desc">A blue rounded square with a cream preview panel and an amber audio meter.</desc>
  <rect x="18" y="18" width="220" height="220" rx="54" fill="#2569c7" />
  <rect x="46" y="52" width="118" height="116" rx="28" fill="#fbf7ef" />
  <rect x="72" y="82" width="68" height="14" rx="7" fill="#1d2632" />
  <rect x="72" y="108" width="54" height="12" rx="6" fill="#1d2632" />
  <rect x="72" y="130" width="64" height="12" rx="6" fill="#1d2632" />
  <rect x="170" y="62" width="44" height="126" rx="22" fill="#b87819" />
  <rect x="180" y="138" width="6" height="28" rx="3" fill="#1852a6" />
  <rect x="192" y="118" width="6" height="48" rx="3" fill="#1852a6" />
  <rect x="204" y="126" width="6" height="40" rx="3" fill="#1852a6" />
</svg>
"""


def main() -> None:
    repoRoot = Path(__file__).resolve().parents[1]
    iconsDir = repoRoot / "desktop-shell" / "src-tauri" / "icons"
    iconsDir.mkdir(parents=True, exist_ok=True)

    svgPath = iconsDir / "icon.svg"
    icoPath = iconsDir / "icon.ico"

    svgPath.write_text(build_svg(), encoding="utf-8", newline="\n")
    icoPath.write_bytes(build_ico([16, 24, 32, 48, 64, 128, 256]))

    print(f"Wrote {svgPath}")
    print(f"Wrote {icoPath}")


if __name__ == "__main__":
    main()
