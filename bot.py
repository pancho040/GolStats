import json
import os
import time
import threading
import http.server
import socketserver
import requests
from datetime import datetime, timezone, timedelta
import espn_service
from telegram_service import TelegramService
import scheduler

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def run_healthcheck_server():
    port = int(os.environ.get("PORT", 7860))
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "running", "bot": "GolStats"}')
        def log_message(self, format, *args):
            pass
    try:
        with socketserver.TCPServer(("", port), HealthHandler) as httpd:
            print(f"Servidor web de salud activo en el puerto {port}", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"Aviso servidor web: {e}", flush=True)

def handle_command(text, chat_id, cfg, tg):
    text = text.strip()
    cmd_parts = text.split(" ", 1)
    cmd = cmd_parts[0].lower()
    arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
    
    if cmd in ["/start", "/ayuda", "/help"]:
        msg = (
            "<b>GolStats · Bot de Alertas de Fútbol</b>\n\n"
            "Comandos disponibles:\n"
            "• <b>/proximos</b> — Ver próximos partidos programados\n"
            "• <b>/equipos</b> — Ver equipos y ligas que estás siguiendo\n"
            "• <b>/agregar &lt;equipo&gt;</b> — Añadir un nuevo equipo (ej: /agregar Inter Miami)\n"
            "• <b>/quitar &lt;equipo&gt;</b> — Quitar un equipo (ej: /quitar Chelsea)\n"
            "• <b>/resultados</b> — Ver marcadores y estadísticas recientes\n\n"
            "<i>Recibirás avisos automáticos 24h y 1h antes de cada partido, y el resumen al terminar.</i>"
        )
        tg.send_message(msg, chat_id=chat_id)
        
    elif cmd in ["/equipos", "/teams"]:
        teams_list = "\n".join([f"• {t}" for t in cfg.get("teams", [])])
        leagues_list = "\n".join([f"• {lg['name']}" + (" (Todos los partidos)" if lg.get("follow_all") else "") for lg in cfg.get("leagues", [])])
        msg = (
            "<b>EQUIPOS Y LIGAS EN SEGUIMIENTO</b>\n\n"
            f"<b>Tus Equipos:</b>\n{teams_list}\n\n"
            f"<b>Ligas Monitoreadas:</b>\n{leagues_list}"
        )
        tg.send_message(msg, chat_id=chat_id)
        
    elif cmd in ["/agregar", "/add"]:
        if not arg:
            tg.send_message("Escribe el nombre del equipo. Ejemplo:\n<code>/agregar Inter Miami</code>", chat_id=chat_id)
            return
        teams = cfg.get("teams", [])
        if any(t.lower() == arg.lower() for t in teams):
            tg.send_message(f"<b>{arg}</b> ya estaba en tu lista de equipos.", chat_id=chat_id)
        else:
            teams.append(arg)
            cfg["teams"] = teams
            save_config(cfg)
            tg.send_message(f"✅ Se agregó <b>{arg}</b> a tus alertas.", chat_id=chat_id)

    elif cmd in ["/quitar", "/remove"]:
        if not arg:
            tg.send_message("Escribe el nombre del equipo a eliminar. Ejemplo:\n<code>/quitar Chelsea</code>", chat_id=chat_id)
            return
        teams = cfg.get("teams", [])
        new_teams = [t for t in teams if t.lower() != arg.lower()]
        if len(new_teams) == len(teams):
            tg.send_message(f"No se encontró <b>{arg}</b> en tu lista. Escribe /equipos para ver los nombres exactos.", chat_id=chat_id)
        else:
            cfg["teams"] = new_teams
            save_config(cfg)
            tg.send_message(f"🗑 Se eliminó <b>{arg}</b> de tus alertas.", chat_id=chat_id)
            
    elif cmd in ["/proximos", "/fixtures"]:
        tg.send_message("Buscando próximos partidos...", chat_id=chat_id)
        now_utc = datetime.now(timezone.utc)
        dates_list = [(now_utc + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]
        
        upcoming = []
        for lg in cfg.get("leagues", []):
            events = espn_service.get_league_events(lg["code"], dates=dates_list)
            for ev in events:
                if ev.get("state") == "pre" and espn_service.is_event_relevant(ev, cfg):
                    upcoming.append(ev)
                    
        upcoming.sort(key=lambda x: x["date_utc"] if x.get("date_utc") else datetime.max.replace(tzinfo=timezone.utc))
        msg = tg.format_upcoming_list(upcoming[:20])
        tg.send_message(msg, chat_id=chat_id)
        
    elif cmd in ["/resultados", "/results"]:
        tg.send_message("Buscando resultados recientes...", chat_id=chat_id)
        now_utc = datetime.now(timezone.utc)
        dates_list = [(now_utc - timedelta(days=i)).strftime("%Y%m%d") for i in range(4)]
        
        finished = []
        for lg in cfg.get("leagues", []):
            events = espn_service.get_league_events(lg["code"], dates=dates_list)
            for ev in events:
                if (ev.get("completed") or ev.get("state") == "post") and espn_service.is_event_relevant(ev, cfg):
                    finished.append(ev)
                    
        if not finished:
            tg.send_message("No se encontraron resultados de tus equipos en los últimos días.", chat_id=chat_id)
        else:
            # Ordenar por fecha más reciente
            finished.sort(key=lambda x: x["date_utc"] if x.get("date_utc") else datetime.min.replace(tzinfo=timezone.utc))
            for m in finished[-4:]:
                tg.send_message(tg.format_postmatch_recap(m), chat_id=chat_id)

def poll_telegram_updates(cfg, tg, stop_event):
    last_update_id = 0
    token = cfg["telegram_token"]
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    while not stop_event.is_set():
        try:
            params = {"timeout": 15, "offset": last_update_id + 1}
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                for update in data.get("result", []):
                    last_update_id = update.get("update_id", last_update_id)
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    sender_id = msg.get("chat", {}).get("id")
                    if text and sender_id:
                        handle_command(text, sender_id, cfg, tg)
        except Exception:
            time.sleep(2)
        time.sleep(1)

def scheduler_loop(cfg, tg, stop_event):
    check_interval = cfg.get("check_interval_seconds", 300)
    while not stop_event.is_set():
        try:
            current_cfg = load_config()
            scheduler.check_and_notify(current_cfg, tg)
        except Exception as e:
            print(f"Error en scheduler_loop: {e}", flush=True)
            
        for _ in range(check_interval):
            if stop_event.is_set():
                break
            time.sleep(1)

def main():
    cfg = load_config()
    tg = TelegramService(cfg["telegram_token"], cfg["chat_id"])
    print("Iniciando GolStats Bot...", flush=True)
    
    stop_event = threading.Event()
    
    t_health = threading.Thread(target=run_healthcheck_server, daemon=True)
    t_health.start()
    
    t_poll = threading.Thread(target=poll_telegram_updates, args=(cfg, tg, stop_event), daemon=True)
    t_poll.start()
    
    scheduler.check_and_notify(cfg, tg)
    
    t_sched = threading.Thread(target=scheduler_loop, args=(cfg, tg, stop_event), daemon=True)
    t_sched.start()
    
    print("Bot corriendo correctamente. Escuchando alertas y comandos...", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo bot...", flush=True)
        stop_event.set()

if __name__ == "__main__":
    main()
