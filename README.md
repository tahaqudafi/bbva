# Inbound Voice Agent

A local inbound receptionist voice agent for Windows.
Listens through a microphone, understands speech, answers support questions
from local documents, and books Google Calendar appointments.

---

## Requirements

- **Python 3.11 or newer** (3.12 recommended)
- Windows 10 / 11
- A working microphone and speakers or headphones
- API accounts: Deepgram, OpenRouter, Google Cloud

---

## Installation (Windows)

### 1. Clone or download the project

```
cd Desktop
# if using git:
git clone <repo-url> voice-agent
cd voice-agent
```

### 2. Create a virtual environment

```
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

sounddevice requires PortAudio. On Windows it is bundled — no extra install needed.

For PDF support, pdfplumber and its dependency `pdfminer.six` install automatically.
For DOCX support, `python-docx` installs automatically.

---

## Environment setup

### 4. Copy the example file and fill it in

```
copy .env.example .env
```

Open `.env` in a text editor and set:

| Variable | Description |
|---|---|
| `DEEPGRAM_API_KEY` | From console.deepgram.com |
| `DEEPGRAM_STT_MODEL` | e.g. `nova-2` |
| `DEEPGRAM_TTS_MODEL` | e.g. `aura-asteria-en` |
| `OPENROUTER_API_KEY` | From openrouter.ai |
| `OPENROUTER_MODEL` | e.g. `google/gemini-flash-1.5` |
| `GOOGLE_CALENDAR_ID` | `primary` for your main calendar |
| `GOOGLE_TIMEZONE` | e.g. `Europe/Madrid` |

---

## Deepgram setup

1. Sign up at https://console.deepgram.com
2. Create an API key with Speech-to-Text and Text-to-Speech access.
3. Paste the key into `DEEPGRAM_API_KEY` in `.env`.

STT model options: `nova-2`, `nova-2-phonecall`, `enhanced`, `base`
TTS voice options: `aura-asteria-en`, `aura-luna-en`, `aura-zeus-en`, and others
(see Deepgram docs for the full list)

---

## OpenRouter setup

1. Sign up at https://openrouter.ai
2. Create an API key.
3. Choose a model that supports tool/function calling, for example:
   - `google/gemini-flash-1.5`
   - `openai/gpt-4o-mini`
   - `anthropic/claude-haiku`
4. Paste into `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in `.env`.

---

## Google Calendar desktop OAuth setup

1. Go to https://console.cloud.google.com
2. Create a project (or use an existing one).
3. Enable the **Google Calendar API**.
4. Go to **APIs & Services → Credentials**.
5. Click **Create Credentials → OAuth 2.0 Client ID**.
6. Application type: **Desktop app**.
7. Download the JSON file and save it as `credentials.json` in the project root.
8. On first run the agent will open a browser window asking you to authorise access.
9. After authorisation a `token.json` file is saved locally (never commit this file).

Both `credentials.json` and `token.json` are in `.gitignore`.

---

## Knowledge base

Place your company documents in the `knowledge/` folder:

```
knowledge/
    faq.txt
    product-catalogue.pdf
    policies.docx
```

Supported formats: `.txt`, `.docx`, `.pdf`

The agent loads all files at startup and searches them when a caller asks
a support question. If the folder is empty the agent will still run but
cannot answer support questions.

---

## Starting the agent

```
python main.py
```

The agent will:
1. Validate configuration
2. Load knowledge documents
3. Authorise Google Calendar (browser on first run)
4. Open the microphone
5. Greet the caller and begin listening

---

## Stopping the agent

Press **Ctrl+C** in the terminal window.

---

## Adjusting barge-in sensitivity

If background noise causes the agent to interrupt itself, raise `VAD_ENERGY_THRESHOLD`
in `.env` (e.g. from `0.005` to `0.02`).

If the agent does not stop speaking when you start talking, lower it.

---

## Running the tests

```
python -m pytest tests/ -v
```

Tests cover:
- Business-day and business-hour checks
- 30-minute duration and timezone handling
- Occupied-slot rejection
- Email normalisation and validation
- Phonetic alphabet parsing (NATO)
- Name / email confirmation state
- Booking cannot succeed without calendar API success
- Failed calendar creation cannot produce success wording
- Unsupported knowledge files are ignored
- Missing knowledge answer returns found=False
- Transfer stub never claims success

Live integration tests (real API keys, real Google auth) are optional and not run
by default.

---

## Known limitations (Windows)

- Only the Windows default audio device is used. Select your headphones as the
  default playback and recording device in Windows Sound Settings before starting.
- PortAudio (used by sounddevice) does not support per-application volume control;
  adjust system volume instead.
- The first Google Calendar authorisation opens a browser on the same machine.
  Run on a machine that has a browser available.

---

## What is not implemented

| Feature | Status |
|---|---|
| Phone-line integration (Twilio, Telnyx, etc.) | Not implemented |
| Outbound calling | Not implemented |
| Human transfer (live connection) | Stub only — tells the caller a representative will follow up |
| Database or persistent conversation history | Not implemented (memory only) |
| Web interface or dashboard | Not implemented |
| Docker / cloud deployment | Not implemented |
| Linux / macOS support | Not tested (audio module is Windows-focused) |

---

## Project layout

```
voice-agent/
├── main.py               Entry point
├── config.py             Environment variable loading and validation
├── audio.py              Microphone capture and speaker playback (Windows)
├── deepgram_service.py   Deepgram STT (streaming) and TTS (REST)
├── openrouter_service.py OpenRouter LLM client
├── calendar_service.py   Google Calendar OAuth and event management
├── knowledge_base.py     Document loading and keyword search
├── conversation.py       Conversation loop, tools, and state
├── phonetic.py           Phonetic alphabet parser and email utilities
├── transfer.py           Human transfer stub
├── knowledge/            Place your .txt / .docx / .pdf files here
├── tests/                Non-live unit tests
├── .env.example          Template for environment variables
├── .gitignore
└── requirements.txt
```