# Flat File Collector

**Bring files scattered across folders and ZIP files together in one place.**

Version 1.0.0 · Testing · Windows, Linux, and macOS

I built Flat File Collector to save the work of opening folder after folder and copying files by hand. Choose a folder to search and a folder to collect into. The tool copies the files it finds, including files inside ZIP downloads, into that one destination.

**Your originals stay where they are.** If two files have the same name, the copies get different names instead of replacing each other.

[Download the project ZIP](https://github.com/HaytamElbouhmidi/flat-file-collector/archive/refs/heads/main.zip) · [Get started](#run) · [Preview before copying](#2-preview-before-copying) · [Command reference](#options)

## What can I use it for?

For example, you may have photos, PDFs, and drawings spread across a project folder, several folders inside it, and old ZIP downloads. Flat File Collector puts copies of those files together so you do not have to collect them one at a time.

| Before | After |
| --- | --- |
| `Documents/photo.jpg` | `Documents_flattened/photo.jpg` |
| `Documents/Project A/notes.pdf` | `Documents_flattened/notes.pdf` |
| Another `photo.jpg` inside `Project A` | `Documents_flattened/photo_2.jpg` |
| `drawing.dxf` inside `Old Files.zip` | `Documents_flattened/drawing.dxf` |
| `results.csv` inside a ZIP within that ZIP | `Documents_flattened/results.csv` |

The output has no matching subfolders. Everything is placed directly in the folder you choose. ZIP files are opened to collect their contents, but the ZIP files themselves are not copied unless you choose that option.

## Before you start

- You need **Python 3.10 or later** installed. Python is the program that runs this tool.
- This version starts with a command in a terminal. A terminal is the window where you paste commands. It has optional folder-picker windows, but it is not a full point-and-click desktop app yet.
- Folder-picker windows need **Tkinter**, Python's window toolkit. If that is unavailable, you can enter folder locations instead.
- Choose a new, empty output folder for your first run. Leave enough free disk space for the copies and unpacked ZIP contents.
- Automated tests have passed on Linux. Native Windows testing is still pending, and macOS compatibility has not been verified.

No additional Python packages are required. Do not run the collector as an administrator unless you have a specific reason to access protected files.

## Run

### 1. Download and open the project folder

1. Use **Download the project ZIP** above, or choose **Code > Download ZIP** on this page.
2. Extract the downloaded ZIP. Open the extracted folder that contains `flatten_files.py`.
3. Open a terminal in that folder. On Windows, use **Open in Terminal** from the folder's right-click menu when available. In Dolphin on KDE, use **Open Terminal Here**.

The commands below are run from that folder. If you see an error saying `flatten_files.py` cannot be found, check that you opened the correct folder.

### 2. Preview before copying

The preview lists where the files would go without copying them into the output folder.

On **Windows**, paste:

```powershell
py flatten_files.py --gui --dry-run
```

On **Linux or macOS**, paste:

```bash
python3 flatten_files.py --gui --dry-run
```

Two folder-picker windows open in turn:

1. Choose the folder you want to search. This is the **source**. Its subfolders and ZIP files are included.
2. Choose a different folder where you want the copies to go. This is the **destination**.

Read the list and the **Summary** in the terminal. Entries marked `PLAN` are proposed copies. If warnings appear, read them to see which files may be skipped. Previewing is not a guarantee that every file can be read and copied later.

### 3. Copy the files

Run the same command without `--dry-run`, then choose the same two folders.

On **Windows**:

```powershell
py flatten_files.py --gui
```

On **Linux or macOS**:

```bash
python3 flatten_files.py --gui
```

Leave the terminal open while it works. When the summary appears, open your destination folder to see the collected files. The summary also reports warnings. A warning means something needs review, not that every file was copied successfully.

**Running it again creates more copies.** It does not replace the output from the previous run. Use a fresh output folder if you want a separate collection.

## If the folder-picker windows do not open

Tkinter is usually included with Python on Windows. On CachyOS or Arch Linux, install the missing window toolkit with:

```bash
sudo pacman -S tk
```

You can also run the tool without folder-picker windows. It will ask you to type or paste the source folder's location:

```powershell
py flatten_files.py
```

On Linux or macOS, use:

```bash
python3 flatten_files.py
```

This creates the output next to the source, with `_flattened` added to its name. For example, collecting from `Documents` creates `Documents_flattened` beside it.

If `py` or `python3` is not recognized, check that Python 3.10 or later is installed before continuing.

## Important behavior

- **Copy only:** Your source files, folders, and ZIPs are never moved or deleted.
- **Same-name files:** Copies get suffixes such as `_2` and `_3`. This also covers names that differ only in capitalization. Existing destination files are not overwritten.
- **All subfolders:** Hidden folders are searched too. Choose the source folder carefully if it contains files you do not want in the collection.
- **Folder links:** Symbolic links, which point to other files or folders, are skipped. This includes symbolic links inside ZIPs.
- **Supported compressed files:** `.zip` files are unpacked, including ZIPs inside other ZIPs. `.7z`, `.rar`, and `.tar` files are copied as ordinary files, not unpacked.
- **Protected or damaged ZIPs:** Password-protected or damaged entries are skipped with warnings. The tool does not ask for a ZIP password.
- **Large ZIPs:** Size and nesting limits reduce the risk of a small download expanding into an unexpectedly large amount of data. Files beyond those limits are skipped and reported.
- **Output inside the source:** This is supported. The destination is excluded from the search so the collector does not keep collecting its own output.
- **Free space:** Make sure the destination has enough room for the copied and unpacked files. Your original folder still takes up space too.

The collector also adjusts unsafe or unsupported filename characters when naming the copies.

## Options

These optional settings go after the command. You do not need them for the folder-picker steps above.

| Option | What it does |
| --- | --- |
| `--dry-run` | Lists the planned copies without writing them into the output folder |
| `--keep-zips` | Copies ZIP files themselves as well as collecting their contents |
| `--verbose` | Shows the source and destination for each copied file |
| `--gui` | Lets you choose the source and destination with folder-picker windows |
| `--max-depth N` | Sets how many levels of ZIPs inside ZIPs can be opened, default `6` |
| `--max-entry-gb N` | Sets the largest unpacked ZIP entry in GiB, default `2` |
| `--max-total-gb N` | Sets the total unpacked ZIP data limit in GiB, default `10` |
| `--version` | Shows the tool's version |

GiB is a file-size unit. These ZIP limits include temporary nested ZIP data, not only the final files in the output folder.

### Enter folder locations directly

On Windows:

```powershell
py flatten_files.py "C:\Users\YourName\Documents"
```

On Linux or macOS:

```bash
python3 flatten_files.py ~/Documents
```

To choose both the source and destination:

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output"
```

Replace the example locations with your own. Keep the quotation marks around locations that contain spaces. On Windows, use `py` instead of `python3` in the examples below.

### Preview and keep the ZIP files too

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output" --dry-run --keep-zips
```

### Increase the ZIP size limits

Only increase these limits for archives you trust and when you have enough free disk space:

```bash
python3 flatten_files.py "/path/to/source" "/path/to/output" --max-entry-gb 8 --max-total-gb 40
```

## Tests

These checks are for development. You do not need to run them to collect files.

From the project folder:

```bash
python3 -m unittest discover -s tests -v
```

## Version history

- **1.0.0:** Initial release with collection from subfolders and nested ZIPs, protection against replacing same-name files, and preview mode.
