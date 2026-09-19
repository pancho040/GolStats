import json
import requests
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

BOLIVIA_TZ = timezone(timedelta(hours=-4))

HEADERS_LIST = [
    {"User-Agent": "ESPN/7.0.0 (Android 14; Mobile; rv:1.0)", "Accept": "*/*"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36", "Accept": "*/*"}
]

MIRRORS = [
    "https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
]

def fetch_json_with_fallbacks(league_code, date_param=None, timeout=7):
    """Consulta ESPN rotando espejos y cabeceras con reintentos automáticos."""
    clean_date = None
    if date_param:
        # Sanitizar estrictamente: solo aceptar 8 dígitos numéricos YYYYMMDD
        match = re.match(r"^\d{8}$", str(date_param))
        if match:
            clean_date = match.group(0)
            
    for mirror_tmpl in MIRRORS:
        base_url = mirror_tmpl.format(league_code=league_code)
        url = f"{base_url}?dates={clean_date}" if clean_date else base_url
        
        for headers in HEADERS_LIST:
            try:
                resp = requests.get(url, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    # Si devuelve JSON válido con clave events
                    if "events" in data:
                        return data
                elif resp.status_code in [400, 404]:
                    # Si falló por la fecha, intentar de inmediato la jornada actual sin fecha
                    if clean_date:
                        fallback_resp = requests.get(base_url, headers=headers, timeout=timeout)
                        if fallback_resp.status_code == 200:
                            return fallback_resp.json()
            except Exception:
                continue
                
    return None

def parse_iso_date(date_str):
    if not date_str:
        return None
    try:
        if date_str.endswith("Z"):
            dt_utc = datetime.fromisoformat(date_str[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt_utc = datetime.fromisoformat(date_str)
        return dt_utc
    except Exception:
        return None

def parse_raw_event(ev, league_code, league_name):
    event_id = str(ev.get("id"))
    name = ev.get("name", "")
    short_name = ev.get("shortName", "")
    dt_utc = parse_iso_date(ev.get("date"))
    dt_local = dt_utc.astimezone(BOLIVIA_TZ) if dt_utc else None
    
    season_slug = ev.get("season", {}).get("slug", "")
    competitions = ev.get("competitions", [{}])[0]
    status_info = ev.get("status", {})
    status_type = status_info.get("type", {})
    state = status_type.get("state", "pre")
    completed = status_type.get("completed", False)
    clock = status_info.get("displayClock", "")
    detail_status = status_type.get("detail", "")
    
    venue = competitions.get("venue", {}).get("fullName", "")
    
    competitors = competitions.get("competitors", [])
    home_team = {}
    away_team = {}
    for c in competitors:
        t_info = {
            "id": c.get("id"),
            "name": c.get("team", {}).get("displayName", ""),
            "short_name": c.get("team", {}).get("shortDisplayName", ""),
            "score": c.get("score"),
            "logo": c.get("team", {}).get("logo", ""),
            "stats_raw": c.get("statistics", [])
        }
        if c.get("homeAway") == "home":
            home_team = t_info
        else:
            away_team = t_info
    
    details = competitions.get("details", [])
    goals = []
    for d in details:
        d_type = d.get("type", {}).get("text", "")
        if "Goal" in d_type:
            clock_str = d.get("clock", {}).get("displayValue", "")
            athletes = [a.get("displayName", "") for a in d.get("athletesInvolved", [])]
            scorer = athletes[0] if athletes else "Gol"
            t_id = str(d.get("team", {}).get("id"))
            is_home = (t_id == str(home_team.get("id")))
            goals.append({
                "player": scorer,
                "minute": clock_str,
                "team": home_team.get("name") if is_home else away_team.get("name"),
                "is_home": is_home
            })
    
    def extract_stat(stats_list, stat_name):
        for s in stats_list:
            if s.get("name") == stat_name:
                return s.get("displayValue", "-")
        return "-"
    
    home_possession = extract_stat(home_team.get("stats_raw", []), "possessionPct")
    away_possession = extract_stat(away_team.get("stats_raw", []), "possessionPct")
    home_shots = extract_stat(home_team.get("stats_raw", []), "totalShots")
    away_shots = extract_stat(away_team.get("stats_raw", []), "totalShots")
    home_sog = extract_stat(home_team.get("stats_raw", []), "shotsOnTarget")
    away_sog = extract_stat(away_team.get("stats_raw", []), "shotsOnTarget")
    
    video_link = None
    for l in ev.get("links", []):
        rel = l.get("rel", [])
        if "highlights" in rel or l.get("text") == "Highlights":
            video_link = l.get("href")
            break
    
    if not video_link and home_team.get("name") and away_team.get("name"):
        query = f"{home_team.get('name')} vs {away_team.get('name')} resumen goles"
        video_link = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
    
    return {
        "id": event_id,
        "name": name,
        "short_name": short_name,
        "date_utc": dt_utc,
        "date_local": dt_local,
        "league_code": league_code,
        "league_name": league_name,
        "season_slug": season_slug,
        "venue": venue,
        "state": state,
        "completed": completed,
        "clock": clock,
        "detail_status": detail_status,
        "home_team": home_team,
        "away_team": away_team,
        "goals": goals,
        "stats": {
            "home_possession": home_possession,
            "away_possession": away_possession,
            "home_shots": home_shots,
            "away_shots": away_shots,
            "home_sog": home_sog,
            "away_sog": away_sog
        },
        "video_link": video_link
    }

def get_league_events(league_code, dates=None):
    if not dates:
        date_queries = [None]
    elif isinstance(dates, str):
        date_queries = [dates]
    elif isinstance(dates, (list, tuple, set)):
        date_queries = list(dates)
    else:
        date_queries = [None]
        
    events_by_id = {}
    for d in date_queries:
        data = fetch_json_with_fallbacks(league_code, date_param=d)
        if not data:
            continue
            
        league_name = data.get("leagues", [{}])[0].get("name", league_code)
        for ev in data.get("events", []):
            ev_id = str(ev.get("id"))
            if ev_id not in events_by_id:
                events_by_id[ev_id] = parse_raw_event(ev, league_code, league_name)
                
    # Si después de consultar las fechas no hubo ningún evento, hacer un intento de rescate con la jornada actual
    if not events_by_id and dates:
        data_rescue = fetch_json_with_fallbacks(league_code, date_param=None)
        if data_rescue:
            league_name = data_rescue.get("leagues", [{}])[0].get("name", league_code)
            for ev in data_rescue.get("events", []):
                ev_id = str(ev.get("id"))
                if ev_id not in events_by_id:
                    events_by_id[ev_id] = parse_raw_event(ev, league_code, league_name)
                
    return list(events_by_id.values())

def is_team_match(event, team_list):
    home_name = event["home_team"].get("name", "").lower()
    away_name = event["away_team"].get("name", "").lower()
    for team in team_list:
        t_clean = team.strip().lower()
        if t_clean in home_name or t_clean in away_name:
            return True
    return False

def is_event_relevant(event, config):
    league_code = event["league_code"]
    leagues_cfg = {lg["code"]: lg for lg in config.get("leagues", [])}
    lg_cfg = leagues_cfg.get(league_code)
    
    if not lg_cfg:
        return False
        
    if lg_cfg.get("follow_all"):
        return True
        
    if league_code == "uefa.champions" and lg_cfg.get("knockout_only"):
        slug = event.get("season_slug", "").lower()
        is_knockout = any(k in slug for k in ["knockout", "round-of-16", "quarter", "semi", "final"])
        if is_knockout:
            return True
        return is_team_match(event, config.get("teams", []))
        
    return is_team_match(event, config.get("teams", []))
