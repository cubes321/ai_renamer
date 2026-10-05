# ai_renamer

Renames invoice PDFs to `[company]_[date]_[invoice number]_[amount].pdf` using any
OpenAI-compatible chat API (OpenAI, Ollama, LM Studio, OpenRouter, Gemini, ...).

The PDF text is extracted locally with `pypdf` and sent as plain text, so scanned
PDFs without a text layer are skipped.

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

Other servers:

    # Ollama
    python ai_renamer.py --base-url http://localhost:11434/v1 --model llama3.1 bill.pdf
    # LM Studio
    python ai_renamer.py --base-url http://localhost:1234/v1 --model <loaded-model> bill.pdf
    # Gemini (OpenAI-compatible endpoint; set OPENAI_API_KEY to your Gemini key)
    python ai_renamer.py --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --model gemini-2.5-flash bill.pdf
