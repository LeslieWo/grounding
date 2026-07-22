# data/ — personal data, never committed

The production backend **does not use this directory**. It is stateless: photos and memory
cards live on the client (the phone), the client sends the cards up each turn, and the server
forgets everything as soon as the turn ends.

This directory is only used when **running the local Streamlit dev app** (`app.py`):

```
data/
├── memories.json     # memory cards (local)
├── photos/           # original photos (local)
├── display/          # 800px display versions (local)
└── config.json       # trusted contact (local)
```

`.gitignore` keeps the whole `data/` directory out of the repo, allowing only this README
and `memories.example.json` through.

## What a memory card looks like

See `memories.example.json`. Fields:

| Field | Meaning |
|---|---|
| `id` | 8 hex chars; the photo filename uses it too |
| `title` | a warm one-line title |
| `where` / `when` / `who` / `what_happened` | things only the person knows; if the vision model can't tell, it writes "(please fill in)" |
| `see` / `hear` / `touch` / `smell_taste` | the sensory axes — the main handholds for grounding |
| `weather_temp` / `food` / `emotion` | supplementary axes |
| `grounding_questions` | 4-6 gentle questions, asked one at a time |
| `image_path` | relative photo path (local use only; the phone doesn't use this field) |

**The agent only ever reads this text. It never looks at photo pixels.** That is exactly why
the photos never need to leave the device. The single moment a photo is seen is card creation
(the vision model looks once to draft the card; the photo is never written to disk).
