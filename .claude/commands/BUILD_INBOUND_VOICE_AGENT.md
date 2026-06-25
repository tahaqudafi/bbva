---
name: Build Inbound Voice Agent
description: Build and maintain a local inbound AI voice-agent prototype in Python for Windows using Deepgram for STT and TTS, OpenRouter for the conversational model, Google Calendar for appointment booking, and local PDF, DOCX, and TXT files for customer-support knowledge.
argument-hint: "[build|fix|test|feature description]"
disable-model-invocation: true
effort: high
---

# Build the Inbound Voice Agent

You are the coding assistant for this project.

Your role is to write, run, test, debug, and maintain the code. You are not the runtime voice agent.

Follow the requirements in this file exactly. Do not add technologies, providers, infrastructure, features, or architectural complexity that were not requested.

When a necessary implementation detail is genuinely unknown and cannot be inferred safely, ask the user. Do not guess.

## Project goal

Build a local inbound voice-agent prototype that runs on a Windows PC.

The agent should behave like a receptionist that can:

- answer customer-support questions using local company documents;
- book appointments in Google Calendar;
- offer a future human-transfer option without implementing a real transfer yet.

This version is for local testing only.

It is not connected to a phone line.

It is inbound only.

Do not implement outbound calling.

## Fixed technology requirements

Use:

- Python;
- Deepgram for speech-to-text;
- Deepgram for text-to-speech;
- OpenRouter for the language model;
- Google Calendar for appointments;
- local files for the knowledge base;
- environment variables for API keys and configurable settings.

Do not replace these services unless the user explicitly asks.

## Explicit exclusions

Do not add:

- TypeScript;
- a database;
- SQLite;
- PostgreSQL;
- Redis;
- a vector database;
- Docker;
- Docker Compose;
- Kubernetes;
- FastAPI;
- Flask;
- a web interface;
- a dashboard;
- Twilio;
- Telnyx;
- LiveKit;
- a phone provider;
- CRM integration;
- Outlook integration;
- outbound calling;
- cloud deployment;
- live web search;
- additional LLM providers;
- additional STT providers;
- additional TTS providers;
- user accounts;
- analytics platforms.

## Local runtime

The application must run locally from the terminal.

The intended start command should be simple, such as:

```bash
python main.py
```

The application should:

1. validate its configuration;
2. initialize microphone input;
3. initialize speaker or headphone output;
4. connect to Deepgram streaming STT;
5. initialize Deepgram TTS;
6. initialize the OpenRouter client;
7. load the local knowledge base;
8. initialize Google Calendar access;
9. begin continuous listening;
10. greet the user;
11. continue until the user exits.

Provide a clear way to stop the program cleanly.

## Operating-system target

Optimize the first version for Windows.

Use Python libraries that work reliably on Windows.

The user will test while wearing headphones.

Do not implement Linux support now.

Keep any Windows-specific audio code isolated enough that Linux support can be added later.

Document all Windows installation steps clearly.

## Continuous conversation

The user should be able to speak naturally without pressing a button before every sentence.

The application must:

- listen continuously;
- use streaming speech recognition;
- detect completed user turns;
- avoid sending every partial transcript to OpenRouter;
- send stable or final utterances to the language model;
- speak responses through Deepgram TTS;
- continue listening after each response.

## Interruption and barge-in

The user must be able to interrupt the agent while it is speaking.

When the microphone detects that the user has started speaking during agent playback:

1. stop or cancel the current TTS playback;
2. discard queued audio from the interrupted response;
3. stop generating more of that response when possible;
4. listen to the new user utterance;
5. continue the conversation using the latest valid state.

Ignore late text or audio events from an interrupted response.

Do not let the agent continue talking over the user.

## OpenRouter

Use OpenRouter as the runtime language-model API.

Read the model from:

```env
OPENROUTER_MODEL=
```

Do not hardcode a model name into the application.

The user may choose a Gemini Flash model through OpenRouter.

Use the official OpenRouter-compatible API format.

Keep model-specific code isolated so the configured model can be changed without rewriting the application.

## Deepgram speech-to-text

Use Deepgram for live speech recognition.

Requirements:

- stream microphone audio to Deepgram;
- receive partial and final transcripts;
- use final or stable transcripts for conversation turns;
- handle connection errors;
- reconnect safely when practical;
- do not create duplicate user turns after reconnecting;
- keep interim transcripts separate from confirmed conversation history.

The Deepgram STT model must be configurable through:

```env
DEEPGRAM_STT_MODEL=
```

## Deepgram text-to-speech

Use Deepgram for speech generation.

Requirements:

- generate spoken audio from the model response;
- play the audio through the local Windows audio output;
- support interruption;
- stop playback immediately when barge-in is detected;
- avoid replaying audio from an interrupted response.

The Deepgram TTS voice or model must be configurable through:

```env
DEEPGRAM_TTS_MODEL=
```

Use a generic default only in `.env.example`, not as a hidden hardcoded dependency.

## Environment variables

Use a `.env` file locally.

Provide a `.env.example`.

At minimum support:

