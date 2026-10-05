# ai pdf renamer
# Renames invoice PDFs to [company]_[date]_[invoice number]_[amount].pdf
# using any OpenAI-compatible chat completions API.
import argparse
import json
import os
import pathlib
import re
import sys
from datetime import datetime

from openai import OpenAI, APIError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_CHARS = 20000

SYS_INSTRUCT = """You extract invoice details from the text of a PDF.
Reply with a single JSON object and nothing else, using these keys:
  "company": the name of the company that issued the invoice
  "date": the invoice date in the format YYYY-MM-DD
  "invoice_number": the invoice number or other unique identifier
  "amount": the total amount due as a number, without currency symbols
If the text does not contain all of these, reply with {"error": "<what is missing>"}."""


def extract_text(path):
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.strip()[:MAX_CHARS]


def ask_model(client, model, text):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYS_INSTRUCT},
            {"role": "user", "content": text},
        ],
    )
    reply = response.choices[0].message.content.strip()
    # some models wrap JSON in ```json ... ``` fences
    reply = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply)
    return json.loads(reply)


def clean(part):
    part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(part)).strip()
    return re.sub(r"\s+", "-", part)


def build_filename(details):
    if "error" in details:
        raise ValueError(details["error"])
    date = datetime.strptime(details["date"], "%Y-%m-%d").strftime("%Y-%m-%d")
    amount = float(str(details["amount"]).replace(",", ""))
    parts = [clean(details["company"]), date, clean(details["invoice_number"]), f"{amount:.2f}"]
    if not all(parts):
        raise ValueError(f"empty field in {details}")
    return "_".join(parts) + ".pdf"


def rename_file(client, args, filepath):
    text = extract_text(filepath)
    if not text:
        print(f"{filepath}: no text found (scanned PDF?), skipping.")
        return False

    new_path = filepath.with_name(build_filename(ask_model(client, args.model, text)))
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
    print(f"Renamed file to: {new_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Rename invoice PDFs using an OpenAI-compatible API.")
    parser.add_argument("files", nargs="+", type=pathlib.Path, help="PDF files to rename")
    parser.add_argument("--model", default=os.environ.get("AI_RENAMER_MODEL", "gpt-4o-mini"),
                        help="model name (default: $AI_RENAMER_MODEL or gpt-4o-mini)")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="API base URL, e.g. http://localhost:11434/v1 (default: $OPENAI_BASE_URL or OpenAI)")
    parser.add_argument("-y", "--yes", action="store_true", help="rename without asking for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="show the new names without renaming")
    args = parser.parse_args()

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
