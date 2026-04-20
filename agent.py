#!/usr/bin/env python3
"""
SignalWire Appointment Agent
============================
A low-latency voice AI receptionist that searches and books appointments
against an external API.

Configuration:
- Model: gpt-oss-120b (via Groq) — fastest option on SignalWire
- TTS: ElevenLabs Rachel (eleven_turbo_v2_5)
- end_of_speech_timeout: 200ms
- temperature: 0.2, top_p: 0.8
- No speech fillers (measure raw latency)

Measured conversational latency: ~1.09s avg
"""

import os
import requests
from dotenv import load_dotenv
from signalwire_agents import AgentBase
from signalwire_agents.core.function_result import SwaigFunctionResult

load_dotenv()

# The default appointment API runs on Heroku's free tier and sleeps after
# 30 min of inactivity. First request after idle can take 5-10+ seconds.
# Warm it before testing:
#     curl https://apptsrv-b98a1588311b.herokuapp.com/search
APPOINTMENT_API_URL = os.getenv(
    "APPOINTMENT_API_URL",
    "https://apptsrv-b98a1588311b.herokuapp.com",
)


class AppointmentAgent(AgentBase):
    def __init__(self):
        super().__init__(
            name="appointment-agent",
            route="/appointment",
            host="0.0.0.0",
            port=int(os.getenv("PORT", "3000")),
            use_pom=True,
            record_call=True,
            record_format="wav",
            record_stereo=True,
        )

        # --- System Prompt ---
        self.prompt_add_section(
            "Role",
            body=(
                "You are a friendly appointment desk assistant. "
                "Your job is to help callers book, reschedule, or cancel appointments."
            ),
        )
        self.prompt_add_section(
            "Instructions",
            bullets=[
                "When a caller wants to book an appointment, use the search_appointments tool to check available time slots.",
                "Present the available options clearly to the caller.",
                "Once they select a time, use the book_appointment tool with the EXACT ISO 8601 datetime string from the search results that matches their selection. Do not modify or guess the datetime.",
                "Confirm the booking details back to the caller.",
                "Be natural, friendly, and concise. Keep your responses short and conversational.",
                "Always use the search_appointments tool before offering times to the caller.",
                "Don't make up available times.",
                "Do not ask clarifying questions. If the caller wants to book, immediately search for available slots.",
            ],
        )

        # --- LLM: OSS model via Groq (fastest on SignalWire) ---
        self.set_prompt_llm_params(
            model="gpt-oss-120b",
            temperature=0.2,
            top_p=0.8,
        )

        # --- Aggressive speech detection ---
        self.set_params({
            "end_of_speech_timeout": 200,
            "wait_for_user": False,
            "static_greeting": "Hello, this is the appointment desk. How can I help you today?",
            "static_greeting_no_barge": True,
        })

        # --- TTS: ElevenLabs Rachel ---
        self.add_language(
            name="English",
            code="en-US",
            voice="elevenlabs.rachel:eleven_turbo_v2_5",
        )

    @AgentBase.tool(
        name="search_appointments",
        description=(
            "Search for available appointment time slots. Use this when the caller "
            "wants to book an appointment or needs to know what times are available. "
            "After calling this tool, present the available times to the user in a "
            "natural, conversational way."
        ),
        parameters={},
    )
    def search_appointments(self, args, raw_data):
        """Search available appointment slots from the appointment server."""
        try:
            response = requests.get(f"{APPOINTMENT_API_URL}/search", timeout=10)
            if response.status_code == 200:
                result = response.json()
                appointments = result.get("appointments", [])
                if not appointments:
                    return SwaigFunctionResult("No appointments are currently available.")

                from datetime import datetime

                times = []
                for apt in appointments:
                    iso = apt["datetime"]
                    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                    formatted = dt.strftime("%A, %B %d at %I:%M %p")
                    times.append(f"{formatted} (datetime: {iso})")

                return SwaigFunctionResult(
                    f"Available slots: {'; '.join(times)}. Present these to the caller "
                    f"and when they choose one, use the exact datetime value in parentheses for booking."
                )
            else:
                return SwaigFunctionResult(
                    "I'm having trouble accessing the schedule right now."
                )
        except Exception as e:
            return SwaigFunctionResult(
                f"I encountered an error checking availability: {str(e)}"
            )

    @AgentBase.tool(
        name="book_appointment",
        description=(
            "Book an appointment at the specified date and time. Use this after the "
            "caller has selected a specific time slot. Always confirm the details "
            "with the caller before calling this function."
        ),
        parameters={
            "datetime": {
                "type": "string",
                "description": 'The date and time for the appointment in ISO 8601 format (e.g., "2025-11-05T14:00:00Z")',
            },
        },
    )
    def book_appointment(self, args, raw_data):
        """Book an appointment via the appointment server.

        The caller's phone number is read directly from SignalWire's telecom
        metadata (raw_data) — no need for the LLM to pass it as a parameter.
        """
        dt_str = args.get("datetime", "")
        caller_phone = (raw_data or {}).get("caller_id_num", "")

        try:
            response = requests.post(
                f"{APPOINTMENT_API_URL}/book",
                json={
                    "caller_phone": caller_phone,
                    "datetime": dt_str,
                    "action": "book",
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code == 200:
                from datetime import datetime

                try:
                    appointment_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    formatted = appointment_dt.strftime("%A, %B %d at %I:%M %p")
                except ValueError:
                    formatted = dt_str
                return SwaigFunctionResult(
                    f"Perfect! I've booked your appointment for {formatted}. Is there anything else I can help you with?"
                )
            else:
                return SwaigFunctionResult(
                    "I'm sorry, I wasn't able to book that appointment. Could we try a different time?"
                )
        except Exception as e:
            return SwaigFunctionResult(
                f"I encountered an error while booking: {str(e)}. Please try again."
            )


if __name__ == "__main__":
    agent = AppointmentAgent()
    print("=" * 60)
    print("SignalWire Appointment Agent")
    print("=" * 60)
    print(f"Model:            gpt-oss-120b (via Groq)")
    print(f"Voice:            ElevenLabs Rachel (eleven_turbo_v2_5)")
    print(f"temperature:      0.2")
    print(f"top_p:            0.8")
    print(f"end_of_speech:    200ms")
    print(f"fillers:          none")
    print(f"URL:              http://localhost:{os.getenv('PORT', '3000')}/appointment")
    username, password, source = agent.get_basic_auth_credentials(include_source=True)
    print(f"Auth:             {username}:{password}  (source: {source})")
    print("=" * 60)
    agent.run()
