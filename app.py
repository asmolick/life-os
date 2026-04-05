import os
import json
import anthropic
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

app = Flask(__name__)

# Config from environment variables
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = os.environ.get('TWILIO_NUMBER', '+18554184935')
AARON_NUMBER = os.environ.get('AARON_NUMBER', '+12038561259')

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

AARON_PROFILE = """You are texting Aaron Smolick, 50 years old, Fairfield CT.
Executive Director at JPMorgan Chase leading AI transformation for 2,300-person Data & Analytics org.
Married to a registered dietitian. Two kids: Tyler (17, graduating 2026, wants environmental engineering)
and Casey (15, varsity lacrosse/field hockey, wants to play college lacrosse, graduating HS 2029).
4-hour daily round-trip commute to NYC. Lost his father at 15 to a heart attack right in front of him.
Health: 226 lbs (goal 190 by summer), HbA1C 6.2, HDL 29, takes Rosuvastatin nightly. Bad knee, can't run.
Father died of heart attack at 50 — Aaron is HIGH RISK. Drinks too much, too many carbs.
Finances: ~$2.6M net worth, $850K home, $140K left on mortgage at 2.625%.
Hobbies: boating, fishing, cooking/grilling, exploring cities. Influencers: Joe Rogan, Dana White, Steve Jobs, Elon Musk.
Played D1 lacrosse at UNH. Writing a 100-question AI transformation book (48 questions done).
Glass-half-empty person who wants to be glass-half-full. Doesn't know what makes him happy.
Action before readiness is his mantra. Goal: live better, healthier, more fulfilled life into his 80s.
IMPORTANT: You are texting via SMS. Keep responses SHORT — 2-4 sentences max. Conversational. No bullet points."""

AGENTS = {
    'white': {
        'name': 'AI White',
        'system': f'You are AI White, Aaron\'s brutal no-excuses health coach via SMS. Aaron is 226 lbs, father died of heart attack at 50, Aaron is NOW 50 and HIGH RISK. Be savage. Mock excuses. Short punchy texts. {AARON_PROFILE}'
    },
    'buffett': {
        'name': 'AI Buffett',
        'system': f'You are AI Buffett, Aaron\'s wise financial advisor texting via SMS. Warren Buffett energy. Short, punchy, actionable. {AARON_PROFILE}'
    },
    'dimon': {
        'name': 'AI Dimon',
        'system': f'You are AI Dimon, Aaron\'s career strategist texting via SMS. Jamie Dimon directness. MD-focused. Short and direct. {AARON_PROFILE}'
    },
    'freud': {
        'name': 'AI Freud',
        'system': f'You are AI Freud, Aaron\'s mental wellness guide texting via SMS. Calm, probing. Ask ONE deep question. Short texts only. {AARON_PROFILE}'
    },
    'jobs': {
        'name': 'AI Jobs',
        'system': f'You are AI Jobs, Aaron\'s learning coach texting via SMS. Steve Jobs vision. Short inspiring texts. {AARON_PROFILE}'
    },
    'ruth': {
        'name': 'AI Ruth',
        'system': f'You are AI Ruth, Aaron\'s relationship coach texting via SMS. Help him be present with Tyler and Casey. Short warm texts. {AARON_PROFILE}'
    },
    'rogan': {
        'name': 'AI Rogan',
        'system': f'You are AI Rogan, Aaron\'s productivity coach texting via SMS. Joe Rogan raw energy. Tell him to get off social media. Short fire texts. {AARON_PROFILE}'
    },
    'stewart': {
        'name': 'AI Stewart',
        'system': f'You are AI Stewart, Aaron\'s home and life guide texting via SMS. Martha Stewart practical warmth. Short helpful texts. {AARON_PROFILE}'
    },
    'robbins': {
        'name': 'AI Robbins',
        'system': f'You are AI Robbins, Tony Robbins-style motivator texting via SMS. Pure fire. Make Aaron take action NOW. 1-2 sentences max. {AARON_PROFILE}'
    },
    'doc': {
        'name': 'AI Doc',
        'system': f'You are AI Doc, Aaron\'s doctor texting via SMS. He has HIGH cardiac risk — father died at 50. Remind about Rosuvastatin, appointments, weight. Short direct texts. {AARON_PROFILE}'
    },
    'pa': {
        'name': 'AI PA',
        'system': f'You are AI PA, Aaron\'s personal assistant texting via SMS. Organized, helpful briefings. Short and scannable. {AARON_PROFILE}'
    },
    'freud_therapy': {
        'name': 'AI Therapy',
        'system': f'You are AI Therapy, Aaron\'s therapist texting via SMS. Ask one deep probing question. If no reply in 30 min, follow up. Short texts. {AARON_PROFILE}'
    },
}

# Conversation history stored in memory (resets on server restart)
# Format: { phone_number: { agent_id: [messages] } }
conversation_history = {}

