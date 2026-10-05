# ai_renamer

Renames invoice PDFs to a consistent, sortable filename such as

    ACME-Ltd_2025-03-14_INV0042_1234.50.pdf

by asking a language model to read the invoice and pull out the company, date,
invoice number and total. It works with any **OpenAI-compatible** chat API:
OpenAI, Ollama, LM Studio, OpenRouter, Gemini's OpenAI endpoint, and others.

## How it works

1. **Read the PDF.** By default the text is extracted locally with `pypdf`
   (up to 20,000 characters). With `--send-pdf` the whole PDF is sent instead.
2. **Ask the model.** The model is told to reply with a JSON object:
   `{"company": ..., "date": "YYYY-MM-DD", "invoice_number": ..., "amount": ...}`,
   or `{"error": "..."}` if something is missing. Replies wrapped in
   ```` ```json ```` fences are handled.
3. **Build the filename in code**, not by the model:
   - the date is checked to be a real `YYYY-MM-DD` date
   - the amount is formatted with two decimal places (`1,234.5` → `1234.50`)
   - characters that aren't allowed in filenames (`<>:"/\|?*`) are removed and
     spaces become `-` (`INV/0042` → `INV0042`, `ACME Ltd` → `ACME-Ltd`)
4. **Rename** the file in its own folder, after asking you to confirm. Existing
   files are never overwritten.
5. **Log** the rename to `ai_renamer_log.csv` in the same folder, so it can be undone.

## Requirements

- Python 3.9+
- An OpenAI-compatible API: an API key for a hosted service, or a local server
  such as Ollama or LM Studio

## Installation

    git clone https://github.com/cubes321/ai_renamer.git
    cd ai_renamer
    python -m venv .venv
    # Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt

## Configuration

Each setting can come from an environment variable or a command-line flag. The
flag wins if both are set.

| Setting  | Environment variable | Flag         | Default                    |
|----------|----------------------|--------------|----------------------------|
| API key  | `OPENAI_API_KEY`     | —            | `not-needed` (local servers) |
| Base URL | `OPENAI_BASE_URL`    | `--base-url` | OpenAI (`https://api.openai.com/v1`) |
| Model    | `AI_RENAMER_MODEL`   | `--model`    | `gpt-4o-mini`              |

Setting environment variables:

    # Windows (PowerShell), current session
    $env:OPENAI_API_KEY = "sk-..."
    # Windows, permanently (open a new terminal afterwards)
    setx OPENAI_API_KEY "sk-..."
    # macOS / Linux
    export OPENAI_API_KEY="sk-..."

The API key is never written to disk by the script.

### Provider examples

| Provider   | `--base-url`                                               | Example `--model`   | API key            |
|------------|------------------------------------------------------------|---------------------|--------------------|
| OpenAI     | *(leave unset)*                                            | `gpt-4o-mini`       | OpenAI key         |
| Gemini     | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash`  | Gemini key         |
| OpenRouter | `https://openrouter.ai/api/v1`                             | `openai/gpt-4o-mini`| OpenRouter key     |
| Ollama     | `http://localhost:11434/v1`                                | `llama3.1`          | not needed         |
| LM Studio  | `http://localhost:1234/v1`                                 | the loaded model    | not needed         |

## Usage

    python ai_renamer.py [options] FILE [FILE ...]

### Options

| Option            | Description |
|-------------------|-------------|
| `--model NAME`    | Model to use. |
| `--base-url URL`  | API base URL. |
| `--pattern TEXT`  | Filename pattern (see below). Default: `{company}_{date}_{invoice_number}_{amount}` |
| `--send-pdf`      | Send the whole PDF instead of its extracted text. |
| `-y`, `--yes`     | Rename without asking for confirmation. |
| `--dry-run`       | Show the new names without renaming anything. |
| `--undo`          | Undo the renames logged in the given folders (default: current folder). |
| `-h`, `--help`    | Show help. |

### Examples

Rename one file, confirming first:

    python ai_renamer.py bill.pdf
    bill.pdf -> ACME-Ltd_2025-03-14_INV0042_1234.50.pdf
    Rename? (y/n): y
    Renamed file to: ACME-Ltd_2025-03-14_INV0042_1234.50.pdf

Preview a whole folder, then rename it without prompts:

    python ai_renamer.py --dry-run invoices/*.pdf
    python ai_renamer.py -y invoices/*.pdf

On Windows `cmd.exe` doesn't expand `*.pdf`; use PowerShell instead:

    python ai_renamer.py -y (Get-ChildItem invoices\*.pdf)

Use a local model through Ollama:

    python ai_renamer.py --base-url http://localhost:11434/v1 --model llama3.1 bill.pdf

Use Gemini:

    $env:OPENAI_API_KEY = "<your Gemini key>"
    python ai_renamer.py --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --model gemini-2.5-flash bill.pdf

### Filename patterns

`--pattern` uses Python format syntax with these fields:

| Field              | Example     |
|--------------------|-------------|
| `{company}`        | `ACME-Ltd`  |
| `{date}`           | `2025-03-14`|
| `{invoice_number}` | `INV0042`   |
| `{amount}`         | `1234.50`   |

`.pdf` is added if the pattern doesn't end with it. Unknown fields and path
separators (`/`, `\`) are rejected before any API call.

    python ai_renamer.py --pattern "{date} {company} {amount}" bill.pdf
    # -> 2025-03-14 ACME-Ltd 1234.50.pdf

    python ai_renamer.py --pattern "{company}-{invoice_number}" bill.pdf
    # -> ACME-Ltd-INV0042.pdf

### Scanned PDFs

A scanned invoice is just an image with no text layer, so text extraction finds
nothing and the file is skipped with a hint. Use `--send-pdf` to send the whole
PDF so the model can read the page images:

    python ai_renamer.py --send-pdf scan.pdf

This needs a server and model that accept PDF file inputs (for example OpenAI's
`gpt-4o` / `gpt-4o-mini`). Most local servers don't, and will return an API error.

### Undoing renames

Every rename is appended to `ai_renamer_log.csv` in the PDF's folder:

    time,old,new
    2025-03-20T10:15:02,bill.pdf,ACME-Ltd_2025-03-14_INV0042_1234.50.pdf

`--undo` reverses the logged renames in a folder, newest first, so a file
renamed twice gets its original name back:

    python ai_renamer.py --undo --dry-run invoices   # preview
    python ai_renamer.py --undo invoices             # undo
    python ai_renamer.py --undo                      # current folder

If a renamed file has gone, or its original name is now taken, that entry is
skipped and kept in the log. When everything has been undone the log is deleted.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Every file was renamed, skipped by you, or already correctly named. |
| `1`  | At least one file failed (API error, unreadable PDF, missing details, name already taken, ...). Other files are still processed. |
| `2`  | Invalid command-line arguments (e.g. a bad `--pattern`). |

## Troubleshooting

- **`no text found (scanned PDF?)`** — the PDF has no text layer. Use `--send-pdf`.
- **`could not get a valid name from the model`** — the model's reply wasn't
  valid JSON, a field was missing or malformed, or the model reported an error
  (e.g. the document isn't an invoice). Try a stronger model.
- **`API error: ... 401`** — `OPENAI_API_KEY` is missing or wrong for that server.
- **`API error: Connection error`** — check `--base-url` and that the local
  server is running.
- **`... already exists, skipping`** — another file already has that name,
  for example a duplicate invoice.

## Privacy

The invoice text (or the whole PDF with `--send-pdf`) is sent to whichever API
you configure. Use a local server such as Ollama or LM Studio if invoices must
not leave your machine.
