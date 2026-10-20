# Flat File Collector

**Version:** 1.0.0  
**Requirements:** Python 3.10 or later. No third-party Python packages.

I use this script to collect files from a folder, all of its subfolders, and ZIP archives into one flat destination folder. ZIP files inside other ZIP files are supported.

The original files and folders stay unchanged. Nothing is deleted or overwritten.

## What it does

- Recursively finds files, including those in hidden folders.
- Opens `.zip` archives and ZIP files nested inside them.
- Puts all discovered files directly into one output folder without recreating subfolders.
- Renames filename collisions with `_2`, `_3`, and so on, including case-insensitive collisions.
- Skips symbolic links and sanitizes ZIP member filenames.
- Supports a no-write preview and optional native folder-selection dialogs.
- Uses configurable extraction limits to reduce the risk of ZIP bombs.

ZIP archives are unpacked but the ZIP container files are not copied by default. Add `--keep-zips` to copy the ZIP files too.

## Example

Before:

```text
Documents/
├── photo.jpg
├── Project A/
│   ├── notes.pdf
│   └── photo.jpg
└── Old Files.zip
    ├── drawing.dxf
    └── archive.zip
        └── results.csv
```

After:

```text
Documents_flattened/
├── photo.jpg
├── notes.pdf
├── photo_2.jpg
├── drawing.dxf
└── results.csv
```

## Run

Save `flatten_files.py` and open a terminal in the folder containing it.

### Windows

```powershell
py flatten_files.py "C:\Users\YourName\Documents"
```

### Linux or macOS

```bash
python3 flatten_files.py ~/Documents
```

When only the source is specified, the destination is created next to it with `_flattened` added to the folder name.

To designate both folders:

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output"
```

On Windows, use `py` instead of `python3` if needed.

To select source and output directories with folder-picking dialogs:

```bash
python3 flatten_files.py --gui
```

The GUI requires Tkinter, which is usually installed with Python on Windows. On CachyOS or Arch Linux, install it with `sudo pacman -S tk` if needed. Folder paths work without Tkinter.

Running without arguments starts a terminal prompt for the source folder and uses the default destination.

## Options

| Option | Behavior |
| --- | --- |
| `--dry-run` | Preview the destination names without writing files |
| `--keep-zips` | Keep ZIP containers in the output along with extracted contents |
| `--verbose` | Print the source and destination for every copied file |
| `--gui` | Open native folder-selection dialogs |
| `--max-depth N` | Set nested ZIP depth, default `6` |
| `--max-entry-gb N` | Set largest ZIP entry size in GiB, default `2` |
| `--max-total-gb N` | Set total uncompressed ZIP data limit in GiB, default `10` |
| `--version` | Show the script version |

For example, preview the collection and include ZIP containers:

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output" --dry-run --keep-zips
```

To raise the extraction limits for a trusted archive collection:

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output" --max-entry-gb 8 --max-total-gb 40
```

## Important behavior

- **Copy only:** Source files and ZIPs are never moved or deleted.
- **No overwrite:** If a filename already exists in the destination, the next available numbered name is used.
- **Safe destination:** The destination can be inside the source folder. The script excludes that destination while searching.
- **Archives:** `.zip` is supported. `.7z`, `.rar`, and `.tar` are not currently unpacked and are collected as ordinary files.
- **Protected archives:** Password-protected and damaged ZIP members are skipped with warnings.
- **Symbolic links:** Linked source files, linked folders, and ZIP symbolic links are skipped.
- **Extraction limits:** Limits apply to decompressed ZIP data, including intermediate nested ZIP files. Oversized entries are skipped and reported.
- **Reruns:** Running again in the same destination creates additional numbered copies rather than replacing existing output.
- **Free space:** Make sure the destination has enough disk space for the extracted contents.

## Tests

Run the built-in unit tests from the repository directory:

```bash
python3 -m unittest discover -s tests -v
```

## Version history

- **1.0.0:** Initial release with recursive file collection, nested ZIP handling, filename conflict protection, and preview mode.
