#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rockbox Theme Rescaler
---------------------
Author: thinkVHS (updated)
Date: 2025-09-03

Description:
Rescales BMP images and coordinates in .wps, .sbs, .fms files
of a Rockbox theme. Copies other files without modifying them.
"""

import argparse
from pathlib import Path
from PIL import Image
from tqdm import tqdm
import shutil
import re
import subprocess, os

def get_bit_depth(file_path):
    result = subprocess.run(
        ['identify', '-format', '%z', file_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        bit_depth = int(result.stdout.strip())
        return bit_depth
    else:
        return None

def get_width(file_path):
    result = subprocess.run(
        ['identify', '-format', '%w', file_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        width = int(result.stdout.strip())
        return width
    else:
        return None


def resize_bmp(input_path, output_path, factor, filter_bg, filter_icon):
    """
    Rescale a BMP image. If detected as an icon (≤32px), NEAREST is used;
    otherwise, the configured filter is applied.
    """
    factor = (1.5,1.5)
    width = get_width(input_path)
    bit_depth = get_bit_depth(input_path)
    magick_filter = "Point"
    os.system(f"mkdir -p \"{'/'.join(str(output_path).split('/')[:-1])}\"")
    if bit_depth != 1:
        if width <= 32:
            os.system(f"magick '{input_path}' -filter Point -resize {int(factor[0]*100)}% '{output_path}'")
        else:
            os.system(f"magick '{input_path}' -filter {filter_bg} -resize {int(factor[0]*100)}% '{output_path}'")
    else:
        if width <= 32:
            os.system(f"magick '{input_path}' -filter Point -resize {int(factor[0]*100)}% '{output_path}'")
        else:
            os.system(f"magick '{input_path}' -filter {filter_bg} -resize {int(factor[0]*100)}% '{output_path}'")

        os.system(f"magick '{output_path}' -monochrome -colors 2 -depth 1 '/tmp/{str(output_path).split('/')[-1]}'")
        os.system(f"mv '/tmp/{str(output_path).split('/')[-1]}' '{output_path}'")
def scale_value(val, factor):
    val = val.strip()
    if val == '-' or val.endswith('%'):
        return val  # do not rescale special values
    try:
        return str(int(int(val) * factor))
    except ValueError:
        return val

def get_image_height(image_path):
    """Retrieve the height of the image at the given path."""
    try:
        with Image.open(image_path) as img:
            return img.height
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return None  # Return None if there's an error

def rescale_wps_file(file_path, out_path, factor_x, factor_y, FILTER_BG, FILTER_ICON):
    """
    Rescale coordinates inside .wps, .sbs, or .fms files.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")

    processed_bmps = []

    patterns = {
        "%V":  ["x","y","width","height","fontid"],
        "%Vl": ["id","x","y","width","height","fontid"],
        "%Vi": ["label","x","y","width","height","fontid"],
        "%dr": ["x","y","width","height","colour1","colour2"],
        "%pb": ["x","y","width","height","filename"],
        "%pv": ["x","y","width","height","filename"],
        "%x":  ["label","filename","x","y"],
        "%xl": ["label","filename","x","y","nimages"],
        "%Cl": ["xpos","ypos","maxwidth","maxheight","halign","valign"],
        "%T":  ["label","x","y","width","height","action","options"],
        "%Lb": ["viewport","width","height","tile"],
        "%XX": ["x","y","width","height","filename","options"]
    }

    for key, params in patterns.items():
        regex = re.compile(rf"{key}\((.*?)\)")
        def repl(match):
            parts = [p.strip() for p in match.group(1).split(",")]
            for i, name in enumerate(params):
                if i < len(parts):
                    if name in ["x","y","width","height","xpos","ypos","maxwidth","maxheight"] and not ((key == "%xl") and (len(parts) == 5)):
                        factor = factor_x if "x" in name else factor_y
                        parts[i] = scale_value(parts[i], factor)
                    elif name == "nimages":
                        # Handle the nimages scaling
                        image_filename = parts[1]  # Assuming the filename is the second parameter
                        image_path = file_path.parent / file_path.stem / image_filename  # Construct the full path
                        original_height = get_image_height(image_path)  # Get the original height
                        scaled_height = int(original_height * factor_y)
                        
                        # Find the next best integer multiple of nimages
                        nimages = int(parts[i]) if parts[i].isdigit() else 1
                        if scaled_height % nimages != 0:
                            factor_new = ((scaled_height // nimages) * nimages ) / original_height
                            height_new = ((scaled_height // nimages) * nimages ) 
                        else:
                            factor_new = factor_x
                        resize_bmp(image_path, Path(out_path.parent) / Path(out_path.stem) / image_filename, (factor_new, factor_new), FILTER_BG, FILTER_ICON)
                        processed_bmps.append(image_path)

            return f"{key}({','.join(parts)})"
        text = regex.sub(repl, text)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    return processed_bmps

def main():
    parser = argparse.ArgumentParser(description="Rescale BMP images and WPS coordinates of a Rockbox theme.")
    parser.add_argument("input_dir", help="Input theme folder (e.g., MyTheme_240p)")
    parser.add_argument("input_res", choices=["240p", "360p"], help="Input resolution")
    parser.add_argument("output_res", choices=["240p", "360p"], help="Output resolution")
    parser.add_argument("--filter", choices=["NEAREST", "LANCZOS"], default="LANCZOS",
                        help="Filter for large images (default: LANCZOS)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"The folder {input_dir} does not exist")

    output_dir = input_dir.parent / f"{input_dir.name}_{args.output_res}"
    output_dir.mkdir(exist_ok=True)

    res_map = {"240p": (320, 240), "360p": (480, 360)}
    in_w, in_h = res_map[args.input_res]
    out_w, out_h = res_map[args.output_res]
    factor_x = out_w / in_w
    factor_y = out_h / in_h

    FILTER_BG = "Point" if args.filter.upper() == "NEAREST" else "Lanczos"
    FILTER_ICON = "Point"

    files = list(input_dir.rglob("*"))
    with tqdm(total=len(files), desc="Processing files") as pbar:
        already_processed = []
        # First pass: Process .wps, .sbs, .fms files
        for file in files:
            if not file.is_file():
                pbar.update(1)
                continue

            rel_path = file.relative_to(input_dir)
            out_file = output_dir / rel_path

            rel_path = file.relative_to(input_dir)
            out_file = output_dir / rel_path

            if file.suffix.lower() == ".bmp":
                if file not in already_processed:
                    resize_bmp(file, out_file, (factor_x, factor_y), FILTER_BG, FILTER_ICON)

            elif file.suffix.lower() in [".wps", ".sbs", ".fms"]:
                processed_bmps = rescale_wps_file(file, out_file, factor_x, factor_y, FILTER_BG, FILTER_ICON)
                for b in processed_bmps:
                    already_processed.append(b)

            else:
                out_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, out_file)

            pbar.update(1)

if __name__ == "__main__":
    main()
