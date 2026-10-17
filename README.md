# LLM Dictionary

A Python command-line application that asks for a word and uses an LLM to generate a dictionary entry with definitions, synonyms, antonyms and example sentences. The model's output is **validated before it is used**, and the provider can be switched without changing the rest of the application.

```json
{
  "word": "kallis",
  "definitions": ["expensive", "dear", "costly"],
  "synonyms": ["hintava", "arvokas", "tyyris"],
  "antonyms": ["halpa", "edullinen"],
  "examples": ["Tämä auto on liian kallis.", "Hän on minulle hyvin kallis ystävä."]
}
```

## Quick start (Windows, VS Code + PowerShell)

1. Unzip and open the `llm-dictionary` folder in VS Code (**File → Open Folder**), then **Terminal → New Terminal**.
2. Install: `python -m pip install -r requirements.txt`
3. Set your key, for Gemini: `$env:GEMINI_API_KEY="your-key"`
4. Run: `python dictionary.py` and type a word, for example `kallis`. Press Enter on an empty line to quit.

No key at hand? `python dictionary.py kallis --provider mock` runs fully offline.

## Usage

```
python dictionary.py                            interactive mode
python dictionary.py kallis                     one word
python dictionary.py kallis -p openai           choose the provider
python dictionary.py kallis -o output           also save output/kallis.json
python dictionary.py happy -l English -d Finnish  English word, Finnish definitions
python dictionary.py --list-providers
```

| Option | Description |
|---|---|
| `-p`, `--provider` | `openai`, `gemini`, `ollama`, `lmstudio` or `mock` (default `$LLM_PROVIDER` or `gemini`) |
| `-m`, `--model` | Model name (default depends on the provider) |
| `-l`, `--lang` | Language of the word (default Finnish) |
| `-d`, `--definition-lang` | Language of the definitions (default English) |
| `-o`, `--output` | Save the entry as JSON (file name, or a folder for `<word>.json`) |
| `-r`, `--retries` | Extra attempts when the model's answer is invalid (default 2) |
| `-t`, `--temperature` | Sampling temperature (default 0.2) |
| `-v`, `--verbose` | Show raw model responses and timings |

## Validation

`validation.py` checks every response before the application uses it:

- the response must be a JSON object (Markdown code fences or text around it are tolerated);
- all five fields must exist, `word` must be a string matching the requested word, and the other four must be lists of non-empty strings;
- **an empty `definitions` list is invalid**;
- the word must not appear in its own synonyms or antonyms, and no word may be both a synonym and an antonym;
- duplicates are removed, extra fields are ignored, and lists are capped at 10 items (reported as notes).

If the response is invalid, the program asks the model again and tells it exactly what was wrong, up to `--retries` times. If it is still invalid, it reports the problems instead of showing bad data. The user's input is validated too: letters only, at most 50 characters.

The offline mock provider can be used to see validation in action: `kallis` returns the valid example, `tyhjä` returns an empty definition list, and `rikki` returns broken JSON.

Run the unit tests with `python -m unittest -v`.

## Switching providers

`providers.py` hides every provider behind one method, `complete(system, user) -> text`. `dictionary.py` never knows which provider it is using.

| Provider | Key variable | Default model |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | gpt-4o-mini |
| `gemini` | `GEMINI_API_KEY` | gemini-3.5-flash-lite |
| `ollama` | none (local, port 11434) | llama3.1 |
| `lmstudio` | none (local, port 1234) | local-model |
| `mock` | none (offline test data) | — |

Adding a provider means adding one line to `PROVIDERS` in `providers.py`.

## Project structure

```
dictionary.py        main program: input, prompt, retries, output
providers.py         provider interface and implementations
validation.py        JSON parsing and validation of the model output
test_validation.py   unit tests for the validation
requirements.txt
output/              saved entries
```
