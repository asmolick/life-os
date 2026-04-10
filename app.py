import os
import json
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
 
app = Flask(__name__)
 
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
TWILIO_NUMBER = os.environ.get('TWILIO_NUMBER', '+15186174724')
AARON_NUMBER = os.environ.get('AARON_NUMBER', '+12038561259')
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')
 
AARON_PROFILE = """You are texting Aaron Smolick, 50, Fairfield CT. Executive Director at JPMorgan Chase leading AI transformation.
Married to a registered dietitian. Two kids: Tyler (17, graduating 2026, wants environmental engineering) and Casey (15, varsity lacrosse, graduating HS 2029).
4-hour daily commute to NYC. Lost father at 15 to heart attack right in front of him. Health: 226 lbs goal 190, HIGH cardiac risk.
Takes Rosuvastatin nightly. Bad knee no running. Net worth $2.6M. Played D1 lacrosse at UNH.
Writing 100-question AI transformation book. Glass half empty wants to be half full.
IMPORTANT: SMS/WhatsApp only. Keep replies 2-3 sentences max. No bullet points. Conversational and direct."""
 
AGENTS = {
    'white': {'name': 'AI White', 'system': 'You are AI White, brutal no-excuses health coach via WhatsApp. Aaron is 226 lbs, father died at 50, Aaron IS 50 and HIGH RISK. Be savage, mock excuses, short punchy texts. ' + AARON_PROFILE},
    'buffett': {'name': 'AI Buffett', 'system': 'You are AI Buffett, wise financial advisor via WhatsApp. Warren Buffett energy. Short punchy actionable texts. When given search results, summarize the most important financial insight in 2-3 sentences. ' + AARON_PROFILE},
    'dimon': {'name': 'AI Dimon', 'system': 'You are AI Dimon, career strategist via WhatsApp. Jamie Dimon directness. MD-focused. Short and direct. ' + AARON_PROFILE},
    'freud': {'name': 'AI Freud', 'system': 'You are AI Freud, mental wellness guide via WhatsApp. Calm, probing. Ask ONE deep question per text. ' + AARON_PROFILE},
    'jobs': {'name': 'AI Jobs', 'system': 'You are AI Jobs, learning coach via WhatsApp. Steve Jobs vision. When given search results about AI/tech news, summarize the most exciting development in 2-3 sentences and tell Aaron why it matters. ' + AARON_PROFILE},
    'ruth': {'name': 'AI Ruth', 'system': 'You are AI Ruth, relationship coach via WhatsApp. Help Aaron be present with Tyler and Casey. Short warm texts. ' + AARON_PROFILE},
    'rogan': {'name': 'AI Rogan', 'system': 'You are AI Rogan, productivity coach via WhatsApp. Joe Rogan raw energy. Tell him to get off social media. Short fire texts. ' + AARON_PROFILE},
    'stewart': {'name': 'AI Stewart', 'system': 'You are AI Stewart, home and life guide via WhatsApp. Martha Stewart warmth. When given search results about local events or recipes, give Aaron the best option in 2-3 sentences. ' + AARON_PROFILE},
    'robbins': {'name': 'AI Robbins', 'system': 'You are AI Robbins, Tony Robbins motivator via WhatsApp. Pure fire. Make Aaron take action NOW. 1-2 sentences max. ' + AARON_PROFILE},
    'doc': {'name': 'AI Doc', 'system': 'You are AI Doc, proactive doctor via WhatsApp. Aaron has HIGH cardiac risk. Remind about Rosuvastatin, appointments, weight goal 190. Short direct texts. ' + AARON_PROFILE},
    'pa': {'name': 'AI PA', 'system': 'You are AI PA, personal assistant via WhatsApp. When given search results, summarize the most relevant info for Aaron in 2-3 sentences. ' + AARON_PROFILE},
    'shark': {'name': 'AI Shark', 'system': 'You are AI Shark, side hustle advisor via WhatsApp. Help Aaron build wooden signs business, lacrosse lessons, fishing tours, publish AI book. Short entrepreneurial texts. ' + AARON_PROFILE},
    'scout': {'name': 'AI Scout', 'system': 'You are AI Scout, sports and events tracker via WhatsApp. When given search results about sports schedules or concerts, give Aaron the key dates in 2-3 sentences. ' + AARON_PROFILE},
    'realty': {'name': 'AI Realty', 'system': 'You are AI Realty, real estate advisor via WhatsApp. When given search results about properties, highlight the best opportunity for Aaron in 2-3 sentences. ' + AARON_PROFILE},
}
 
AGENT_SHORTCUTS = {
    'white': 'white', 'arnold': 'white', 'health': 'white',
    'buffett': 'buffett', 'finance': 'buffett', 'money': 'buffett',
    'dimon': 'dimon', 'career': 'dimon',
    'freud': 'freud', 'mental': 'freud',
    'jobs': 'jobs', 'learn': 'jobs',
    'ruth': 'ruth', 'family': 'ruth',
    'rogan': 'rogan', 'productivity': 'rogan',
    'stewart': 'stewart', 'home': 'stewart',
    'robbins': 'robbins', 'motivate': 'robbins', 'fire': 'robbins',
    'doc': 'doc', 'doctor': 'doc',
    'pa': 'pa', 'assistant': 'pa',
    'shark': 'shark', 'hustle': 'shark',
    'scout': 'scout', 'sports': 'scout',
    'realty': 'realty', 'homes': 'realty',
}
 
