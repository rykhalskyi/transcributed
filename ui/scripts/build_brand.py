from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "brand" / "transcributed-logo.png"
ASSETS = ROOT / "src" / "assets" / "brand"
PUBLIC = ROOT / "public"
ALPHA_THRESHOLD = 16
COLOR_TOLERANCE = 50


def alpha_mask(image: Image.Image) -> Image.Image:
    return image.getchannel("A").point(lambda value: 255 if value > ALPHA_THRESHOLD else 0)


def content_box(image: Image.Image) -> tuple[int, int, int, int]:
    box = alpha_mask(image).getbbox()
    if box is None:
        raise ValueError("source image has no visible pixels")
    return box


def row_runs(image: Image.Image) -> list[tuple[int, int]]:
    mask = alpha_mask(image)
    width, height = image.size
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for y in range(height):
        active = mask.crop((0, y, width, y + 1)).getbbox() is not None
        if active and start is None:
            start = y
        elif not active and start is not None:
            runs.append((start, y))
            start = None
    if start is not None:
        runs.append((start, height))

    merged: list[tuple[int, int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] <= 4:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)
    return merged


def color_box(
    image: Image.Image,
    predicate,
    region: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    pixels = image.load()
    x0, y0, x1, y1 = region
    xs: list[int] = []
    ys: list[int] = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 32 and predicate(red, green, blue):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def near(red: int, green: int, blue: int, target: tuple[int, int, int]) -> bool:
    return all(
        abs(channel - expected) <= COLOR_TOLERANCE
        for channel, expected in zip((red, green, blue), target)
    )


def padded(image: Image.Image, box: tuple[int, int, int, int], pad: int) -> Image.Image:
    x0, y0, x1, y1 = box
    canvas = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(image.crop(box), (pad, pad))
    return canvas


def save(image: Image.Image, path: Path, width: int | None = None, height: int | None = None) -> None:
    if width is not None:
        height = round(image.height * width / image.width)
    elif height is not None:
        width = round(image.width * height / image.height)
    if width is None or height is None:
        raise ValueError("width or height is required")
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    resized.save(path, "PNG", optimize=True)


def square(image: Image.Image, pad: int) -> Image.Image:
    size = max(image.width, image.height) + 2 * pad
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(
        image,
        ((size - image.width) // 2, (size - image.height) // 2),
    )
    return canvas


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    runs = row_runs(source)
    if len(runs) < 2:
        raise ValueError("expected an icon row and a wordmark row")

    icon_run = runs[0]
    wordmark_run = runs[-1]
    full_box = content_box(source)
    icon_box = content_box(source.crop((0, icon_run[0], source.width, icon_run[1])))
    icon_box = (
        icon_box[0],
        icon_box[1] + icon_run[0],
        icon_box[2],
        icon_box[3] + icon_run[0],
    )
    logo = padded(source, full_box, 28)
    save(logo, ASSETS / "transcributed-logo.png", width=320)
    save(logo, ASSETS / "transcributed-logo@2x.png", width=640)

    wordmark_box = content_box(
        source.crop((0, wordmark_run[0], source.width, wordmark_run[1]))
    )
    wordmark_box = (
        wordmark_box[0],
        wordmark_box[1] + wordmark_run[0],
        wordmark_box[2],
        wordmark_box[3] + wordmark_run[0],
    )
    wordmark = padded(source, wordmark_box, 4)
    save(wordmark, ASSETS / "transcributed-wordmark.png", height=24)
    save(wordmark, ASSETS / "transcributed-wordmark@2x.png", height=48)

    mark = padded(source, icon_box, 16)
    save(mark, ASSETS / "transcributed-mark.png", height=128)
    save(mark, ASSETS / "transcributed-mark@2x.png", height=256)

    icon_region = (0, icon_run[0], source.width, icon_run[1])
    navy = color_box(source, lambda r, g, b: near(r, g, b, (30, 10, 78)), icon_region)
    purple = color_box(source, lambda r, g, b: near(r, g, b, (106, 31, 208)), icon_region)
    if navy is None or purple is None:
        raise ValueError("could not find the document and hexagon colours")
    app_box = (
        min(navy[0], purple[0]),
        min(navy[1], purple[1]),
        max(navy[2], purple[2]),
        max(navy[3], purple[3]),
    )
    app_icon = square(padded(source, app_box, 24), 0)
    save(app_icon, ASSETS / "transcributed-app-icon.png", width=512)

    icon_512 = app_icon.resize((512, 512), Image.Resampling.LANCZOS)
    icon_512.save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    save(icon_512, PUBLIC / "favicon-32.png", width=32)
    save(icon_512, PUBLIC / "apple-touch-icon.png", width=180)
    save(icon_512, PUBLIC / "icon-192.png", width=192)
    save(icon_512, PUBLIC / "icon-512.png", width=512)


if __name__ == "__main__":
    main()
