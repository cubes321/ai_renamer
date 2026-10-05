# ai_renamer

Renames invoice PDFs to `[company]_[date]_[invoice number]_[amount].pdf` using any
OpenAI-compatible chat API (OpenAI, Ollama, LM Studio, OpenRouter, Gemini, ...).

By default the PDF text is extracted locally with `pypdf` and sent as plain text,
which works with any server. Scanned PDFs without a text layer need `--send-pdf`,
which sends the whole PDF instead (only some servers accept this, e.g. OpenAI).

## Setup

    pip install -r requirements.txt

| Setting  | Env var            | Flag         | Default       |
|----------|--------------------|--------------|---------------|
| API key  | `OPENAI_API_KEY`   |              | `not-needed`  |
| Base URL | `OPENAI_BASE_URL`  | `--base-url` | OpenAI        |
| Model    | `AI_RENAMER_MODEL` | `--model`    | `gpt-4o-mini` |

## Usage

    python ai_renamer.py bill.pdf                 # asks before renaming
    python ai_renamer.py --dry-run *.pdf          # just show the new names
    python ai_renamer.py -y invoices/*.pdf        # rename without asking
    python ai_renamer.py --send-pdf scan.pdf      # send the PDF itself (scanned invoices)

Custom filename pattern, using `{company}`, `{date}`, `{invoice_number}` and `{amount}`
(`.pdf` is added if missing):

    python ai_renamer.py --pattern "{date} {company} {amount}" bill.pdf

Every rename is recorded in `ai_renamer_log.csv` in the PDF's folder. To undo them
(newest first):

    python ai_renamer.py --undo --dry-run invoices   # show what would be undone
    python ai_renamer.py --undo invoices             # default folder: current one

Other servers:

    # Ollama
    python ai_renamer.py --base-url http://localhost:11434/v1 --model llama3.1 bill.pdf
    # LM Studio
    python ai_renamer.py --base-url http://localhost:1234/v1 --model <loaded-model> bill.pdf
    # Gemini (OpenAI-compatible endpoint; set OPENAI_API_KEY to your Gemini key)
    python ai_renamer.py --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --model gemini-2.5-flash bill.pdf
