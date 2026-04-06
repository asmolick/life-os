import os
import random
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import anthropic

app = Flask(__name__)

# Config from environment variables
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_NUMBER = os.environ.get('TWILIO_NUMBER', '+15186174724')
AARON_NUMBER = os.environ.get('AARON_NUMBER', '+12038561259')

AARON_PROFILE = """You are texting Aaron Smolick, 50, Fairfield CT. Executive Director at JPMorgan Chase.
Married with two kids: Tyler (17, graduating 2026) and Casey (15, varsity lacrosse, graduating HS 2029).
4-hour daily commute to NYC. Lost father at 15 to heart attack. Health: 226 lbs goal 190, high cardiac risk.
Takes Rosuvastatin nightly. Bad knee. Net worth $2.6M. Plays D1 lacrosse at UNH.
IMPORTANT: SMS only. Keep replies to 2-3 sentences max. No bullet points. Conversational."""

AGENTS = {
    'white': {'name': 'AI White', 'system': 'You are AI White, brutal no-excuses health coach via SMS. Aaron is 226 lbs, father died at 50, Aaron IS 50 and HIGH RISK. Be savage, mock excuses, short punchy texts. ' + AARON_PROFILE},
    'buffett': {'name': 'AI Buffett', 'system': 'You are AI Buffett, wise financial advisor via SMS. Warren Buffett energy. Short punchy actionable texts. ' + AARON_PROFILE},
    'dimon': {'name': 'AI Dimon', 'system': 'You are AI Dimon, career strategist via SMS. Jamie Dimon directness. MD-focused. Short and direct. ' + AARON_PROFILE},
    'freud': {'name': 'AI Freud', 'system': 'You are AI Freud, mental wellness guide via SMS. Calm, probing. Ask ONE deep question per text. ' + AARON_PROFILE},
    'jobs': {'name': 'AI Jobs', 'system': 'You are AI Jobs, learning coach via SMS. Steve Jobs vision. Short inspiring texts. ' + AARON_PROFILE},
    'ruth': {'name': 'AI Ruth', 'system': 'You are AI Ruth, relationship coach via SMS. Help Aaron be present with Tyler and Casey. Short warm texts. ' + AARON_PROFILE},
    'rogan': {'name': 'AI Rogan', 'system': 'You are AI Rogan, productivity coach via SMS. Joe Rogan raw energy. Tell him to get off social media. Short fire texts. ' + AARON_PROFILE},
    'stewart': {'name': 'AI Stewart', 'system': 'You are AI Stewart, home and life guide via SMS. Martha Stewart warmth. Short helpful texts. ' + AARON_PROFILE},
    'robbins': {'name': 'AI Robbins', 'system': 'You are AI Robbins, Tony Robbins motivator via SMS. Pure fire. Make Aaron take action NOW. 1-2 sentences max. ' + AARON_PROFILE},
    'doc': {'name': 'AI Doc', 'system': 'You are AI Doc, doctor via SMS. HIGH cardiac risk. Remind about Rosuvastatin, appointments, weight. Short direct texts. ' + AARON_PROFILE},
    'pa': {'name': 'AI PA', 'system': 'You are AI PA, personal assistant via SMS. Organized helpful briefings. Short and scannable. ' + AARON_PROFILE},
}

# Simple in-memory storage
conversation_history = {}
active_agent = {}

AGENT_SHORTCUTS = {
    'white': 'white', 'arnold': 'white', 'health': 'white',
    'buffett': 'buffett', 'finance': 'buffett', 'money': 'buffett',
    'dimon': 'dimon', 'career': 'dimon',
    'freud': 'freud', 'mental': 'freud',
    'jobs': 'jobs', 'learn': 'jobs',
    'ruth': 'ruth', 'family': 'ruth',
    'rogan': 'rogan', 'productivity': 'rogan',
    'stewart': 'stewart', 'home': 'stewart',
    'robbins': 'robbins', 'motivate': 'robbins',
    'doc': 'doc', 'doctor': 'doc',
    'pa': 'pa', 'assistant': 'pa',
}

def get_history(phone, agent_id):
    if phone not in conversation_history:
        conversation_history[phone] = {}
    if agent_id not in conversation_history[phone]:
        conversation_history[phone][agent_id] = []
    return conversation_history[phone][agent_id]

def get_ai_response(agent_id, user_message, phone):
    agent = AGENTS.get(agent_id, AGENTS['rogan'])
    history = get_history(phone, agent_id)
    history.append({"role": "user", "content": user_message})
    if len(history) > 20:
        history = history[-20:]
        conversation_history[phone][agent_id] = history

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=agent['system'],
        messages=history
    )
    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    return reply

@app.route('/sms', methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get('Body', '').strip()
    from_number = request.form.get('From', '')
    resp = MessagingResponse()

    lower_msg = incoming_msg.lower().strip()

    # Help command
    if lower_msg in ['help', 'agents', 'list']:
        resp.message("Your agents — reply with name to switch:\nWHITE - Health\nBUFFETT - Finance\nDIMON - Career\nFREUD - Mental\nJOBS - Learning\nRUTH - Family\nROGAN - Productivity\nSTEWART - Home\nROBBINS - Motivation\nDOC - Health\nPA - Assistant")
        return str(resp)

    # Agent switch
    if lower_msg in AGENT_SHORTCUTS:
        new_agent = AGENT_SHORTCUTS[lower_msg]
        active_agent[from_number] = new_agent
        agent_name = AGENTS[new_agent]['name']
        resp.message(f"Switched to {agent_name}. What's on your mind, Aaron?")
        return str(resp)

    # Get current agent
    current_agent_id = active_agent.get(from_number, 'rogan')

    try:
        ai_reply = get_ai_response(current_agent_id, incoming_msg, from_number)
        agent_name = AGENTS[current_agent_id]['name']
        resp.message(f"[{agent_name}]\n{ai_reply}")
    except Exception as e:
        resp.message(f"Connection issue. Try again. (Error: {str(e)[:50]})")

    return str(resp)

@app.route('/')
def home():
    return "Aaron's Life OS is running! Text +15186174724 to talk to your agents.", 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