```env
DEEPGRAM_API_KEY=
DEEPGRAM_STT_MODEL=
DEEPGRAM_TTS_MODEL=

OPENROUTER_API_KEY=
OPENROUTER_MODEL=

GOOGLE_CALENDAR_ID=primary
GOOGLE_TIMEZONE=Europe/Madrid

BUSINESS_START_HOUR=09:00
BUSINESS_END_HOUR=17:00
APPOINTMENT_DURATION_MINUTES=30
```

Do not hardcode API keys.

Do not commit:

- `.env`;
- API keys;
- Google OAuth tokens;
- Google credentials;
- personal calendar data.

Provide an appropriate `.gitignore`.

## Receptionist behavior

The runtime agent is an inbound receptionist.

It should:

- greet the user;
- ask how it can help;
- determine whether the user needs customer support, an appointment, or a human representative;
- answer supported questions from the local knowledge base;
- help the user book an appointment;
- offer the future transfer path when needed;
- stay within the information available in the knowledge base and calendar.

The agent must not pretend to be human.

The agent must not invent company information.

The agent must not claim that an appointment was created unless Google Calendar returned success.

## Customer support

Customer-support answers must come from local knowledge files.

Support these file types:

- `.txt`;
- `.docx`;
- `.pdf`.

The codebase must include a folder such as:

```text
knowledge/
```

The user will place company documents in that folder.

At startup, the application should:

1. scan the folder;
2. load supported files;
3. extract their text;
4. keep the content in memory;
5. make the content searchable for support questions.

For the first version:

- do not use a database;
- do not use a vector database;
- do not call an external embedding service;
- use a simple local search or ranking approach;
- keep the implementation understandable;
- return only answers supported by the loaded documents.

When the answer cannot be verified:

- say that the information cannot be confirmed;
- offer the future human-transfer option;
- do not invent an answer;
- do not claim that a real transfer happened.

## Future transfer option

Include a transfer capability in the application design, but do not connect it to any real phone or human system.

The transfer component should:

- expose a clear function or interface;
- return a structured result;
- make it obvious that real transfer is not yet implemented;
- allow the conversation to tell the user that a human representative would be needed.

It must not falsely report that a transfer succeeded.

## Google Calendar

Use the user's primary Google Calendar for testing.

Use:

```env
GOOGLE_CALENDAR_ID=primary
```

Use the Google Calendar API with local desktop OAuth.

The first authorization may open a browser.

Store the local OAuth token outside source control.

Do not expose the token in logs.

## Appointment rules

Appointments must follow these rules:

- duration: 30 minutes;
- working days: Monday through Friday;
- business hours: 09:00 to 17:00;
- timezone: `Europe/Madrid`;
- calendar: primary Google Calendar.

Do not create appointments outside business hours.

Do not create appointments on Saturday or Sunday.

Do not double-book occupied time.

Check Google Calendar before offering or confirming a slot.

Resolve relative dates into exact dates.

Speak the full date and time when confirming.

Example:

```text
Tuesday, 14 July 2026 at 10:30 in Madrid time
```

## Information required for booking

Collect only:

- customer name;
- customer email address;
- requested date;
- requested time.

Do not require a phone number.

Keep this information in memory during the current application session.

Do not add permanent storage.

Closing the application may clear the conversation state.

The Google Calendar event itself should remain in Google Calendar after successful creation.

## Name spelling and verification

The agent must ask the user to spell the name letter by letter.

The user may use phonetic words such as Alpha, Bravo, Charlie, and Delta.

The application should:

- capture the spelled name;
- normalize it;
- read it back letter by letter;
- ask the user to confirm it;
- repeat the process when the user says it is incorrect.

Do not proceed until the name is confirmed.

## Email spelling and verification

The agent must ask the user to spell the email address letter by letter.

It must correctly handle spoken forms of:

- `at`;
- `dot`;
- hyphen;
- underscore;
- numbers;
- repeated letters.

Normalize the result into an email address.

Validate the email format in Python.

Do not rely only on the language model for email validation.

After capture, read the email back letter by letter.

Read punctuation explicitly.

Example:

```text
J for Juliett,
O for Oscar,
H for Hotel,
N for November,
at,
E for Echo,
X for X-ray,
A for Alpha,
M for Mike,
P for Papa,
L for Lima,
E for Echo,
dot com.
```

Ask the user to confirm the email.

Do not continue to booking until the email is valid and confirmed.

## Booking flow

The booking flow should be:

1. identify that the user wants an appointment;
2. collect the requested date and time;
3. collect and confirm the spelled name;
4. collect and confirm the spelled email address;
5. check Google Calendar availability;
6. offer the requested slot when available;
7. offer nearby available slots when it is unavailable;
8. read back the confirmed name, confirmed email, full date, exact time, Madrid timezone, and 30-minute duration;
9. ask for explicit final confirmation;
10. create the event only after confirmation;
11. report success only when Google Calendar confirms creation.

If event creation fails:

- say that the appointment was not confirmed;
- do not claim success;
- allow the user to retry or request the future human-transfer path.

