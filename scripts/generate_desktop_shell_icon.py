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
    shellGreen = Color(3, 219, 108)
    shellGlow = Color(229, 255, 239, 62)
    panelShadow = Color(1, 28, 17, 40)
    panelInk = Color(5, 43, 27)
    panelHeader = Color(60, 104, 80)
    panelCream = Color(246, 255, 250)
    lineSoft = Color(179, 248, 208)
    lineMuted = Color(122, 219, 166)
    capsuleShadow = Color(1, 28, 17, 34)
    capsuleCream = Color(241, 255, 247)
    meterDeep = Color(3, 98, 51)
    meterMid = Color(3, 164, 81)

    shapes = [
        RoundedRect(18.0, 18.0, 238.0, 238.0, 58.0, shellGreen),
        RoundedRect(34.0, 30.0, 214.0, 118.0, 42.0, shellGlow),
        RoundedRect(54.0, 58.0, 180.0, 192.0, 34.0, panelShadow),
        RoundedRect(46.0, 50.0, 172.0, 184.0, 34.0, panelInk),
        RoundedRect(62.0, 66.0, 78.0, 82.0, 8.0, panelCream),
        RoundedRect(88.0, 68.0, 150.0, 80.0, 6.0, panelHeader),
        RoundedRect(62.0, 98.0, 148.0, 112.0, 7.0, panelCream),
        RoundedRect(62.0, 122.0, 138.0, 134.0, 6.0, lineSoft),
        RoundedRect(62.0, 144.0, 122.0, 156.0, 6.0, lineMuted),
        RoundedRect(62.0, 166.0, 112.0, 178.0, 6.0, shellGreen),
        RoundedRect(176.0, 76.0, 216.0, 196.0, 20.0, capsuleShadow),
        RoundedRect(168.0, 68.0, 208.0, 188.0, 20.0, capsuleCream),
        RoundedRect(178.0, 132.0, 186.0, 168.0, 4.0, meterDeep),
        RoundedRect(190.0, 112.0, 198.0, 168.0, 4.0, shellGreen),
        RoundedRect(202.0, 124.0, 210.0, 168.0, 4.0, meterMid),
        RoundedRect(178.0, 88.0, 210.0, 96.0, 4.0, lineSoft),
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
    for size, pngBlob in zip(iconSizes, pngBlobs):
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
  <desc id="desc">A vivid green shell icon with a dark message panel and a bright audio meter capsule.</desc>
  <rect x="18" y="18" width="220" height="220" rx="58" fill="#03db6c" />
  <rect x="34" y="30" width="180" height="88" rx="42" fill="#e5ffef" fill-opacity="0.243" />
  <rect x="54" y="58" width="126" height="134" rx="34" fill="#011c11" fill-opacity="0.157" />
  <rect x="46" y="50" width="126" height="134" rx="34" fill="#052b1b" />
  <rect x="62" y="66" width="16" height="16" rx="8" fill="#f6fffa" />
  <rect x="88" y="68" width="62" height="12" rx="6" fill="#3c6850" />
  <rect x="62" y="98" width="86" height="14" rx="7" fill="#f6fffa" />
  <rect x="62" y="122" width="76" height="12" rx="6" fill="#b3f8d0" />
  <rect x="62" y="144" width="60" height="12" rx="6" fill="#7adba6" />
  <rect x="62" y="166" width="50" height="12" rx="6" fill="#03db6c" />
  <rect x="176" y="76" width="40" height="120" rx="20" fill="#011c11" fill-opacity="0.133" />
  <rect x="168" y="68" width="40" height="120" rx="20" fill="#f1fff7" />
  <rect x="178" y="132" width="8" height="36" rx="4" fill="#036233" />
  <rect x="190" y="112" width="8" height="56" rx="4" fill="#03db6c" />
  <rect x="202" y="124" width="8" height="44" rx="4" fill="#03a451" />
  <rect x="178" y="88" width="32" height="8" rx="4" fill="#b3f8d0" />
</svg>
"""


def main() -> None:
    repoRoot = Path(__file__).resolve().parents[1]
    iconsDir = repoRoot / "desktop-shell" / "src-tauri" / "icons"
    iconsDir.mkdir(parents=True, exist_ok=True)

    svgPath = iconsDir / "icon.svg"
    icoPath = iconsDir / "icon.ico"
    pngPath = iconsDir / "icon.png"

    with svgPath.open("w", encoding="utf-8", newline="\n") as svgFile:
        svgFile.write(build_svg())
    icoPath.write_bytes(build_ico([16, 24, 32, 48, 64, 128, 256]))
    pngPath.write_bytes(build_png(256, render_icon(256)))

    print(f"Wrote {svgPath}")
    print(f"Wrote {icoPath}")
    print(f"Wrote {pngPath}")


if __name__ == "__main__":
    main()
