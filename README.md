# SignalWire Appointment Agent

Low-latency voice AI receptionist built on the [SignalWire Agents SDK](https://github.com/signalwire/signalwire-agents-python). The agent answers inbound calls, searches an external appointment API, and books a slot the caller selects.

Produced as the best-performing configuration from a cross-platform voice AI latency benchmark against LiveKit and Vapi.

## Measured Performance

| Metric                | Avg    |
|-----------------------|--------|
| Conversational turn   | 1.09s  |
| Tool turn (w/ API)    | 2.01s  |
| Overall               | 1.68s  |

Measured via waveform analysis (human stops speaking → AI starts speaking). 3 calls, 9 turns, stereo recordings.

## Configuration

| Parameter            | Value                              |
|----------------------|------------------------------------|
| LLM                  | `gpt-oss-120b` (via Groq)          |
| TTS                  | `elevenlabs.rachel:eleven_turbo_v2_5` |
| `temperature`        | 0.2                                |
| `top_p`              | 0.8                                |
| `end_of_speech_timeout` | 200ms                           |
| `wait_for_user`      | `False`                            |
| Static greeting      | Enabled, no barge-in               |
| Speech fillers       | None                               |

## Setup

```bash
git clone <repo-url>
cd signalwire-appointment-agent
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
python agent.py
```

The agent serves SWML at `http://localhost:3000/appointment`. Point a SignalWire phone number's handler at this URL (via a public tunnel like ngrok for local development).

## External API

The agent calls two endpoints on a mock appointment server:

- `GET /search` — returns available slots
- `POST /book` — books a slot

Override via `APPOINTMENT_API_URL` in `.env` to point at your own backend.

### ⚠️ Cold Start Warning

The default appointment API is hosted on Heroku's free tier and **sleeps after 30 minutes of inactivity**. The first request after idle can take 5–10+ seconds, which will dominate your first tool-call latency.

**Warm the API before testing:**

```bash
curl https://apptsrv-b98a1588311b.herokuapp.com/search
```

Run this once before placing test calls. Subsequent requests return in ~200ms. If you're running your own backend, this doesn't apply.
