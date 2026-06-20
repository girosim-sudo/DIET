"""
Ferrero Mensa Coach - Alba
Web app Streamlit per scegliere il pranzo alla mensa Ferrero Alba e suggerire la cena
in base al piano alimentare personale da 1800 kcal.

Avvio:
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup

MENU_INDEX_URL = "https://ferrero.compasscloud.it/presentazione_menu"
APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR / "diario_alimentare.json"

# Preferenze e vincoli personali. Modificabili qui o nel pannello laterale.
DEFAULT_PROFILE = {
    "target_kcal": 1800,
    "acqua_litri": 2.5,
    "olio_g_giorno": 30,
    "verdura_g_pasto": 200,
    "evita": ["fragole", "arachidi"],
    "non_graditi": ["carciofi", "cavolfiore", "broccoli", "melone"],
    "note": [
        "steatosi/MASLD: preferire piatti semplici, verdure, legumi, cereali integrali, pesce e carni magre",
        "niente pane se già si sceglie pasta, riso, farro, cous cous o patate",
        "una sola fonte proteica principale per pasto, salvo porzioni molto piccole",
        "olio: misurato; se il piatto è già condito, non aggiungere altro olio a crudo",
        "peperoncino ok, ma limitarlo se compare reflusso",
    ],
}

FIXED_OPTIONS = [
    {
        "name": "Pokè controllata: riso Venere o farro + 3 verdure + pollo/tacchino + poca salsa yogurt",
        "category": "Piatto unico",
        "line": "Alternative fisse",
        "score": 96,
        "tags": ["carboidrato", "proteina magra", "verdura", "controllabile", "integrale"],
        "reason": "Molto controllabile: carboidrato, proteina magra, tante verdure e condimento moderato.",
    },
    {
        "name": "Pasta integrale al sugo rosso + pollo/tacchino ai ferri + insalata cruda",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 93,
        "tags": ["integrale", "sugo semplice", "proteina magra", "verdura"],
        "reason": "Scelta standard ottima quando il menù del giorno è troppo ricco.",
    },
    {
        "name": "Riso integrale al sugo rosso + pollo/tacchino ai ferri + insalata cruda",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 91,
        "tags": ["integrale", "sugo semplice", "proteina magra", "verdura"],
        "reason": "Alternativa valida alla pasta integrale, saziante e facile da gestire.",
    },
    {
        "name": "Pollo o tacchino ai ferri + verdure crude/cotte + pane controllato",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 89,
        "tags": ["proteina magra", "verdura", "carboidrato controllato"],
        "reason": "Piano B pulito se non ci sono primi o piatti unici adatti.",
    },
    {
        "name": "Sottofiletto ai ferri + insalata grande + pane/riso controllato",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 78,
        "tags": ["carne rossa", "verdura", "occasionale"],
        "reason": "Accettabile, ma meno frequente rispetto a pollo e tacchino perché è carne rossa.",
    },
]

CATEGORY_HEADINGS = {
    "primi piatti": "Primi Piatti",
    "secondi piatti": "Secondi Piatti",
    "contorni": "Contorni",
    "piatto unico": "Piatto unico",
    "alternative fisse": "Alternative fisse",
}

BAD_KEYWORDS = {
    "fritto": -35, "fritti": -35, "chips": -35, "impan": -25, "crosta": -18,
    "gratin": -22, "burro": -20, "panna": -22, "gorgo": -25, "gorgonzola": -25,
    "scamorza": -18, "torta salata": -26, "strudel": -20, "bacon": -28,
    "salsiccia": -30, "salame": -30, "wurstel": -30, "carbonara": -28,
    "nocina": -22, "lasagne": -18, "ragu": -8, "ragù": -8, "maionese": -25,
    "patate fritte": -45, "dolce": -35, "dessert": -35,
}

GOOD_KEYWORDS = {
    "integral": 15, "vapore": 22, "grigliat": 16, "ferri": 20, "sugo rosso": 12,
    "pomodoro": 10, "verdure": 12, "insalata": 18, "bieta": 12, "zucchine": 12,
    "carote": 10, "fagiolini": 12, "cime di rapa": 12, "melanzane": 10,
    "legumi": 18, "ceci": 18, "lenticchie": 18, "fagioli": 18, "piselli": 11,
    "pesce": 18, "tonno": 18, "nasello": 20, "orata": 20, "passera": 20,
    "sgombro": 15, "salmone": 12, "trota": 10, "pollo": 18, "tacchino": 18,
    "farro": 15, "riso venere": 17, "riso integrale": 17, "basmati": 8,
    "quinoa": 16, "cous cous": 10, "zuppa": 8, "minestrone": 12,
}

PROTEIN_KEYWORDS = {
    "fish": ["pesce", "tonno", "salmone", "sgombro", "trota", "orata", "nasello", "passera", "merluzzo", "platessa", "gamberi"],
    "poultry": ["pollo", "tacchino"],
    "red_meat": ["bovino", "vitello", "manzo", "sottofiletto", "tagliata", "lonza", "maiale"],
    "eggs": ["uova", "frittata"],
    "cheese": ["ricotta", "primo sale", "mozzarella", "fiocchi", "scamorza", "gorgo", "formaggio"],
    "legumes": ["ceci", "lenticchie", "fagioli", "piselli", "legumi", "falafel"],
    "soy": ["tofu", "seitan", "soia"],
}

CARB_KEYWORDS = ["pasta", "riso", "farro", "orzo", "cous cous", "quinoa", "pane", "patate", "lasagne", "noodles", "spaghetti", "fusilli", "penne", "pennette", "rigatoni", "tagliatelle"]
VEG_KEYWORDS = ["verdure", "insalata", "zucchine", "carote", "bieta", "fagiolini", "broccoli", "cavolfiore", "cime di rapa", "melanzane", "pomodoro", "pomodorini", "asparagi", "songino", "crudite", "crudité", "agro", "spinaci"]
RICH_KEYWORDS = ["frit", "gratin", "burro", "panna", "gorgo", "scamorza", "torta salata", "strudel", "bacon", "salsiccia", "lasagne", "crosta", "impan", "nocina"]

@dataclass
class Dish:
    name: str
    category: str = "Altro"
    line: str = ""
    score: int = 0
    tags: List[str] = None
    reason: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def lower(text: str) -> str:
    return normalize(text).lower()


def is_probable_dish(line: str) -> bool:
    if not line or len(line) < 4:
        return False
    lowered = lower(line)
    banned_exact = {
        "visualizza", "tutti", "pranzo", "cena", "stampa il menu", "precedente", "successiva",
        "caricamento in corso...", "il tuo menu", "completa settimana", "visualizza piatti senza:",
        "le immagini visualizzate sono a puro titolo esemplificativo",
    }
    if lowered in banned_exact:
        return False
    if lowered.startswith("image:") or lowered.startswith("cereali contenenti"):
        return False
    if "prodotti a base" in lowered or "allerg" in lowered:
        return False
    if lowered.startswith("giu ") or re.match(r"^(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)$", lowered):
        return False
    if lowered in CATEGORY_HEADINGS:
        return False
    if lowered.startswith("linea self") or lowered.startswith("primavera"):
        return False
    return any(k in lowered for k in CARB_KEYWORDS + VEG_KEYWORDS + sum(PROTEIN_KEYWORDS.values(), []) + ["zuppa", "crema", "burger", "falafel"])


def classify_category(name: str, current_category: Optional[str] = None) -> str:
    n = lower(name)
    if current_category:
        return current_category
    if any(k in n for k in ["pasta", "spaghetti", "fusilli", "penne", "pennette", "rigatoni", "tagliatelle", "risotto", "riso", "zuppa", "crema", "minestrone", "cous cous", "farro", "orzo"]):
        return "Primi Piatti"
    if any(k in n for k in ["pollo", "tacchino", "bovino", "vitello", "lonza", "orata", "nasello", "passera", "salmone", "sgombro", "trota", "uova", "frittata", "burger", "tofu", "seitan", "falafel", "straccetti", "filetto"]):
        return "Secondi Piatti"
    if any(k in n for k in VEG_KEYWORDS) or "patate" in n:
        return "Contorni"
    if any(k in n for k in ["noodles", "nasi goreng", "fish and chips"]):
        return "Piatto unico"
    return "Altro"


def score_dish(name: str, category: str = "Altro", line: str = "") -> Tuple[int, List[str], str]:
    n = lower(name)
    score = 50
    tags: List[str] = []
    reasons: List[str] = []

    if "healthy" in lower(line):
        score += 8
        tags.append("linea healthy")
    if "urban" in lower(line):
        score -= 3
    if "traditional" in lower(line):
        score -= 2

    for kw, delta in GOOD_KEYWORDS.items():
        if kw in n:
            score += delta
            tags.append(kw)
    for kw, delta in BAD_KEYWORDS.items():
        if kw in n:
            score += delta
            tags.append(f"attenzione: {kw}")

    if category == "Contorni":
        score += 10
        if "patate" in n:
            score -= 12
            tags.append("patate = carboidrato")
        if any(k in n for k in ["gratin", "fritte", "burro"]):
            score -= 25
    elif category == "Primi Piatti":
        score += 2
        if any(k in n for k in ["integral", "farro", "orzo", "riso venere", "riso integrale"]):
            score += 8
        if any(k in n for k in ["ricotta", "pesto", "crema", "caprese"]):
            score -= 5
    elif category == "Secondi Piatti":
        score += 5
        if any(k in n for k in ["vapore", "ferri", "grigli"]):
            score += 15
        if any(k in n for k in ["lonza", "bovino", "vitello", "maiale", "sottofiletto"]):
            score -= 5
    elif category == "Piatto unico":
        score += 4

    # Allergie dichiarate nel piano: fragole e arachidi.
    if "arachid" in n:
        score = min(score, 5)
        tags.append("evitare: arachidi")
        reasons.append("Contiene arachidi, da evitare per allergia/intolleranza indicata.")
    if "fragol" in n:
        score = min(score, 5)
        tags.append("evitare: fragole")
        reasons.append("Contiene fragole, da evitare per allergia/intolleranza indicata.")

    if any(k in n for k in CARB_KEYWORDS):
        tags.append("carboidrato")
    if any(k in n for k in VEG_KEYWORDS):
        tags.append("verdura")
    for protein_type, kws in PROTEIN_KEYWORDS.items():
        if any(k in n for k in kws):
            tags.append(protein_type)

    if score >= 85:
        reasons.append("Molto adatto: semplice, bilanciabile e coerente con carboidrato/proteina/verdura.")
    elif score >= 70:
        reasons.append("Buono, da completare con verdura e condimento controllato.")
    elif score >= 55:
        reasons.append("Accettabile, ma attenzione ad abbinamenti e porzioni.")
    else:
        reasons.append("Da limitare oggi: rischia di essere troppo ricco o poco adatto all'obiettivo.")

    return max(0, min(100, score)), sorted(set(tags)), " ".join(reasons)


def fetch_url(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FerreroMensaCoach/1.0; +local-app)",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def get_menu_links() -> Dict[str, str]:
    html = fetch_url(MENU_INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    links: Dict[str, str] = {}

    # Strategia robusta: i link "Visualizza" sono preceduti dal nome linea.
    visible_links = [a for a in anchors if "menu/" in a["href"]]
    text_lines = [normalize(x) for x in soup.get_text("\n").split("\n") if normalize(x)]
    line_names = [x for x in text_lines if x.upper().startswith("LINEA SELF ALBA") or "LUNCH BOX" in x.upper()]

    for idx, a in enumerate(visible_links):
        href = a["href"]
        if href.startswith("/"):
            href = "https://ferrero.compasscloud.it" + href
        elif href.startswith("menu/"):
            href = "https://ferrero.compasscloud.it/" + href
        label = line_names[idx] if idx < len(line_names) else f"Linea {idx + 1}"
        if "POZZUOLO" not in label.upper() and "LUNCH BOX" not in label.upper():
            links[label] = href
    return links


def parse_menu_page(url: str) -> Tuple[str, str, List[Dish]]:
    html = fetch_url(url)
    soup = BeautifulSoup(html, "html.parser")
    lines = [normalize(x) for x in soup.get_text("\n").split("\n") if normalize(x)]

    menu_date = next((x for x in lines if re.search(r"\b\d{1,2}\s+\w+\s+20\d{2}\b", x, flags=re.I)), "")
    line_name = next((x for x in lines if x.upper().startswith("LINEA SELF")), "")

    dishes: List[Dish] = []
    current_category: Optional[str] = None
    in_daily = False

    # Tenta estrazione del solo menu giornaliero tra "Il Tuo menu" e "I piatti contrassegnati".
    daily_lines: List[str] = []
    for x in lines:
        xl = lower(x)
        if xl == "il tuo menu":
            in_daily = True
            daily_lines = []
            continue
        if in_daily and xl.startswith("i piatti contrassegnati"):
            break
        if in_daily:
            daily_lines.append(x)

    for x in daily_lines:
        xl = lower(x)
        if xl in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[xl]
            continue
        if is_probable_dish(x):
            cat = classify_category(x, current_category)
            sc, tags, reason = score_dish(x, cat, line_name)
            dishes.append(Dish(name=x, category=cat, line=line_name, score=sc, tags=tags, reason=reason, url=url))

    # Fallback: se il blocco giornaliero non viene estratto bene, usa tutte le righe probabili.
    if not dishes:
        for x in lines:
            xl = lower(x)
            if xl in CATEGORY_HEADINGS:
                current_category = CATEGORY_HEADINGS[xl]
                continue
            if is_probable_dish(x):
                cat = classify_category(x, current_category)
                sc, tags, reason = score_dish(x, cat, line_name)
                dishes.append(Dish(name=x, category=cat, line=line_name, score=sc, tags=tags, reason=reason, url=url))

    # Deduplica preservando ordine.
    seen = set()
    unique: List[Dish] = []
    for d in dishes:
        key = (lower(d.name), d.category, lower(d.line))
        if key not in seen:
            unique.append(d)
            seen.add(key)
    return menu_date, line_name, unique


def load_all_menus(selected_lines: Optional[List[str]] = None) -> Tuple[str, List[Dish], List[str]]:
    errors: List[str] = []
    all_dishes: List[Dish] = []
    menu_date = ""
    links = get_menu_links()
    if selected_lines:
        links = {k: v for k, v in links.items() if k in selected_lines}
    for line_name, url in links.items():
        try:
            d, line, dishes = parse_menu_page(url)
            if d and not menu_date:
                menu_date = d
            # Se il nome linea non viene estratto, usa quello dell'indice.
            for dish in dishes:
                if not dish.line:
                    dish.line = line_name
            all_dishes.extend(dishes)
        except Exception as exc:  # noqa: BLE001 - utile in app locale
            errors.append(f"{line_name}: {exc}")

    # Aggiunge alternative fisse personali.
    for item in FIXED_OPTIONS:
        all_dishes.append(Dish(**item))

    return menu_date, all_dishes, errors


def parse_manual_menu(text: str) -> List[Dish]:
    dishes: List[Dish] = []
    current_category: Optional[str] = None
    for raw in text.splitlines():
        line = normalize(raw.strip("-•* "))
        if not line:
            continue
        xl = lower(line).rstrip(":")
        if xl in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[xl]
            continue
        if ":" in line and lower(line.split(":", 1)[0]) in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[lower(line.split(":", 1)[0])]
            rest = line.split(":", 1)[1].strip()
            if rest:
                for part in re.split(r"[,;]", rest):
                    p = normalize(part)
                    if p:
                        cat = classify_category(p, current_category)
                        sc, tags, reason = score_dish(p, cat, "Menu manuale")
                        dishes.append(Dish(p, cat, "Menu manuale", sc, tags, reason))
            continue
        if is_probable_dish(line) or len(line.split()) >= 2:
            cat = classify_category(line, current_category)
            sc, tags, reason = score_dish(line, cat, "Menu manuale")
            dishes.append(Dish(line, cat, "Menu manuale", sc, tags, reason))
    for item in FIXED_OPTIONS:
        dishes.append(Dish(**item))
    return dishes


def unique_dishes(dishes: Iterable[Dish]) -> List[Dish]:
    seen = set()
    out = []
    for d in dishes:
        key = (lower(d.name), d.category)
        if key not in seen:
            out.append(d)
            seen.add(key)
    return out


def best_by_category(dishes: List[Dish], category: str, n: int = 5) -> List[Dish]:
    return sorted([d for d in dishes if d.category == category], key=lambda d: d.score, reverse=True)[:n]


def find_best_lunch(dishes: List[Dish]) -> Dict[str, object]:
    dishes = unique_dishes(dishes)
    piatti_unici = sorted([d for d in dishes if d.category in {"Piatto unico", "Combinazione"}], key=lambda d: d.score, reverse=True)
    primi = best_by_category(dishes, "Primi Piatti", 10)
    secondi = best_by_category(dishes, "Secondi Piatti", 10)
    contorni = best_by_category(dishes, "Contorni", 10)

    candidates: List[Dict[str, object]] = []

    for d in piatti_unici[:8]:
        candidates.append({
            "type": "piatto_unico",
            "score": d.score,
            "items": [d],
            "text": d.name,
            "rationale": d.reason,
        })

    for primo in primi[:6]:
        for secondo in secondi[:6]:
            # Evita doppia proteina se il primo contiene già tonno/salmone/uova/formaggio/legumi.
            primo_has_protein = any(tag in primo.tags for tag in ["fish", "poultry", "red_meat", "eggs", "cheese", "legumes", "soy"])
            penalty = 14 if primo_has_protein else 0
            contorno = contorni[0] if contorni else None
            combo_score = int((primo.score * 0.36) + (secondo.score * 0.38) + ((contorno.score if contorno else 60) * 0.26) - penalty)
            items = [primo, secondo] + ([contorno] if contorno else [])
            candidates.append({
                "type": "combo",
                "score": combo_score,
                "items": items,
                "text": " + ".join(d.name for d in items),
                "rationale": "Combinazione completa: carboidrato + proteina + verdura. " + ("Attenzione: il primo contiene già una proteina; evita porzioni doppie. " if primo_has_protein else ""),
            })

    # Primo proteico + contorno senza secondo.
    for primo in primi[:8]:
        if any(tag in primo.tags for tag in ["fish", "eggs", "cheese", "legumes", "soy", "poultry"]):
            contorno = contorni[0] if contorni else None
            combo_score = int((primo.score * 0.68) + ((contorno.score if contorno else 60) * 0.32) + 4)
            items = [primo] + ([contorno] if contorno else [])
            candidates.append({
                "type": "primo_proteico",
                "score": combo_score,
                "items": items,
                "text": " + ".join(d.name for d in items),
                "rationale": "Il primo contiene già una proteina: non aggiungere pane né un secondo completo.",
            })

    # Secondo + contorno + carboidrato semplice quando i primi non sono adatti.
    for secondo in secondi[:8]:
        contorno = contorni[0] if contorni else None
        combo_score = int((secondo.score * 0.58) + ((contorno.score if contorno else 60) * 0.32) + 8)
        text = f"{secondo.name} + {contorno.name if contorno else 'insalata cruda'} + pane/riso controllato"
        items = [secondo] + ([contorno] if contorno else [])
        candidates.append({
            "type": "secondo_contorno",
            "score": combo_score,
            "items": items,
            "text": text,
            "rationale": "Usa una sola quota di carboidrato: pane oppure riso/pasta semplice, non entrambi.",
        })

    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    best = candidates[0] if candidates else None
    alternatives = candidates[1:4]
    avoid = sorted([d for d in dishes if d.score < 55], key=lambda d: d.score)[:8]
    return {"best": best, "alternatives": alternatives, "avoid": avoid, "all": dishes}


def meal_contains(items: Iterable[Dish], words: Iterable[str]) -> bool:
    text = " ".join(d.name for d in items).lower()
    return any(w in text for w in words)


def suggest_dinner(lunch_items: Iterable[Dish], lunch_score: int) -> Dict[str, str]:
    items = list(lunch_items)
    rich = meal_contains(items, RICH_KEYWORDS) or lunch_score < 65
    fish = meal_contains(items, PROTEIN_KEYWORDS["fish"])
    poultry = meal_contains(items, PROTEIN_KEYWORDS["poultry"])
    red_meat = meal_contains(items, PROTEIN_KEYWORDS["red_meat"])
    cheese = meal_contains(items, PROTEIN_KEYWORDS["cheese"])
    legumes = meal_contains(items, PROTEIN_KEYWORDS["legumes"])
    eggs = meal_contains(items, PROTEIN_KEYWORDS["eggs"])
    carb_heavy = meal_contains(items, ["lasagne", "patate", "pizza", "pasta", "riso", "cous cous", "farro", "noodles"])

    if rich:
        dinner = "Cena leggera: pollo/tacchino ai ferri o pesce bianco + verdure abbondanti. Carboidrato ridotto: 50-70 g pane oppure niente pane se non hai fame."
        why = "Il pranzo è risultato ricco o poco pulito: la sera compensiamo senza saltare il pasto."
    elif fish:
        dinner = "Cena: pollo o tacchino ai ferri + verdure abbondanti + 80-100 g pane fresco/integrale. Evita formaggi e salumi."
        why = "A pranzo hai già usato pesce/tonno/salmone: la sera ruotiamo su carne bianca magra."
    elif red_meat:
        dinner = "Cena: pesce bianco al forno/vapore oppure legumi + verdure + 80-100 g pane. Evita altra carne rossa."
        why = "A pranzo c'è carne rossa: meglio non ripeterla nello stesso giorno."
    elif cheese:
        dinner = "Cena: pesce bianco o tacchino + verdure + 80-100 g pane. Niente altri formaggi."
        why = "A pranzo c'è formaggio: la sera conviene scegliere una proteina più magra."
    elif legumes:
        dinner = "Cena: pesce o pollo/tacchino + verdure + pane controllato. Se hai gonfiore, evita altri legumi la sera."
        why = "A pranzo hai già inserito legumi: ottimo, ma meglio variare la proteina a cena."
    elif eggs:
        dinner = "Cena: pesce bianco o pollo/tacchino + verdure + pane controllato. Evita altre uova."
        why = "A pranzo hai già usato uova: ruotiamo la fonte proteica."
    elif poultry:
        dinner = "Cena: pesce oppure legumi + verdure + pane/riso controllato."
        why = "A pranzo hai fatto carne bianca: la sera si può variare con pesce o legumi."
    else:
        dinner = "Cena: proteina magra a scelta + verdure abbondanti + 80-100 g pane o 80 g riso."
        why = "Pranzo abbastanza neutro: resta sullo schema base del piano."

    if carb_heavy and not rich:
        why += " Poiché a pranzo c'è già una quota di carboidrati, a cena non sommare pane e patate/riso."
    return {"dinner": dinner, "why": why}


def load_log() -> List[Dict[str, object]]:
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_log(entries: List[Dict[str, object]]) -> None:
    LOG_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def add_log_entry(entry: Dict[str, object]) -> None:
    entries = load_log()
    entries.append(entry)
    save_log(entries)


def weekly_counts(entries: List[Dict[str, object]]) -> Dict[str, int]:
    counts = {"fish": 0, "poultry": 0, "red_meat": 0, "cheese": 0, "eggs": 0, "legumes": 0, "rich": 0}
    today = date.today()
    for e in entries:
        try:
            d = datetime.fromisoformat(str(e.get("date"))).date()
        except Exception:
            continue
        if (today - d).days > 7:
            continue
        text = lower(str(e.get("lunch", "")) + " " + str(e.get("dinner", "")))
        for key, kws in PROTEIN_KEYWORDS.items():
            if any(k in text for k in kws):
                counts[key] = counts.get(key, 0) + 1
        if any(k in text for k in RICH_KEYWORDS):
            counts["rich"] += 1
    return counts


def render_score(score: int) -> str:
    if score >= 85:
        return f"🟢 {score}/100"
    if score >= 70:
        return f"🟡 {score}/100"
    if score >= 55:
        return f"🟠 {score}/100"
    return f"🔴 {score}/100"


def main() -> None:
    st.set_page_config(page_title="Ferrero Mensa Coach", page_icon="🥗", layout="centered")
    st.title("🥗 Ferrero Mensa Coach - Alba")
    st.markdown("""
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 1.1rem;}
    .stButton button {width: 100%; border-radius: 10px;}
    @media (max-width: 768px) {
        h1 {font-size: 1.6rem !important;}
        h2, h3 {font-size: 1.15rem !important;}
        .block-container {padding-left: 1rem; padding-right: 1rem;}
    }
    </style>
    """, unsafe_allow_html=True)
    st.caption("Supporto pratico per applicare il piano alimentare alla mensa. Non sostituisce nutrizionista o medico.")

    with st.sidebar:
        st.header("Profilo")
        st.write(f"Schema: **{DEFAULT_PROFILE['target_kcal']} kcal**")
        st.write(f"Acqua: **{DEFAULT_PROFILE['acqua_litri']} L/die**")
        st.write(f"Olio EVO target: **{DEFAULT_PROFILE['olio_g_giorno']} g/die**")
        st.write("Alternative fisse considerate: pollo/tacchino ai ferri, sottofiletto ai ferri, banco insalata, pasta/riso al sugo rosso, pokè.")
        st.divider()
        mode = st.radio("Origine menù", ["Scarica dal sito", "Inserisco/copio il menù"], index=0)
        include_traditional = st.checkbox("Traditional", value=True)
        include_healthy = st.checkbox("Healthy", value=True)
        include_urban = st.checkbox("Urban Grill", value=True)
        include_chroma = st.checkbox("Chroma Corner", value=False)
        include_local = st.checkbox("Local&World", value=True)
        st.divider()
        st.write("Allergie/intolleranze da evitare: **fragole, arachidi**.")
        st.write("Non graditi: carciofi, cavolfiore, broccoli, melone.")

    selected_lines = None
    if mode == "Scarica dal sito":
        try:
            links = get_menu_links()
            selected_lines = []
            for name in links:
                up = name.upper()
                if "TRADITIONAL" in up and include_traditional:
                    selected_lines.append(name)
                elif "HEALTHY" in up and include_healthy:
                    selected_lines.append(name)
                elif "URBAN" in up and include_urban:
                    selected_lines.append(name)
                elif "CHROMA" in up and include_chroma:
                    selected_lines.append(name)
                elif "LOCAL" in up and include_local:
                    selected_lines.append(name)
        except Exception:
            selected_lines = None

    if mode == "Scarica dal sito":
        with st.spinner("Leggo il menù Ferrero CompassCloud..."):
            try:
                menu_date, dishes, errors = load_all_menus(selected_lines=selected_lines)
            except Exception as exc:
                menu_date, dishes, errors = "", [], [str(exc)]
        if errors:
            with st.expander("Avvisi di lettura sito"):
                for e in errors:
                    st.warning(e)
        if not dishes:
            st.error("Non sono riuscito a leggere il sito. Usa la modalità manuale nel pannello laterale e incolla il menù.")
            st.stop()
    else:
        st.info("Incolla il menù: puoi scrivere 'Primi:', 'Secondi:', 'Contorni:' e poi i piatti.")
        manual_text = st.text_area("Menù del giorno", height=220, placeholder="Primi: pasta integrale al pomodoro; risotto...\nSecondi: pollo ai ferri; nasello al vapore...\nContorni: melanzane al funghetto; insalata...")
        dishes = parse_manual_menu(manual_text) if manual_text else [Dish(**item) for item in FIXED_OPTIONS]
        menu_date = date.today().strftime("%d/%m/%Y")

    result = find_best_lunch(dishes)
    best = result["best"]
    alternatives = result["alternatives"]
    avoid = result["avoid"]

    st.subheader(f"Indicazione per oggi {('— ' + menu_date) if menu_date else ''}")

    if best:
        lunch_items: List[Dish] = best["items"]  # type: ignore[assignment]
        dinner = suggest_dinner(lunch_items, int(best["score"]))
        col1, col2 = st.columns([1.2, 1])
        with col1:
            st.markdown("### ✅ Pranzo consigliato")
            st.markdown(f"**{best['text']}**")
            st.markdown(f"Punteggio: **{render_score(int(best['score']))}**")
            st.write(str(best["rationale"]))
            st.info("Regola: niente pane se il pranzo contiene già pasta/riso/farro/cous cous/patate. Aggiungi insalata cruda se la verdura del piatto è poca.")
        with col2:
            st.markdown("### 🌙 Cena consigliata")
            st.markdown(f"**{dinner['dinner']}**")
            st.write(dinner["why"])
            st.warning("Bevi fino ad arrivare ad almeno 2,5 L d'acqua nella giornata. Peperoncino ok se non dà reflusso.")

        st.divider()
        st.markdown("### Alternative valide")
        if alternatives:
            for alt in alternatives:
                with st.container(border=True):
                    st.markdown(f"**{alt['text']}**")
                    st.caption(f"Punteggio: {render_score(int(alt['score']))} — {alt['rationale']}")
        else:
            st.write("Nessuna alternativa rilevante trovata.")

        st.markdown("### Da evitare o limitare oggi")
        if avoid:
            cols = st.columns(2)
            for i, d in enumerate(avoid):
                with cols[i % 2]:
                    st.write(f"{render_score(d.score)} **{d.name}** — {d.line}")
        else:
            st.write("Non emergono piatti chiaramente critici tra quelli letti.")

        st.divider()
        st.markdown("### Tutti i piatti letti e punteggio")
        for d in sorted(unique_dishes(dishes), key=lambda x: x.score, reverse=True):
            with st.expander(f"{render_score(d.score)} {d.name} — {d.category} — {d.line}"):
                st.write(d.reason)
                if d.tags:
                    st.write("Tag:", ", ".join(d.tags))
                if d.url:
                    st.write(d.url)

        st.divider()
        st.markdown("### Diario")
        eaten_lunch = st.text_input("Cosa hai mangiato davvero a pranzo?", value=str(best["text"]))
        eaten_dinner = st.text_input("Cena fatta o prevista", value=dinner["dinner"])
        note = st.text_area("Note facoltative", placeholder="Fame, reflusso, energia, acqua bevuta...")
        if st.button("Salva giornata"):
            add_log_entry({
                "date": date.today().isoformat(),
                "lunch": eaten_lunch,
                "dinner": eaten_dinner,
                "score": int(best["score"]),
                "note": note,
            })
            st.success("Giornata salvata nel diario locale.")

    entries = load_log()
    if entries:
        with st.sidebar:
            st.divider()
            st.header("Ultimi 7 giorni")
            counts = weekly_counts(entries)
            st.write(f"Pesce: {counts.get('fish', 0)}")
            st.write(f"Carne bianca: {counts.get('poultry', 0)}")
            st.write(f"Carne rossa/maiale: {counts.get('red_meat', 0)}")
            st.write(f"Formaggi: {counts.get('cheese', 0)}")
            st.write(f"Uova: {counts.get('eggs', 0)}")
            st.write(f"Legumi: {counts.get('legumes', 0)}")
            if counts.get("rich", 0) > 1:
                st.warning("Settimana un po' ricca: attenzione a fritti/gratin/formaggi/salse.")

    st.caption("Versione web/mobile. Se CompassCloud cambia struttura, usa la modalità manuale dal menu laterale.")


if __name__ == "__main__":
    main()
