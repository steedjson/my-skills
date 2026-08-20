#!/usr/bin/env python3
"""把宽图从左到右切成带重叠的分段，供视觉逐段读取。

用法: python3 wide_crop.py <image> <out-dir> [--seg 1200] [--overlap 60]
依赖 PIL。无 PIL 时回退 sips 居中裁剪（只能得到中间段，会打印警告）。
"""
import argparse
import os
import shutil
import subprocess
import sys


def crop_with_pil(path, out_dir, seg, overlap):
    from PIL import Image  # 延迟导入：无 PIL 走回退

    im = Image.open(path)
    w, h = im.size
    os.makedirs(out_dir, exist_ok=True)
    if w <= seg:
        out = os.path.join(out_dir, "full.png")
        im.save(out)
        print(out)
        return

    step = seg - overlap
    x = 0
    i = 0
    while x < w:
        right = min(x + seg, w)
        im.crop((x, 0, right, h)).save(os.path.join(out_dir, f"seg{ i:02d}.png"))
        print(os.path.join(out_dir, f"seg{ i:02d}.png"))
        i += 1
        if right >= w:
            break
        x += step


def crop_with_sips(path, out_dir, seg, h_hint):
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "center.png")
    subprocess.run(
        ["sips", "--cropToHeightWidth", str(h_hint), str(seg), path, "--out", out],
        check=True,
        capture_output=True,
    )
    print(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("out_dir")
    ap.add_argument("--seg", type=int, default=1200, help="每段宽度像素")
    ap.add_argument("--overlap", type=int, default=60, help="相邻段重叠像素")
    a = ap.parse_args()
    if a.overlap >= a.seg:
        ap.error("--overlap 必须小于 --seg")

    try:
        crop_with_pil(a.image, a.out_dir, a.seg, a.overlap)
        return
    except ImportError:
        pass

    # 回退：sips 居中裁剪（偏移不可控），至少拿到中段
    print("WARN: 无 PIL，回退 sips 居中裁剪（仅中间段）。建议: pip install pillow", file=sys.stderr)
    h = 1000  # sips 需要高度参数；宽表场景用 1000 足够多数设计截图，失败则让用户自定
    if shutil.which("sips"):
        try:
            crop_with_sips(a.image, a.out_dir, a.seg, h)
            return
        except subprocess.CalledProcessError as e:
            print(f"sips 失败: {e.stderr or e.stdout}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