# Search triggers — if message contains these words, search the web first
SEARCH_TRIGGERS = [
    'news', 'latest', 'today', 'current', 'price', 'stock', 'market',
    'weather', 'game', 'score', 'schedule', 'concert', 'ticket',
    'search', 'find', 'look up', 'what is', "what's", 'who is',
    'when is', 'where is', 'how much', 'listings', 'property',
    'fishing', 'tide', 'wind', 'forecast', 'event', 'happening'
]
 
conversation_history = {}
active_agent = {}
 
def should_search(message):
    lower = message.lower()
    return any(trigger in lower for trigger in SEARCH_TRIGGERS)
 
def tavily_search(query):
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3
            },
            timeout=10
        )
        data = response.json()
        results = data.get('results', [])
        if not results:
            return None
        summary = []
        for r in results[:3]:
            title = r.get('title', '')
            content = r.get('content', '')[:200]
            summary.append(f"{title}: {content}")
        return "\n\n".join(summary)
    except Exception as e:
        return None
 
def get_history(phone, agent_id):
    if phone not in conversation_history:
        conversation_history[phone] = {}
    if agent_id not in conversation_history[phone]:
        conversation_history[phone][agent_id] = []
    return conversation_history[phone][agent_id]
 
def get_ai_response(agent_id, user_message, phone, search_context=None):
    agent = AGENTS.get(agent_id, AGENTS['rogan'])
    history = get_history(phone, agent_id)
 
    # Add search context to message if available
    if search_context:
        enhanced_message = f"{user_message}\n\n[Live search results]:\n{search_context}"
    else:
        enhanced_message = user_message
 
    history.append({"role": "user", "content": enhanced_message})
    if len(history) > 20:
        history = history[-20:]
        conversation_history[phone][agent_id] = history
 
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 250,
            "system": agent['system'],
            "messages": history
        },
        timeout=25
    )
 
    data = response.json()
    reply = data['content'][0]['text']
    # Store clean message in history (without search context)
    history[-1] = {"role": "user", "content": user_message}
    history.append({"role": "assistant", "content": reply})
    return reply
 
def build_search_query(agent_id, message):
    """Build a good search query based on agent and message"""
    agent_context = {
        'jobs': 'AI artificial intelligence news',
        'buffett': 'stock market finance news',
        'scout': 'sports schedule Fairfield CT',
        'stewart': 'events Fairfield CT',
        'realty': 'real estate listings',
        'pa': 'news',
        'white': 'health fitness',
    }
    base = agent_context.get(agent_id, '')
    return f"{base} {message}".strip()
 
@app.route('/sms', methods=['POST'])
def sms_reply():
    incoming_msg = request.form.get('Body', '').strip()
    from_number = request.form.get('From', '')
    resp = MessagingResponse()
 
    if not incoming_msg:
        resp.message("Hey Aaron — text me anything or say HELP for agent list.")
        return str(resp)
 
    lower_msg = incoming_msg.lower().strip()
 
    if lower_msg in ['help', 'agents', 'list']:
        resp.message("Your agents — reply name to switch:\n\nWHITE - Health\nBUFFETT - Finance\nDIMON - Career\nFREUD - Mental\nJOBS - AI News\nRUTH - Family\nROGAN - Productivity\nSTEWART - Home/Events\nROBBINS - Motivation\nDOC - Health Check\nPA - Assistant\nSHARK - Side Hustle\nSCOUT - Sports/Concerts\nREALTY - Real Estate")
        return str(resp)
 
    if lower_msg in AGENT_SHORTCUTS:
        new_agent = AGENT_SHORTCUTS[lower_msg]
        active_agent[from_number] = new_agent
        agent_name = AGENTS[new_agent]['name']
        resp.message(f"Switched to {agent_name}. What's on your mind, Aaron?")
        return str(resp)
 
    current_agent_id = active_agent.get(from_number, 'rogan')
 
    try:
        # Search the web if needed
        search_context = None
        if should_search(incoming_msg) and TAVILY_API_KEY:
            query = build_search_query(current_agent_id, incoming_msg)
            search_context = tavily_search(query)
 
        ai_reply = get_ai_response(current_agent_id, incoming_msg, from_number, search_context)
        agent_name = AGENTS[current_agent_id]['name']
        resp.message(f"[{agent_name}]\n{ai_reply}")
    except Exception as e:
        resp.message(f"Something went wrong. Try again. ({str(e)[:80]})")
 
    return str(resp)
 
@app.route('/')
def home():
    return "Aaron's Life OS is live. All agents ready with web search.", 200
 
@app.route('/health')
def health():
    return "OK", 200
 
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
