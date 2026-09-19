import json
import os
from datetime import datetime, timezone, timedelta
import espn_service
from telegram_service import TelegramService

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("alert_24h", [])
                    data.setdefault("alert_1h", [])
                    data.setdefault("recap", [])
                    return data
        except Exception as e:
            print(f"Aviso leyendo state.json: {e}", flush=True)
    return {"alert_24h": [], "alert_1h": [], "recap": []}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error guardando estado: {e}", flush=True)

def initialize_on_startup(config):
    """Evita re-enviar alertas de partidos pasados si el contenedor se reinicia."""
    state = load_state()
    now_utc = datetime.now(timezone.utc)
    past_dates = [(now_utc - timedelta(days=i)).strftime("%Y%m%d") for i in range(1, 4)]
    
    for lg in config.get("leagues", []):
        try:
            events = espn_service.get_league_events(lg["code"], dates=past_dates)
            for ev in events:
                ev_id = ev["id"]
                if ev.get("completed") or ev.get("state") == "post":
                    if ev_id not in state["recap"]:
                        state["recap"].append(ev_id)
        except Exception as e:
            print(f"Aviso inicializando liga {lg.get('code')}: {e}", flush=True)
            
    save_state(state)
    print(f"Estado inicializado. Total partidos ignorados de inicio: {len(state['recap'])}", flush=True)

def check_and_notify(config, tg_service):
    state = load_state()
    now_utc = datetime.now(timezone.utc)
    
    dates_list = [(now_utc + timedelta(days=i)).strftime("%Y%m%d") for i in range(-1, 3)]
    
    leagues = config.get("leagues", [])
    relevant_matches = []
    
    for lg in leagues:
        try:
            events = espn_service.get_league_events(lg["code"], dates=dates_list)
            for ev in events:
                if espn_service.is_event_relevant(ev, config):
                    relevant_matches.append(ev)
        except Exception as e:
            print(f"Error consultando liga {lg.get('code')}: {e}", flush=True)
                
    for match in relevant_matches:
        match_id = match["id"]
        match_date = match.get("date_utc")
        if not match_date:
            continue
            
        diff_sec = (match_date - now_utc).total_seconds()
        diff_min = diff_sec / 60.0
        
        # 1. Alerta de 24 horas antes (ventana entre 20h y 26h antes)
        if 20 * 60 <= diff_min <= 26 * 60:
            if match_id not in state["alert_24h"] and match["state"] == "pre":
                msg = tg_service.format_24h_alert(match)
                if tg_service.send_message(msg):
                    state["alert_24h"].append(match_id)
                    print(f"Alerta 24h enviada: {match['name']}", flush=True)

        # 2. Alerta de 1 hora antes (ventana entre 30 y 90 minutos antes)
        if 30 <= diff_min <= 90:
            if match_id not in state["alert_1h"] and match["state"] == "pre":
                msg = tg_service.format_1h_alert(match)
                if tg_service.send_message(msg):
                    state["alert_1h"].append(match_id)
                    print(f"Alerta 1h enviada: {match['name']}", flush=True)

        # 3. Resumen post-partido (partido finalizado en las últimas 6 horas)
        if match["completed"] or match["state"] == "post":
            if -360 <= diff_min <= 0:
                if match_id not in state["recap"]:
                    msg = tg_service.format_postmatch_recap(match)
                    if tg_service.send_message(msg):
                        state["recap"].append(match_id)
                        print(f"Resumen enviado: {match['name']}", flush=True)

    for key in ["alert_24h", "alert_1h", "recap"]:
        if len(state[key]) > 300:
            state[key] = state[key][-200:]
            
    save_state(state)
