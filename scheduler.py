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
                return json.load(f)
        except Exception:
            pass
    return {"alert_24h": [], "alert_1h": [], "recap": []}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error guardando estado: {e}", flush=True)

def check_and_notify(config, tg_service):
    state = load_state()
    now_utc = datetime.now(timezone.utc)
    
    # Consultar ayer, hoy, mañana y pasado mañana individualmente (sin guiones)
    dates_list = [(now_utc + timedelta(days=i)).strftime("%Y%m%d") for i in range(-1, 3)]
    
    leagues = config.get("leagues", [])
    relevant_matches = []
    
    for lg in leagues:
        events = espn_service.get_league_events(lg["code"], dates=dates_list)
        for ev in events:
            if espn_service.is_event_relevant(ev, config):
                relevant_matches.append(ev)
                
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

        # 3. Resumen post-partido (partido finalizado en las últimas 12 horas)
        if match["completed"] or match["state"] == "post":
            if -720 <= diff_min <= 0:
                if match_id not in state["recap"]:
                    msg = tg_service.format_postmatch_recap(match)
                    if tg_service.send_message(msg):
                        state["recap"].append(match_id)
                        print(f"Resumen enviado: {match['name']}", flush=True)

    # Limpiar IDs viejos para no saturar memoria (mantener últimos 300)
    for key in ["alert_24h", "alert_1h", "recap"]:
        if len(state[key]) > 300:
            state[key] = state[key][-200:]
            
    save_state(state)