## Calendar event details

A successful calendar event should include:

- a clear event title;
- customer name;
- customer email;
- appointment duration;
- timezone;
- a short note showing that it was created by the local voice-agent test.

Do not add unnecessary personal information.

## Conversation memory

Keep conversation state in Python memory only.

The application should remember during the current session:

- current intent;
- confirmed customer name;
- confirmed customer email;
- requested date and time;
- offered slots;
- booking confirmation state;
- whether support information was found;
- whether transfer was requested.

Do not add a database or persistent conversation history.

## Code quality

Use clear Python.

Use asynchronous code where required for microphone streaming, Deepgram streaming, model calls, TTS playback, and interruption handling.

Keep modules understandable.

Do not place the entire application in one oversized file when separating responsibilities makes the code easier to maintain.

Do not create unnecessary abstraction layers.

Add type hints where practical.

Handle errors explicitly.

Do not silently ignore failed API calls.

## Suggested project structure

Use a small, understandable project structure.

The exact filenames may adapt to the repository, but responsibilities should remain separated.

```text
voice-agent/
├── main.py
├── config.py
├── audio.py
├── deepgram_service.py
├── openrouter_service.py
├── calendar_service.py
├── knowledge_base.py
├── conversation.py
├── transfer.py
├── knowledge/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

This is still one local application.

Do not split it into microservices.

## Runtime prompt requirements

The runtime system prompt should tell the model to:

- behave as an inbound receptionist;
- use short, natural spoken responses;
- ask one question at a time;
- avoid markdown in spoken output;
- avoid long lists;
- never invent company information;
- use only retrieved knowledge for support answers;
- never claim calendar success without a successful tool result;
- confirm name and email carefully;
- ask for explicit confirmation before booking;
- use the full date and Madrid time;
- offer the future human-transfer path when information is unavailable;
- never claim a transfer occurred;
- not pretend to be human.

Keep the system prompt in a separate editable file or clearly separated section.

## Error handling

Handle at least:

- missing API keys;
- microphone initialization failure;
- speaker initialization failure;
- Deepgram STT connection failure;
- Deepgram TTS failure;
- OpenRouter request failure;
- Google OAuth failure;
- Google Calendar API failure;
- unsupported knowledge files;
- unreadable PDF or DOCX files;
- empty knowledge folder;
- invalid email;
- unclear spelled name;
- unavailable appointment slot;
- interruption during playback;
- clean shutdown.

Errors shown in the terminal should be understandable.

Do not expose secrets in errors.

## Testing

Add tests for logic that does not require live APIs.

At minimum test:

- business-day checks;
- 09:00 to 17:00 business-hour checks;
- 30-minute appointment duration;
- timezone handling for `Europe/Madrid`;
- occupied-slot rejection;
- alternative-slot selection;
- email normalization;
- email validation;
- phonetic-letter parsing;
- name confirmation state;
- email confirmation state;
- booking cannot happen without final confirmation;
- failed calendar creation cannot produce success wording;
- unsupported knowledge files are ignored safely;
- missing knowledge answer triggers the transfer option;
- interruption cancels pending playback state;
- conversation state resets correctly.

Keep live integration tests optional because they require real API keys and Google authorization.

## Documentation

Create a clear `README.md` that includes:

- supported Python version;
- Windows installation steps;
- virtual-environment setup;
- dependency installation;
- `.env` setup;
- Deepgram setup;
- OpenRouter setup;
- Google Calendar desktop OAuth setup;
- where to place PDF, DOCX, and TXT files;
- how to start the program;
- how to stop the program;
- known limitations;
- confirmation that phone-line transfer is not implemented;
- confirmation that outbound calling is not included.

Do not document features that do not exist.

## Implementation workflow

When asked to build or modify the project:

1. inspect the existing repository;
2. preserve working code;
3. identify the smallest necessary changes;
4. implement only the requested scope;
5. run the code where possible;
6. run tests;
7. fix errors introduced by the changes;
8. report what works;
9. report what remains unimplemented.

Do not stop after writing a plan.

Do not describe unfinished features as complete.

## Completion requirements

The first version is complete only when:

- it starts locally on Windows;
- it listens continuously;
- it transcribes speech through Deepgram;
- it sends completed turns to OpenRouter;
- it speaks responses through Deepgram;
- the user can interrupt playback;
- local PDF, DOCX, and TXT files can be loaded;
- support answers are grounded in those files;
- Google Calendar availability is checked;
- 30-minute appointments can be created;
- names and emails are spelled and confirmed;
- no database is used;
- Docker is not used;
- no phone provider is used;
- no outbound calling exists;
- the transfer capability remains a clear unimplemented option;
- setup instructions are documented;
- non-live tests pass.

## Final response format

After coding, report:

1. files created or changed;
2. features that work;
3. exact installation commands;
4. exact start command;
5. exact test command;
6. required environment variables;
7. required Google OAuth files;
8. known Windows audio limitations;
9. features intentionally not implemented;
10. any question that must be answered before the next requested feature.

Do not recommend unrelated technologies or future features unless the user asks.
