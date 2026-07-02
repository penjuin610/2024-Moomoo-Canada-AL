#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


KEYWORD_PATTERN = re.compile(r"user\s*id|moomoo\s*id|\bid\b", re.IGNORECASE)
DIRECT_PATTERNS = [
    re.compile(r"user\s*id\D{0,8}(\d{8})", re.IGNORECASE),
    re.compile(r"(\d{8})\s*\n?\s*user\s*id", re.IGNORECASE),
]
ID_PATTERNS = [
    re.compile(r"user\s*id\D{0,8}(\d{8})", re.IGNORECASE),
    re.compile(r"moomoo\s*id\D{0,8}(\d{8})", re.IGNORECASE),
    re.compile(r"\bid\D{0,6}(\d{8})\b", re.IGNORECASE),
    re.compile(r"\b(\d{8})\b"),
]
IMAGE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}


def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    width, height = image.size
    image = image.resize((width * 2, height * 2))
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return image.point(lambda px: 255 if px > 165 else 0)


def save_temp_image(image: Image.Image) -> Path:
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    image.save(temp_path)
    return temp_path


def convert_heic_to_png(image_path: Path) -> Path:
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    result = subprocess.run(
        ["sips", "-s", "format", "png", str(image_path), "--out", str(temp_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "sips failed")
    return temp_path


def prepare_source_image(image_path: Path) -> tuple[Path, bool]:
    if image_path.suffix.lower() in {".heic", ".heif"}:
        return convert_heic_to_png(image_path), True
    return image_path, False


def build_image_groups(image_path: Path) -> dict[str, Image.Image]:
    source = ImageOps.exif_transpose(Image.open(image_path))
    width, height = source.size
    center_crop = source.crop(
        (
            int(width * 0.28),
            int(height * 0.18),
            int(width * 0.82),
            int(height * 0.72),
        )
    )
    tight_crop = source.crop(
        (
            int(width * 0.34),
            int(height * 0.24),
            int(width * 0.72),
            int(height * 0.58),
        )
    )
    return {"full": source, "center": center_crop, "tight": tight_crop}


def build_variants(image_path: Path, mode: str) -> list[tuple[Path, int, bool]]:
    groups = build_image_groups(image_path)

    if mode == "fast":
        plan = [
            ("tight", 90, 6, True),
            ("tight", 0, 6, True),
            ("center", 90, 6, True),
            ("full", 90, 6, False),
            ("tight", 90, 11, True),
        ]
    else:
        plan = []
        for group_name in ("full", "center", "tight"):
            for angle in (0, 90, 180, 270):
                plan.append((group_name, angle, 6, False))
                plan.append((group_name, angle, 11, False))
                plan.append((group_name, angle, 6, True))

    variants = []
    for group_name, angle, psm, digits_only in plan:
        rotated = groups[group_name].rotate(angle, expand=True)
        variants.append((save_temp_image(preprocess_image(rotated)), psm, digits_only))
    return variants


def run_tesseract(image_path: Path, psm: int, digits_only: bool = False) -> str:
    command = [
        "tesseract",
        str(image_path),
        "stdout",
        "--psm",
        str(psm),
        "-l",
        "eng",
    ]
    if digits_only:
        command.extend(["-c", "tessedit_char_whitelist=0123456789UserID:userid"])
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tesseract failed")
    return result.stdout


def normalize_text(text: str) -> str:
    text = text.replace("|", "I")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("User 1D", "User ID")
    text = text.replace("Userid", "User ID")
    text = text.replace("user \\D", "user ID")
    return text


def find_direct_user_id(text: str) -> str | None:
    for pattern in DIRECT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def score_candidate(candidate: str, context: str) -> int:
    score = 0
    if re.search(r"user\s*id", context, re.IGNORECASE):
        score += 8
    if re.search(r"moomoo", context, re.IGNORECASE):
        score += 5
    if re.search(r"\bid\b", context, re.IGNORECASE):
        score += 3
    if re.fullmatch(r"\d{8}", candidate):
        score += 6
    if len(candidate) == 8:
        score += 4
    return score


def extract_candidates(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = []

    for index, line in enumerate(lines):
        nearby = "\n".join(lines[max(0, index - 1) : min(len(lines), index + 2)])
        line_matches_keyword = bool(KEYWORD_PATTERN.search(nearby))

        for pattern in ID_PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(1)
                score = score_candidate(value, nearby)
                if line_matches_keyword:
                    score += 3
                candidates.append(
                    {
                        "value": value,
                        "score": score,
                        "line": line,
                    }
                )

    deduped = {}
    for candidate in candidates:
        current = deduped.get(candidate["value"])
        if current is None or candidate["score"] > current["score"]:
            deduped[candidate["value"]] = candidate
    return sorted(deduped.values(), key=lambda item: item["score"], reverse=True)


def choose_best_candidate(text_variants: list[str]) -> tuple[str | None, list[dict]]:
    for text in text_variants:
        direct_hit = find_direct_user_id(text)
        if direct_hit:
            return direct_hit, extract_candidates(text)

    all_candidates = []
    for text in text_variants:
        all_candidates.extend(extract_candidates(text))

    deduped = {}
    for candidate in all_candidates:
        current = deduped.get(candidate["value"])
        if current is None or candidate["score"] > current["score"]:
            deduped[candidate["value"]] = candidate

    ranked = sorted(deduped.values(), key=lambda item: item["score"], reverse=True)
    best = ranked[0]["value"] if ranked else None
    return best, ranked


def extract_from_image(image_path: Path, dump_text: bool = False, mode: str = "fast") -> dict:
    source_image_path, should_cleanup_source = prepare_source_image(image_path)
    variants = build_variants(source_image_path, mode=mode)
    texts = []
    direct_hit = None
    try:
        first_text = normalize_text(run_tesseract(source_image_path, psm=6))
        texts.append(first_text)
        direct_hit = find_direct_user_id(first_text)
        for variant_path, psm, digits_only in variants:
            if direct_hit:
                break
            text = normalize_text(run_tesseract(variant_path, psm=psm, digits_only=digits_only))
            texts.append(text)
            direct_hit = find_direct_user_id(text)
    finally:
        if should_cleanup_source:
            source_image_path.unlink(missing_ok=True)
        for variant_path, _, _ in variants:
            variant_path.unlink(missing_ok=True)

    best_candidate, ranked = choose_best_candidate(texts)
    if direct_hit:
        best_candidate = direct_hit
    payload = {
        "file_name": image_path.name,
        "best_candidate": best_candidate,
        "status": "success" if best_candidate else "failed",
        "success_photo_name": image_path.name if best_candidate else "",
        "failed_photo_name": "" if best_candidate else image_path.name,
        "candidates": ranked[:10],
    }
    if dump_text:
        payload["ocr_text"] = texts
    return payload


def iter_image_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def write_csv(rows: list[dict], csv_path: Path) -> None:
    fieldnames = [
        "file_name",
        "user_id",
        "success_photo_name",
        "failed_photo_name",
        "status",
        "top_candidates",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "file_name": row["file_name"],
                    "user_id": row["best_candidate"] or "",
                    "success_photo_name": row["success_photo_name"],
                    "failed_photo_name": row["failed_photo_name"],
                    "status": row["status"],
                    "top_candidates": ",".join(
                        candidate["value"] for candidate in row["candidates"][:3]
                    ),
                }
            )


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def print_progress(
    *,
    label: str,
    completed: int,
    total: int,
    success_count: int,
    failed_count: int,
    started_at: float,
) -> None:
    elapsed = max(time.time() - started_at, 0.001)
    rate = completed / elapsed
    remaining = total - completed
    eta_seconds = remaining / rate if rate > 0 else 0
    percent = (completed / total) * 100 if total else 100
    print(
        f"[{label}] {completed}/{total} ({percent:5.1f}%) | "
        f"success={success_count} failed={failed_count} | "
        f"elapsed={format_duration(elapsed)} eta={format_duration(eta_seconds)}",
        flush=True,
    )


def run_batch(
    image_files: list[Path],
    *,
    mode: str,
    workers: int,
    dump_text: bool,
    label: str,
) -> list[dict]:
    rows = []
    success_count = 0
    failed_count = 0
    started_at = time.time()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(
                extract_from_image,
                image_path,
                dump_text,
                mode,
            ): image_path
            for image_path in image_files
        }

        for completed, future in enumerate(as_completed(future_map), start=1):
            image_path = future_map[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    "file_name": image_path.name,
                    "best_candidate": None,
                    "status": "failed",
                    "success_photo_name": "",
                    "failed_photo_name": image_path.name,
                    "candidates": [],
                    "error": str(exc),
                }
            rows.append(row)
            if row["status"] == "success":
                success_count += 1
            else:
                failed_count += 1
            print_progress(
                label=label,
                completed=completed,
                total=len(image_files),
                success_count=success_count,
                failed_count=failed_count,
                started_at=started_at,
            )

    rows.sort(key=lambda row: row["file_name"])
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract moomoo User ID values from one image or a whole folder."
    )
    parser.add_argument("input_path", type=Path, help="Image file or folder path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON for single-image mode",
    )
    parser.add_argument(
        "--dump-text",
        action="store_true",
        help="Include OCR text in stdout JSON/text output",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path("moomoo_user_ids.csv"),
        help="CSV output path for folder mode or when you want a saved report",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "accurate"],
        default="fast",
        help="fast is much quicker for large batches; accurate tries many more OCR passes",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(8, (os.cpu_count() or 4) - 1)),
        help="Parallel workers for folder mode",
    )
    parser.add_argument(
        "--retry-failed-with-accurate",
        action="store_true",
        help="After a fast pass, retry failed images once with accurate mode",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.input_path.exists():
        print(f"Input not found: {args.input_path}", file=sys.stderr)
        return 1

    image_files = iter_image_files(args.input_path)
    if not image_files:
        print(f"No supported image files found in: {args.input_path}", file=sys.stderr)
        return 1

    if args.input_path.is_file():
        rows = [extract_from_image(image_files[0], dump_text=args.dump_text, mode=args.mode)]
    else:
        print(
            f"Starting batch OCR for {len(image_files)} images | "
            f"mode={args.mode} workers={args.workers}",
            flush=True,
        )
        rows = run_batch(
            image_files,
            mode=args.mode,
            workers=args.workers,
            dump_text=args.dump_text,
            label=f"pass-1:{args.mode}",
        )

        if args.retry_failed_with_accurate and args.mode == "fast":
            failed_files = [
                args.input_path / row["failed_photo_name"]
                for row in rows
                if row["status"] == "failed" and row["failed_photo_name"]
            ]
            if failed_files:
                print(
                    f"Retrying failed images with accurate mode: {len(failed_files)}",
                    flush=True,
                )
                retry_rows = run_batch(
                    failed_files,
                    mode="accurate",
                    workers=args.workers,
                    dump_text=args.dump_text,
                    label="pass-2:accurate",
                )
                retry_map = {row["file_name"]: row for row in retry_rows}
                rows = [retry_map.get(row["file_name"], row) if row["status"] == "failed" else row for row in rows]

    if args.input_path.is_file() and args.json:
        print(json.dumps(rows[0], ensure_ascii=False, indent=2))
        return 0 if rows[0]["best_candidate"] else 2

    if args.input_path.is_file() and not args.csv_output:
        row = rows[0]
        if row["best_candidate"]:
            print(f"Best moomoo User ID candidate: {row['best_candidate']}")
            return 0
        print("No confident User ID candidate found.")
        return 2

    write_csv(rows, args.csv_output)

    success_count = sum(1 for row in rows if row["status"] == "success")
    failed_count = len(rows) - success_count
    print(f"Processed {len(rows)} images.")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"CSV saved to: {args.csv_output.resolve()}")
    return 0 if failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