# Track which agent Aaron is currently talking to
active_agent = {}

def get_history(phone, agent_id):
    if phone not in conversation_history:
        conversation_history[phone] = {}
    if agent_id not in conversation_history[phone]:
        conversation_history[phone][agent_id] = []
    return conversation_history[phone][agent_id]

def add_to_history(phone, agent_id, role, content):
    history = get_history(phone, agent_id)
    history.append({"role": role, "content": content})
    # Keep last 20 messages only
    if len(history) > 20:
        conversation_history[phone][agent_id] = history[-20:]

def get_ai_response(agent_id, user_message, phone):
    agent = AGENTS.get(agent_id, AGENTS['rogan'])
    add_to_history(phone, agent_id, "user", user_message)
    history = get_history(phone, agent_id)

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=agent['system'],
        messages=history
    )
    reply = response.content[0].text
    add_to_history(phone, agent_id, "assistant", reply)
    return reply

def send_sms(to_number, message, agent_name="Life OS"):
    full_message = f"[{agent_name}]\n{message}"
    twilio_client.messages.create(
        body=full_message,
        from_=TWILIO_NUMBER,
        to=to_number
    )

def get_current_agent(phone):
    return active_agent.get(phone, 'rogan')

def set_active_agent(phone, agent_id):
    active_agent[phone] = agent_id

@app.route('/sms', methods=['POST'])
def sms_reply():
    """Handle incoming SMS from Aaron"""
    incoming_msg = request.form.get('Body', '').strip()
    from_number = request.form.get('From', '')

    resp = MessagingResponse()

    # Check if Aaron is switching agents
    agent_switch = {
        'white': 'white', 'arnold': 'white', 'health': 'white',
        'buffett': 'buffett', 'finance': 'buffett', 'money': 'buffett',
        'dimon': 'dimon', 'career': 'dimon',
        'freud': 'freud', 'mental': 'freud', 'wellness': 'freud',
        'jobs': 'jobs', 'learn': 'jobs',
        'ruth': 'ruth', 'family': 'ruth',
        'rogan': 'rogan', 'productivity': 'rogan',
        'stewart': 'stewart', 'home': 'stewart',
        'robbins': 'robbins', 'motivate': 'robbins',
        'doc': 'doc', 'doctor': 'doc', 'health check': 'doc',
        'pa': 'pa', 'assistant': 'pa',
        'therapy': 'freud_therapy',
    }

    lower_msg = incoming_msg.lower()

    # Handle agent switch command
    if lower_msg in agent_switch:
        new_agent = agent_switch[lower_msg]
        set_active_agent(from_number, new_agent)
        agent_name = AGENTS[new_agent]['name']
        resp.message(f"Switched to {agent_name}. What's on your mind?")
        return str(resp)

    # Handle help command
    if lower_msg in ['help', 'agents', 'list']:
        resp.message("Your agents:\nWHITE - Health\nBUFFETT - Finance\nDIMON - Career\nFREUD - Mental\nJOBS - Learning\nRUTH - Family\nROGAN - Productivity\nSTEWART - Home\nROBBINS - Motivation\nDOC - Health Check\nPA - Assistant\n\nReply agent name to switch.")
        return str(resp)

    # Get current agent and respond
    current_agent_id = get_current_agent(from_number)

    try:
        ai_reply = get_ai_response(current_agent_id, incoming_msg, from_number)
        agent_name = AGENTS[current_agent_id]['name']
        resp.message(f"[{agent_name}]\n{ai_reply}")
    except Exception as e:
        resp.message("Connection issue. Try again in a moment.")

    return str(resp)

@app.route('/send-scheduled', methods=['GET'])
def send_scheduled_manually():
    """Manually trigger a scheduled message for testing"""
    send_morning_brief()
    return "Sent!", 200

@app.route('/')
def home():
    return "Aaron's Life OS is running. Text your Twilio number to talk to your agents.", 200

# ============================================================
# SCHEDULED MESSAGES
# ============================================================

ET = pytz.timezone('America/New_York')

def send_morning_brief():
    now = datetime.now(ET)
    day = now.strftime('%A')
    send_sms(AARON_NUMBER,
        f"Good morning Aaron. {day} — make it count. Reply HELP for agent list, or just reply to talk to AI Rogan.",
        "AI PA")

def send_health_challenge():
    messages = [
        "226 lbs. 190 is the goal. Today: 3 sets of 10 chair squats every hour at work. No excuses.",
        "Your HDL is 29. That's dangerously low. Today: drink 8 glasses of water. That's it. Do it.",
        "Your father died at 50. You ARE 50. Today's challenge: 20 minute walk at lunch. No gym needed.",
        "Man boobs don't disappear on their own Aaron. 15 push-ups right now before you read the next text.",
        "Pre-diabetic with a 6.2 HbA1C. Skip the bread at lunch today. One meal. You can do it.",
    ]
    import random
    send_sms(AARON_NUMBER, random.choice(messages), "AI White")

