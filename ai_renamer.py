# ai pdf renamer
# Renames invoice PDFs to [company]_[date]_[invoice number]_[amount].pdf
# using any OpenAI-compatible chat completions API.
import argparse
import base64
import csv
import json
import os
import pathlib
import re
import string
import sys
from datetime import datetime

from openai import OpenAI, APIError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_CHARS = 20000
DEFAULT_PATTERN = "{company}_{date}_{invoice_number}_{amount}"
LOG_NAME = "ai_renamer_log.csv"
FIELDS = {"company", "date", "invoice_number", "amount"}

SYS_INSTRUCT = """You extract invoice details from a PDF.
Reply with a single JSON object and nothing else, using these keys:
  "company": the name of the company that issued the invoice
  "date": the invoice date in the format YYYY-MM-DD
  "invoice_number": the invoice number or other unique identifier
  "amount": the total amount due as a number, without currency symbols
If the PDF does not contain all of these, reply with {"error": "<what is missing>"}."""


def extract_text(path):
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.strip()[:MAX_CHARS]


def pdf_message(path):
    # sends the whole PDF; only some servers (e.g. OpenAI) accept file parts
    data = base64.b64encode(path.read_bytes()).decode()
    return [
        {"type": "file", "file": {"filename": path.name, "file_data": f"data:application/pdf;base64,{data}"}},
        {"type": "text", "text": "Extract the invoice details from this PDF."},
    ]


def ask_model(client, model, content):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYS_INSTRUCT},
            {"role": "user", "content": content},
        ],
    )
    reply = response.choices[0].message.content.strip()
    # some models wrap JSON in ```json ... ``` fences
    reply = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply)
    return json.loads(reply)


def clean(part):
    part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(part)).strip()
    return re.sub(r"\s+", "-", part)


def check_pattern(pattern):
    names = {name for _, name, _, _ in string.Formatter().parse(pattern) if name is not None}
    unknown = names - FIELDS
    if unknown:
        raise ValueError(f"unknown field(s) in --pattern: {', '.join(sorted(unknown))} "
                         f"(allowed: {', '.join(sorted(FIELDS))})")
    if "/" in pattern or "\\" in pattern:
        raise ValueError("--pattern must not contain path separators")


def build_filename(details, pattern):
    if "error" in details:
        raise ValueError(details["error"])
    fields = {
        "company": clean(details["company"]),
        "date": datetime.strptime(details["date"], "%Y-%m-%d").strftime("%Y-%m-%d"),
        "invoice_number": clean(details["invoice_number"]),
        "amount": f"{float(str(details['amount']).replace(',', '')):.2f}",
    }
    if not all(fields.values()):
        raise ValueError(f"empty field in {details}")
    name = pattern.format(**fields)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def log_rename(old, new):
    log = new.parent / LOG_NAME
    is_new = not log.exists()
    with open(log, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["time", "old", "new"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), old.name, new.name])


def rename_file(client, args, filepath):
    if args.send_pdf:
        content = pdf_message(filepath)
    else:
        content = extract_text(filepath)
        if not content:
            print(f"{filepath}: no text found (scanned PDF?), skipping. Try --send-pdf.")
            return False

    new_path = filepath.with_name(build_filename(ask_model(client, args.model, content), args.pattern))
    if new_path == filepath:
        print(f"{filepath}: already has the right name.")
        return True
    if new_path.exists():
        print(f"{filepath}: {new_path.name} already exists, skipping.")
        return False

    print(f"{filepath.name} -> {new_path.name}")
    if args.dry_run:
        return True
    if not args.yes:
        confirm = input("Rename? (y/n): ")
        if confirm.lower() != "y":
            print("File renaming cancelled.")
            return True
    filepath.rename(new_path)
    log_rename(filepath, new_path)
    print(f"Renamed file to: {new_path}")
    return True


def undo(folder, dry_run):
    # reverses the renames recorded in the folder's log, newest first
    log = folder / LOG_NAME
    if not log.exists():
        print(f"No {LOG_NAME} in {folder}")
        return False
    with open(log, newline="") as f:
        rows = list(csv.DictReader(f))

    ok = True
    remaining = []
    for row in reversed(rows):
        old, new = folder / row["old"], folder / row["new"]
        if not new.exists() or old.exists():
            print(f"Can't undo {new.name} -> {old.name}: "
                  f"{'file missing' if not new.exists() else 'original name is taken'}")
            remaining.append(row)
            ok = False
            continue
        print(f"{new.name} -> {old.name}")
        if dry_run:
            remaining.append(row)
        else:
            new.rename(old)

    if dry_run:
        return ok
    if remaining:
        with open(log, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time", "old", "new"])
            writer.writeheader()
            writer.writerows(reversed(remaining))
    else:
        log.unlink()
    return ok


def main():
    parser = argparse.ArgumentParser(description="Rename invoice PDFs using an OpenAI-compatible API.")
    parser.add_argument("files", nargs="*", type=pathlib.Path,
                        help="PDF files to rename (with --undo: folders to undo, default: current folder)")
    parser.add_argument("--model", default=os.environ.get("AI_RENAMER_MODEL", "gpt-4o-mini"),
                        help="model name (default: $AI_RENAMER_MODEL or gpt-4o-mini)")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="API base URL, e.g. http://localhost:11434/v1 (default: $OPENAI_BASE_URL or OpenAI)")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN,
                        help=f"filename pattern using {{company}}, {{date}}, {{invoice_number}}, {{amount}} "
                             f"(default: {DEFAULT_PATTERN})")
    parser.add_argument("--send-pdf", action="store_true",
                        help="send the whole PDF instead of its text (handles scanned PDFs; needs a server "
                             "that accepts PDF files, such as OpenAI)")
    parser.add_argument("-y", "--yes", action="store_true", help="rename without asking for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="show the new names without renaming")
    parser.add_argument("--undo", action="store_true",
                        help=f"undo the renames recorded in {LOG_NAME} in the given folders")
    args = parser.parse_args()

    if args.undo:
        folders = args.files or [pathlib.Path(".")]
        results = [undo(folder, args.dry_run) for folder in folders]
        sys.exit(0 if all(results) else 1)

    if not args.files:
        parser.error("no PDF files given")
    try:
        check_pattern(args.pattern)
    except ValueError as e:
        parser.error(str(e))

    # local servers (Ollama, LM Studio) don't need a key, but the client requires one
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "not-needed"), base_url=args.base_url)

    failed = False
    for filepath in args.files:
        try:
            if not rename_file(client, args, filepath):
                failed = True
        except APIError as e:
            print(f"{filepath}: API error: {e}")
            failed = True
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"{filepath}: could not get a valid name from the model: {e}")
            failed = True
        except (OSError, PyPdfError) as e:
            print(f"{filepath}: {e}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