def send_motivation():
    messages = [
        "Tyler has 18 months left under your roof. Casey is watching everything you do. What story are you writing today?",
        "You have $2.6M, a great family, and a job building the future. Stop scrolling. START DOING.",
        "The only difference between who you are and who you want to be is what you do TODAY.",
        "Your commute is 4 hours. That's 4 hours of podcasts, audiobooks, and big thinking. Use it.",
        "Action before readiness. You said it yourself. What action are you avoiding right now?",
    ]
    import random
    send_sms(AARON_NUMBER, random.choice(messages), "AI Robbins")

def send_deep_question():
    questions = [
        "Aaron — when was the last time you did something just because YOU wanted to, not because it needed doing?",
        "What's one thing you've been meaning to say to Tyler or Casey that you keep putting off?",
        "If your father were alive today, what do you think he'd be most proud of? What would he push you to do more of?",
        "On a scale of 1-10, how present were you with your family this week? What would a 10 have looked like?",
        "What's one thing you're carrying right now that you haven't told anyone about?",
    ]
    import random
    send_sms(AARON_NUMBER, random.choice(questions), "AI Freud")

def send_medication_reminder():
    hour = datetime.now(ET).hour
    if hour == 20:  # 8pm
        send_sms(AARON_NUMBER,
            "ROSUVASTATIN. Take it right now. This is reminder 1 of 3. Your father died of a heart attack at 50. You are 50. Take the pill.",
            "AI Doc")
    elif hour == 20 and datetime.now(ET).minute >= 15:
        send_sms(AARON_NUMBER,
            "Still waiting. Did you take your statin? Don't make me send the third reminder.",
            "AI Doc")

def send_evening_motivation():
    send_sms(AARON_NUMBER,
        "End the day strong Aaron. One thing you're grateful for. Say it out loud before you sleep.",
        "AI Robbins")

def send_stretch_reminder():
    send_sms(AARON_NUMBER,
        "7:30pm — stretch time. 5 minutes. Hip flexors, hamstrings, shoulders. Your body carried you all day. Give it something back.",
        "AI PT")

def send_sunday_mom_reminder():
    send_sms(AARON_NUMBER,
        "Sunday reminder: Text your mom. She's in Florida and feels out of touch. Tell her 3 things that happened this week. Takes 2 minutes.",
        "AI Dad")

def send_weekly_weigh_in():
    send_sms(AARON_NUMBER,
        "Sunday weigh-in. Step on the scale RIGHT NOW and reply with your weight. If I don't hear back in 15 minutes, I'm going to get very annoying.",
        "AI White")

def send_career_nudge():
    nudges = [
        "One LinkedIn action today: comment on a senior leader's post at JPMC. MD visibility starts with being seen.",
        "Have you worked on your AI book this week? One paragraph today. The book writes itself one question at a time.",
        "Who's one person at JPMC you should have coffee with this week to build MD momentum? Text them today.",
        "Speaking opportunity check: any conferences or panels you could submit to speak at in the next 90 days?",
    ]
    import random
    send_sms(AARON_NUMBER, random.choice(nudges), "AI Dimon")

def setup_scheduler():
    scheduler = BackgroundScheduler(timezone=ET)

    # Weekday morning brief — 6:30am
    scheduler.add_job(send_morning_brief, 'cron', day_of_week='mon-fri', hour=6, minute=30)

    # Health challenge — 7:30am daily
    scheduler.add_job(send_health_challenge, 'cron', hour=7, minute=30)

    # Morning motivation — 8:00am daily
    scheduler.add_job(send_motivation, 'cron', hour=8, minute=0)

    # Career nudge — 9:00am weekdays
    scheduler.add_job(send_career_nudge, 'cron', day_of_week='mon-fri', hour=9, minute=0)

    # Midday motivation — 12:30pm daily
    scheduler.add_job(send_motivation, 'cron', hour=12, minute=30)

    # Deep question from Freud — 2:00pm daily
    scheduler.add_job(send_deep_question, 'cron', hour=14, minute=0)

    # Stretch reminder — 7:30pm daily
    scheduler.add_job(send_stretch_reminder, 'cron', hour=19, minute=30)

    # Medication reminder — 8:00pm daily
    scheduler.add_job(send_medication_reminder, 'cron', hour=20, minute=0)

    # Evening motivation — 9:00pm daily
    scheduler.add_job(send_evening_motivation, 'cron', hour=21, minute=0)

    # Sunday mom reminder — 9:00am Sunday
    scheduler.add_job(send_sunday_mom_reminder, 'cron', day_of_week='sun', hour=9, minute=0)

    # Sunday weigh-in — 8:00am Sunday
    scheduler.add_job(send_weekly_weigh_in, 'cron', day_of_week='sun', hour=8, minute=0)

    scheduler.start()
    return scheduler

scheduler = setup_scheduler()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
