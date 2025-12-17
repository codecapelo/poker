import random
import math
import json
import os
import time
from itertools import combinations as combos
from dataclasses import dataclass
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence, Tuple, Literal
from concurrent.futures import ProcessPoolExecutor, as_completed, Future

import streamlit as st
from treys import Card as TreysCard, Evaluator

# #region agent log
LOG_PATH = "/Users/test/poker_app/.cursor/debug.log"


def _log(
    session_id: str,
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: Dict,
) -> None:
    """Pequeno helper de log em formato NDJSON para debug."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        payload = {
            "sessionId": session_id,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        # Não quebrar o app por causa de log.
        pass


_log(
    "debug-session",
    "run1",
    "INIT",
    "app.py:28",
    "Módulo carregado",
    {},
)
# #endregion

Card = int

RANK_SYMBOLS = "23456789TJQKA"
SUITS = ("s", "h", "d", "c")
CATEGORY_NAMES = {
    8: "Straight Flush",
    7: "Quadra",
    6: "Full House",
    5: "Flush",
    4: "Sequência",
    3: "Trinca",
    2: "Dois Pares",
    1: "Um Par",
    0: "Carta Alta",
}
EVALUATOR = Evaluator()
TREYS_CLASS_TO_CATEGORY = {
    0: 8,  # Royal Flush -> Straight Flush
    1: 8,  # Straight Flush
    2: 7,  # Four of a Kind -> Quadra
    3: 6,  # Full House
    4: 5,  # Flush
    5: 4,  # Straight
    6: 3,  # Three of a Kind
    7: 2,  # Two Pair
    8: 1,  # Pair
    9: 0,  # High Card
}

SUIT_SYMBOLS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
SUIT_TITLES = {
    "s": "Espadas ♠",
    "h": "Copas ♥",
    "d": "Ouros ♦",
    "c": "Paus ♣",
}
RANK_DISPLAY = {rank: rank for rank in RANK_SYMBOLS}
RANK_DISPLAY["T"] = "10"
STATE_ICONS = {
    "free": "⬜",
    "hero": "🟦",
    "board": "🟧",
    "opponent": "🟥",
}
TARGET_LABELS = {"hero": "Minha Mão", "board": "Mesa"}


def format_target_label(value: str) -> str:
    if value.startswith("opponent_"):
        suffix = value.split("_", 1)[1]
        return f"Oponente {suffix}"
    return TARGET_LABELS.get(value, value.title())


def category_label(category_value: int) -> str:
    return CATEGORY_NAMES.get(category_value, f"Categoria {category_value}")
CARD_STYLE_BLOCK = """
<style>
.card-marker {
    display: none;
}
div[data-testid="stElementContainer"]:has(.card-marker) + div[data-testid="stElementContainer"] button {
    width: 100%;
    min-width: 42px;
    min-height: 48px;
    font-size: 0.8rem;
    border-radius: 8px;
    border: 2px solid rgba(15, 23, 42, 0.22);
    background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,250,252,0.92));
    color: #0f172a;
    padding: 0.2rem;
    margin: 0.15rem 0;
}
div[data-testid="stElementContainer"]:has(.card-marker.state-hero) + div[data-testid="stElementContainer"] button {
    border-color: #2ecc71;
    box-shadow: 0 0 8px rgba(46, 204, 113, 0.5);
    background: linear-gradient(180deg, rgba(220, 252, 231, 0.95), rgba(187, 247, 208, 0.95));
}
div[data-testid="stElementContainer"]:has(.card-marker.state-board) + div[data-testid="stElementContainer"] button {
    border-color: #e74c3c;
    box-shadow: 0 0 8px rgba(231, 76, 60, 0.45);
    background: linear-gradient(180deg, rgba(254, 226, 226, 0.95), rgba(254, 202, 202, 0.95));
}
div[data-testid="stElementContainer"]:has(.card-marker.state-opponent) + div[data-testid="stElementContainer"] button {
    border-color: #4f83ff;
    box-shadow: 0 0 8px rgba(79, 131, 255, 0.45);
    background: linear-gradient(180deg, rgba(219, 234, 254, 0.95), rgba(191, 219, 254, 0.95));
}
div[data-testid="stElementContainer"]:has(.card-marker.state-free.suit-h) + div[data-testid="stElementContainer"] button,
div[data-testid="stElementContainer"]:has(.card-marker.state-free.suit-d) + div[data-testid="stElementContainer"] button {
    color: #b91c1c;
    border-color: rgba(185, 28, 28, 0.30);
}
div[data-testid="stElementContainer"]:has(.card-marker.state-free.suit-s) + div[data-testid="stElementContainer"] button,
div[data-testid="stElementContainer"]:has(.card-marker.state-free.suit-c) + div[data-testid="stElementContainer"] button {
    color: #0f172a;
    border-color: rgba(15, 23, 42, 0.22);
}
.slot-card {
    border: 1px dashed #343944;
    border-radius: 8px;
    padding: 0.35rem 0.5rem;
    min-height: 60px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: radial-gradient(520px 180px at 20% 20%, rgba(16, 185, 129, 0.12), rgba(15, 23, 42, 0.04)),
                rgba(255, 255, 255, 0.90);
    margin-bottom: 0.5rem;
}
.slot-card .slot-label {
    font-size: 0.7rem;
    color: #9ea4b3;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.slot-card .slot-value {
    font-size: 1rem;
    font-weight: 600;
    color: #0f172a;
}
.slot-card.filled.hero {
    border-style: solid;
    border-color: #2ecc71;
    background: linear-gradient(180deg, rgba(220, 252, 231, 0.92), rgba(187, 247, 208, 0.92));
}
.slot-card.filled.board {
    border-style: solid;
    border-color: #e74c3c;
    background: linear-gradient(180deg, rgba(254, 226, 226, 0.92), rgba(254, 202, 202, 0.92));
}
.slot-card.filled.opponent {
    border-style: solid;
    border-color: #4f83ff;
    background: linear-gradient(180deg, rgba(219, 234, 254, 0.92), rgba(191, 219, 254, 0.92));
}
</style>
"""

POKER_THEME_CSS = """
<style>
/* UI ONLY — visual / layout */

/* Page background (subtle felt) */
html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(1200px 700px at 30% 0%, rgba(18, 82, 55, 0.10), rgba(245, 247, 250, 1.0) 60%),
                linear-gradient(180deg, rgba(245, 247, 250, 1.0), rgba(242, 244, 247, 1.0));
}

/* Main width + spacing */
section.main > div.block-container {
    max-width: 1180px;
    padding-top: 1.2rem;
    padding-bottom: 2.0rem;
}

/* Sidebar (controls) */
section[data-testid="stSidebar"] > div {
    background: radial-gradient(900px 600px at 30% 0%, rgba(18, 82, 55, 0.18), rgba(248, 250, 252, 1.0) 65%),
                linear-gradient(180deg, rgba(248, 250, 252, 1.0), rgba(241, 245, 249, 1.0));
    border-right: 1px solid rgba(15, 23, 42, 0.08);
}

/* Typography */
html, body, [data-testid="stAppViewContainer"] {
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
    color: #0f172a;
}
h1, h2, h3, h4 {
    letter-spacing: -0.02em;
}

/* Section cards */
.poker-panel {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
}
.poker-panel h2, .poker-panel h3 {
    margin-top: 0.25rem;
}
.poker-panel::before {
    content: "";
    display: block;
    height: 3px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.85), rgba(234, 179, 8, 0.55), rgba(239, 68, 68, 0.55));
    margin-bottom: 10px;
    opacity: 0.75;
}
.poker-subtle {
    color: rgba(15, 23, 42, 0.70);
}

/* Primary action marker (only the "Calcular" button) */
.calc-marker { display: none; }
div[data-testid="stElementContainer"]:has(.calc-marker) + div[data-testid="stElementContainer"] button {
    border-radius: 12px !important;
    border: 1px solid rgba(15, 23, 42, 0.14) !important;
    box-shadow: 0 10px 18px rgba(15, 23, 42, 0.08) !important;
    background: linear-gradient(180deg, rgba(16, 185, 129, 0.95), rgba(5, 150, 105, 0.95)) !important;
    color: #052e1b !important;
    font-weight: 700 !important;
    letter-spacing: 0.01em !important;
}
div[data-testid="stElementContainer"]:has(.calc-marker) + div[data-testid="stElementContainer"] button:hover {
    filter: brightness(1.03);
    border-color: rgba(15, 23, 42, 0.22) !important;
}

/* Expanders — clean analysis section */
details[data-testid="stExpander"] {
    border-radius: 12px;
    border: 1px solid rgba(15, 23, 42, 0.08);
    background: rgba(255, 255, 255, 0.75);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
}
details[data-testid="stExpander"] > summary {
    padding: 0.65rem 0.85rem;
    font-weight: 700;
}

/* Equity cards */
.equity-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-top: 8px;
}
.equity-card {
    border-radius: 12px;
    padding: 10px 12px;
    border: 1px solid rgba(15, 23, 42, 0.10);
    background: rgba(255, 255, 255, 0.90);
}
.equity-card .label {
    font-size: 0.80rem;
    font-weight: 600;
    color: rgba(15, 23, 42, 0.72);
    margin-bottom: 2px;
}
.equity-card .value {
    font-size: 1.75rem;
    font-weight: 800;
    line-height: 1.1;
}
.equity-card .sub {
    font-size: 0.75rem;
    color: rgba(15, 23, 42, 0.62);
    margin-top: 2px;
}
.equity-card.win { border-left: 5px solid rgba(34, 197, 94, 0.85); }
.equity-card.tie { border-left: 5px solid rgba(234, 179, 8, 0.85); }
.equity-card.lose { border-left: 5px solid rgba(239, 68, 68, 0.85); }
.equity-card.win .value { color: rgba(21, 128, 61, 0.95); }
.equity-card.tie .value { color: rgba(161, 98, 7, 0.95); }
.equity-card.lose .value { color: rgba(185, 28, 28, 0.95); }

/* Inputs — tighter, pro look */
div[data-testid="stSlider"] {
    padding-top: 0.15rem;
}
div[data-testid="stRadio"] label {
    font-weight: 600;
}

/* Responsive: stack equity cards on narrow screens */
@media (max-width: 860px) {
  .equity-grid { grid-template-columns: 1fr; }
}
</style>
"""


def trigger_rerun() -> None:
    """Dispara um rerun compatível com versões antigas do Streamlit."""
    rerun_fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if rerun_fn:
        rerun_fn()


def running_on_streamlit_cloud() -> bool:
    """Detecta execução no Streamlit Cloud usando apenas variáveis de ambiente.

    O uso de ``st.secrets`` é evitado por completo porque esse objeto não existe
    quando o app roda localmente e não deve ser usado para lógica de execução.
    """
    return os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"


def allow_parallel_workers() -> bool:
    """Permite multiprocessing apenas fora do Streamlit Cloud."""
    if running_on_streamlit_cloud():
        return False
    cpu_count = os.cpu_count() or 1
    return cpu_count > 1


@st.cache_resource(show_spinner=False)
def build_card_grid() -> Dict[str, List[Dict[str, object]]]:
    """Cria metadados do baralho para desenhar a grade visual."""
    grid: Dict[str, List[Dict[str, object]]] = {}
    for suit in SUITS:
        entries: List[Dict[str, object]] = []
        for rank in RANK_SYMBOLS:
            notation = f"{rank}{suit}"
            entries.append(
                {
                    "notation": notation,
                    "card": TreysCard.new(notation),
                    "label": f"{RANK_DISPLAY.get(rank, rank)}{SUIT_SYMBOLS[suit]}",
                }
            )
        grid[suit] = entries
    return grid


CARD_GRID = build_card_grid()


@dataclass
class SelectionState:
    hero: List[Card]
    board: List[Card]
    opponents: Dict[int, List[Card]]

    def all_selected(self) -> List[Card]:
        cards: List[Card] = []
        cards.extend(self.hero)
        cards.extend(self.board)
        for opp_cards in self.opponents.values():
            cards.extend(opp_cards)
        return cards


def ensure_state() -> SelectionState:
    """Inicializa SelectionState no session_state se necessário."""
    if "selection_state" not in st.session_state:
        st.session_state["selection_state"] = SelectionState(hero=[], board=[], opponents={})
    state: SelectionState = st.session_state["selection_state"]
    # Normaliza para listas mutáveis sempre presentes.
    state.hero = list(state.hero)
    state.board = list(state.board)
    state.opponents = {int(k): list(v) for k, v in state.opponents.items()}
    st.session_state["selection_state"] = state
    return state


def card_owner(card: Card, state: SelectionState) -> Tuple[str, Optional[int]]:
    """Retorna ('hero', None), ('board', idx) ou ('opponent', opp_id) para uma carta."""
    if card in state.hero:
        return "hero", None
    if card in state.board:
        return "board", state.board.index(card)
    for opp_id, cards in state.opponents.items():
        if card in cards:
            return "opponent", opp_id
    return "free", None


def remove_card_from_state(card: Card, state: SelectionState) -> None:
    """Remove a carta do destino atual, se existir."""
    owner, data = card_owner(card, state)
    if owner == "hero":
        state.hero.remove(card)
    elif owner == "board":
        state.board.remove(card)
    elif owner == "opponent" and data is not None:
        state.opponents[data].remove(card)


def get_board_slot_label(index: int) -> str:
    labels = ["Flop 1", "Flop 2", "Flop 3", "Turn", "River"]
    if 0 <= index < len(labels):
        return labels[index]
    return f"Carta {index + 1}"


def sync_opponent_slots(state: SelectionState, enabled: bool, desired_count: int) -> None:
    """Ajusta o dicionário de oponentes de acordo com o modo desejado."""
    if not enabled:
        state.opponents = {}
        return
    for opp_id in list(state.opponents.keys()):
        if opp_id > desired_count:
            del state.opponents[opp_id]
    for opp_id in range(1, desired_count + 1):
        state.opponents.setdefault(opp_id, [])


def card_status_label(card: Card, state: SelectionState) -> Tuple[str, str]:
    """Retorna (owner, descrição resumida) para exibição na grade."""
    owner, data = card_owner(card, state)
    if owner == "hero":
        slot = state.hero.index(card) + 1
        return owner, f"Hero {slot}"
    if owner == "board":
        idx = state.board.index(card)
        return owner, get_board_slot_label(idx)
    if owner == "opponent" and data is not None:
        slot = state.opponents[data].index(card) + 1
        return owner, f"Opp {data}-{slot}"
    return "free", "Livre"


def assign_card_to_target(card: Card, target: str, state: SelectionState, tournament_enabled: bool) -> Optional[str]:
    """Atribui a carta conforme o destino ativo. Retorna mensagem de erro opcional."""
    if target == "hero":
        if len(state.hero) >= 2:
            return "O Hero já possui 2 cartas."
        state.hero.append(card)
        return None
    if target == "board":
        if len(state.board) >= 5:
            return "A mesa já possui 5 cartas."
        state.board.append(card)
        return None
    if target.startswith("opponent_"):
        if not tournament_enabled:
            return "Habilite o modo torneio para atribuir cartas aos oponentes."
        try:
            opp_id = int(target.split("_", 1)[1])
        except (IndexError, ValueError):
            return "Destino inválido para oponente."
        cards = state.opponents.setdefault(opp_id, [])
        if len(cards) >= 2:
            return f"Oponente {opp_id} já possui 2 cartas."
        state.opponents[opp_id].append(card)
        return None
    return "Selecione um destino válido para a carta."


def handle_card_click(card: Card, target: str, state: SelectionState, tournament_enabled: bool) -> Optional[str]:
    """Processa clique no deck: remove se já ocupada ou adiciona ao destino ativo."""
    owner, _ = card_owner(card, state)
    _log(
        "debug-session",
        "run1",
        "UI",
        "app.py:312",
        "card click",
        {"card": TreysCard.int_to_str(card), "owner": owner, "target": target},
    )
    if owner != "free":
        remove_card_from_state(card, state)
        st.session_state["selection_state"] = state
        trigger_rerun()
        return None
    error = assign_card_to_target(card, target, state, tournament_enabled)
    st.session_state["selection_state"] = state
    if error is None:
        trigger_rerun()
    return error


def build_target_options(tournament_enabled: bool, opponents: int) -> List[str]:
    options = ["hero", "board"]
    if tournament_enabled:
        for opp_id in range(1, opponents + 1):
            options.append(f"opponent_{opp_id}")
    return options


def render_card_button(meta: Dict[str, object], state: SelectionState, tournament_enabled: bool, active_target: str) -> None:
    card = meta["card"]
    owner, description = card_status_label(card, state)
    suit = meta["notation"][-1]
    label = meta["label"]
    button_key = f"card_btn_{meta['notation']}"
    st.markdown(
        f"<div class='card-marker state-{owner} suit-{suit}'></div>",
        unsafe_allow_html=True,
    )
    clicked = st.button(
        label,
        key=button_key,
        use_container_width=True,
    )
    if clicked:
        feedback = handle_card_click(card, active_target, state, tournament_enabled)
        if feedback:
            st.session_state["deck_feedback"] = feedback


def render_card_deck(state: SelectionState, active_target: str, tournament_enabled: bool) -> None:
    """Exibe a grade visual do baralho completo."""
    deck_container = st.container()
    deck_container.markdown(CARD_STYLE_BLOCK, unsafe_allow_html=True)
    caption = "Clique nas cartas para atribuir ou remover. Limites: Hero 2 cartas, Mesa até 5 cartas."
    if tournament_enabled:
        caption += " Oponentes conhecidos: 2 cartas cada."
    deck_container.caption(caption)
    for suit in SUITS:
        row = deck_container.container()
        row.markdown(f"**{SUIT_TITLES[suit]}**")
        cols = row.columns(len(CARD_GRID[suit]))
        for idx, meta in enumerate(CARD_GRID[suit]):
            with cols[idx].container():
                render_card_button(meta, state, tournament_enabled, active_target)


def parse_card(card_text: str) -> Card:
    """Converte texto como 'As' ou '10h' em uma representação interna (valor, naipe)."""
    token = card_text.strip().lower()
    if len(token) < 2:
        raise ValueError(f"Carta inválida: '{card_text}'")

    suit = token[-1]
    rank_token = token[:-1]

    if suit not in SUITS:
        raise ValueError(f"Naipe inválido na carta '{card_text}'")

    rank_token = rank_token.replace("10", "t").upper()
    if len(rank_token) != 1 or rank_token not in RANK_SYMBOLS:
        raise ValueError(f"Valor inválido na carta '{card_text}'")

    treys_notation = f"{rank_token}{suit}"
    return TreysCard.new(treys_notation)


@st.cache_data(show_spinner=False)
def build_deck() -> Tuple[Card, ...]:
    """Retorna um novo baralho padrão de 52 cartas."""
    deck = []
    for rank in RANK_SYMBOLS:
        for suit in SUITS:
            deck.append(TreysCard.new(f"{rank}{suit}"))
    return tuple(deck)


def remove_known_cards(deck: Sequence[Card], known_cards: Sequence[Card]) -> List[Card]:
    """Remove cartas já conhecidas (Hero + mesa) do baralho restante."""
    known_set = set(known_cards)
    return [card for card in deck if card not in known_set]


def best_hand_rank_7(cards: Sequence[Card], board_cards: Optional[Sequence[Card]] = None) -> Tuple[int, int]:
    """Determina o ranking de uma mão usando o avaliador Treys."""
    _log(
        "debug-session",
        "run1",
        "RANK",
        "app.py:75",
        "best_hand_rank_7 entrada",
        {"len_cards": len(cards), "len_board": 0 if board_cards is None else len(board_cards)},
    )
    if board_cards is None:
        if len(cards) < 5:
            raise ValueError(f"best_hand_rank_7 precisa de pelo menos 5 cartas, recebeu {len(cards)}")
        hand = list(cards[:2])
        board = list(cards[2:])
    else:
        if len(cards) < 2:
            raise ValueError("Informe pelo menos duas cartas da mão do jogador.")
        hand = cards if isinstance(cards, list) else list(cards)
        board = board_cards if isinstance(board_cards, list) else list(board_cards)
        if len(hand) + len(board) < 5:
            raise ValueError("São necessárias ao menos 5 cartas combinadas para avaliar a mão.")

    rank_value = EVALUATOR.evaluate(hand, board)
    class_int = EVALUATOR.get_rank_class(rank_value)
    category = TREYS_CLASS_TO_CATEGORY[class_int]
    result = (category, -rank_value)
    _log(
        "debug-session",
        "run1",
        "RANK",
        "app.py:89",
        "best_hand_rank_7 saída",
        {"result": result},
    )
    return result


def board_only_rank_value(board_cards: Sequence[Card]) -> Optional[Tuple[int, int]]:
    """Retorna o ranking apenas das cartas do board (5 cartas)."""
    if len(board_cards) < 5:
        return None
    board_list = list(board_cards)
    hand_cards = board_list[:2]
    community = board_list[2:]
    return best_hand_rank_7(hand_cards, community)


def format_card(card: Card) -> str:
    """Representação amigável usando símbolos de naipe."""
    notation = TreysCard.int_to_str(card)
    if len(notation) < 2:
        return notation.upper()
    rank_token = notation[0].upper()
    suit_token = notation[1].lower()
    rank_display = RANK_DISPLAY.get(rank_token, rank_token)
    suit_display = SUIT_SYMBOLS.get(suit_token, suit_token)
    return f"{rank_display}{suit_display}"


def format_hand(cards: Sequence[Card]) -> str:
    """Ordena as cartas do oponente por força para exibição."""
    sorted_cards = sorted(cards, key=lambda c: TreysCard.get_rank_int(c), reverse=True)
    return " ".join(format_card(card) for card in sorted_cards)


@st.cache_resource(show_spinner=False)
def get_monte_carlo_pool(max_workers: Optional[int] = None) -> Optional[ProcessPoolExecutor]:
    """Cria (e cacheia) um pool de workers para o Monte Carlo no modo rápido."""
    workers = max_workers or (os.cpu_count() or 1)
    if workers < 2:
        return None
    return ProcessPoolExecutor(max_workers=workers)


def _mc_worker_fast(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    num_opponents: int,
    known_opponents: Sequence[Sequence[Card]],
    deck_remaining: Sequence[Card],
    iterations: int,
    seed: int,
) -> Tuple[int, int, int]:
    """Processa um lote de iterações Monte Carlo retornando apenas win/tie/loss."""
    rng = random.Random(seed)
    hero = list(hero_cards)
    board_base = list(board_cards)
    missing_board = max(0, 5 - len(board_base))
    board_buffer = board_base + [0] * missing_board
    base_len = len(board_base)
    known = [tuple(cards) for cards in known_opponents]
    random_opponents = num_opponents - len(known)
    if random_opponents < 0:
        raise ValueError("Worker recebeu mais oponentes conhecidos que o total configurado.")
    deck_buffer = list(deck_remaining)
    wins = ties = losses = 0
    for _ in range(iterations):
        rng.shuffle(deck_buffer)
        for idx in range(missing_board):
            board_buffer[base_len + idx] = deck_buffer[idx]
        hero_rank = best_hand_rank_7(hero, board_buffer)
        best_opponent_rank: Tuple[int, int] = (-1, 0)
        for opp_cards in known:
            rank = best_hand_rank_7(opp_cards, board_buffer)
            if rank > best_opponent_rank:
                best_opponent_rank = rank
        offset = missing_board
        for _ in range(random_opponents):
            card_a = deck_buffer[offset]
            card_b = deck_buffer[offset + 1]
            offset += 2
            rank = best_hand_rank_7((card_a, card_b), board_buffer)
            if rank > best_opponent_rank:
                best_opponent_rank = rank
        if hero_rank > best_opponent_rank:
            wins += 1
        elif hero_rank == best_opponent_rank:
            ties += 1
        else:
            losses += 1
    return wins, ties, losses


def _run_parallel_fast(
    pool: ProcessPoolExecutor,
    hero_cards: Tuple[Card, ...],
    board_cards: Tuple[Card, ...],
    num_opponents: int,
    known_opponents: Tuple[Tuple[Card, ...], ...],
    deck_remaining: Tuple[Card, ...],
    max_seconds: float,
    chunk_iterations: int,
) -> Tuple[int, int, int, float, Dict[str, object]]:
    """Executa Monte Carlo rápido em paralelo agregando contadores."""
    start = time.perf_counter()
    rng = random.Random()
    chunk_iterations = max(200, chunk_iterations)

    def submit_one() -> Future:
        seed = rng.randrange(1, 1_000_000_000)
        return pool.submit(
            _mc_worker_fast,
            hero_cards,
            board_cards,
            num_opponents,
            known_opponents,
            deck_remaining,
            chunk_iterations,
            seed,
        )

    max_workers = getattr(pool, "_max_workers", os.cpu_count() or 1)
    active: List[Future] = []
    for _ in range(max_workers):
        active.append(submit_one())

    wins = ties = losses = 0
    chunks = 0
    while active:
        future = next(as_completed(active))
        active.remove(future)
        worker_result = future.result()
        wins += worker_result[0]
        ties += worker_result[1]
        losses += worker_result[2]
        chunks += 1
        if time.perf_counter() - start < max_seconds:
            active.append(submit_one())
    elapsed = time.perf_counter() - start
    profile = {
        "parallel_workers": getattr(pool, "_max_workers", None),
        "chunks": chunks,
        "deal_board": 0.0,
        "deal_opponents": 0.0,
        "evaluate": 0.0,
        "compare": 0.0,
        "iter_per_sec_initial": 0.0,
    }
    return wins, ties, losses, elapsed, profile


def _build_result_dict(
    wins: int,
    ties: int,
    losses: int,
    category_counter: Counter,
    loss_category_counter: Counter,
    losing_examples_data: Dict[int, Counter],
) -> Dict[str, object]:
    """Normaliza contadores em um dicionário de resultado padrão."""
    total = wins + ties + losses
    if total <= 0:
        raise ValueError("Nenhum cenário válido calculado.")
    win_pct = wins / total * 100
    tie_pct = ties / total * 100
    loss_pct = max(0.0, 100.0 - (win_pct + tie_pct))
    most_common_category = category_counter.most_common(1)
    sorted_loss_categories = [
        CATEGORY_NAMES.get(category_value)
        for category_value, _ in sorted(loss_category_counter.items(), key=lambda item: item[0], reverse=True)
        if CATEGORY_NAMES.get(category_value)
    ]
    losing_category_examples = []
    for category_value, hands_counter in sorted(
        losing_examples_data.items(), key=lambda item: item[0], reverse=True
    ):
        name = CATEGORY_NAMES.get(category_value)
        if not name:
            continue
        losing_category_examples.append(
            {"name": name, "hands": [hand for hand, _ in hands_counter.most_common(3)]}
        )
    return {
        "win_pct": win_pct,
        "tie_pct": tie_pct,
        "loss_pct": loss_pct,
        "most_likely_category": CATEGORY_NAMES.get(most_common_category[0][0]) if most_common_category else None,
        "losing_categories": sorted_loss_categories,
        "losing_examples": losing_category_examples,
        "total_scenarios": total,
        "counts": {"win": wins, "tie": ties, "loss": losses},
    }


def build_fast_mode_result(wins: int, ties: int, losses: int) -> Dict[str, object]:
    """Estrutura o resultado para o modo rápido (sem breakdown)."""
    total = wins + ties + losses
    if total <= 0:
        raise ValueError("Nenhum cenário válido simulado.")
    win_pct = wins / total * 100
    tie_pct = ties / total * 100
    loss_pct = 100.0 - (win_pct + tie_pct)
    return {
        "win_pct": win_pct,
        "tie_pct": tie_pct,
        "loss_pct": loss_pct,
        "losing_categories": [],
        "losing_examples": [],
        "total_scenarios": total,
        "counts": {"win": wins, "tie": ties, "loss": losses},
        "loss_breakdown": None,
        "tie_breakdown": None,
        "hero_most_common_category": None,
        "hero_most_common_category_wins": None,
    }


def _compute_confidence_intervals(wins: int, ties: int, losses: int, total: int) -> Dict[str, Dict[str, float]]:
    """Retorna IC95% (em %) para Win/Tie/Loss."""
    if total <= 0:
        return {}
    intervals: Dict[str, Dict[str, float]] = {}
    for label, count in (("win", wins), ("tie", ties), ("loss", losses)):
        p = count / total
        se = math.sqrt(p * (1 - p) / total)
        margin = 1.96 * se
        low = max(0.0, p - margin) * 100
        high = min(1.0, p + margin) * 100
        intervals[label] = {"low": low, "high": high, "se": se}
    return intervals


# Stats: CI only for MC
def compute_ci95(
    method: Literal["exact", "monte_carlo"],
    wins: int,
    ties: int,
    losses: int,
    n_samples: int,
) -> Optional[Dict[str, Dict[str, float]]]:
    """Calcula IC95% apenas quando o método é Monte Carlo."""
    if method != "monte_carlo" or n_samples <= 0:
        return None
    return _compute_confidence_intervals(wins, ties, losses, n_samples)


# UI: EXACT vs MC
def build_display_result(
    method: Literal["exact", "monte_carlo"],
    result: Dict[str, object],
    meta: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Normaliza a estrutura exibida na UI sem alterar os números de equity."""
    counts = result.get("counts") or {}
    wins = int(counts.get("win", 0))
    ties = int(counts.get("tie", 0))
    losses = int(counts.get("loss", 0))

    n_samples = 0
    elapsed_s: Optional[float] = None
    it_per_s: Optional[float] = None
    if method == "monte_carlo" and meta:
        n_samples = int(meta.get("iterations", wins + ties + losses))
        elapsed_s = float(meta.get("elapsed", 0.0))
        it_per_s = float(meta.get("iter_per_sec", 0.0))
    else:
        n_samples = int(result.get("total_scenarios", wins + ties + losses))
        if meta and "elapsed" in meta:
            elapsed_s = float(meta.get("elapsed", 0.0))
            it_per_s = (n_samples / elapsed_s) if elapsed_s and elapsed_s > 0 else None

    ci = compute_ci95(method, wins, ties, losses, n_samples)

    return {
        "method": method,
        "win": float(result.get("win_pct", 0.0)),
        "tie": float(result.get("tie_pct", 0.0)),
        "lose": float(result.get("loss_pct", 0.0)),
        "win_count": wins,
        "tie_count": ties,
        "lose_count": losses,
        "n_samples": n_samples,
        "elapsed_s": elapsed_s,
        "it_per_s": it_per_s,
        "ci95_win": None if not ci else {"low": ci["win"]["low"], "high": ci["win"]["high"]},
        "ci95_tie": None if not ci else {"low": ci["tie"]["low"], "high": ci["tie"]["high"]},
        "ci95_lose": None if not ci else {"low": ci["loss"]["low"], "high": ci["loss"]["high"]},
    }


def build_loss_breakdown(
    loss_category_counter: Counter,
    loss_winner_counter: Counter,
) -> Dict[str, List[Dict[str, object]]]:
    categories = [
        {"category": category_label(category_value), "count": count}
        for category_value, count in loss_category_counter.most_common()
    ]
    winners = [
        {"category": category_label(category_value), "opponent": opponent_label, "count": count}
        for (category_value, opponent_label), count in loss_winner_counter.most_common()
    ]
    return {"categories": categories, "winners": winners}


def build_tie_breakdown(
    tie_category_counter: Counter,
    tie_size_counter: Counter,
    board_only_ties: int,
) -> Dict[str, object]:
    categories = [
        {"category": category_label(category_value), "count": count}
        for category_value, count in tie_category_counter.most_common()
    ]
    sizes = [{"players": size, "count": count} for size, count in tie_size_counter.most_common()]
    return {"categories": categories, "players": sizes, "board_only_ties": board_only_ties}


def render_slot_group(title: str, cards: Sequence[Card], max_cards: int, slot_type: str) -> None:
    """Exibe visualmente um grupo de slots (Hero ou Board)."""
    cols = st.columns(max_cards)
    for idx in range(max_cards):
        filled = idx < len(cards)
        label = get_board_slot_label(idx) if slot_type == "board" else f"{title} {idx + 1}"
        value = format_card(cards[idx]) if filled else "Selecione"
        classes = ["slot-card", slot_type]
        if filled:
            classes.append("filled")
        html = (
            f"<div class='{' '.join(classes)}'>"
            f"<div class='slot-label'>{label}</div>"
            f"<div class='slot-value'>{value}</div>"
            "</div>"
        )
        cols[idx].markdown(html, unsafe_allow_html=True)


def normalize_known_opponents_entries(
    known_entries: Optional[Sequence[Sequence[Card]]],
) -> Tuple[List[List[Card]], List[str]]:
    """Normaliza entradas dos oponentes conhecidos em (cartas, rótulos)."""
    cards: List[List[Card]] = []
    labels: List[str] = []
    if not known_entries:
        return cards, labels
    for idx, entry in enumerate(known_entries):
        opp_id = idx + 1
        cards_seq = entry
        if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], int):
            opp_id = entry[0]
            cards_seq = entry[1]
        cards_list = list(cards_seq)
        cards.append(cards_list)
        labels.append(f"Oponente {opp_id}")
    return cards, labels


def render_opponent_sections(state: SelectionState, opponent_count: int) -> None:
    """Renderiza slots dos oponentes conhecidos."""
    if opponent_count <= 0:
        return
    st.markdown("**Oponentes conhecidos**")
    for start in range(1, opponent_count + 1, 2):
        cols = st.columns(min(2, opponent_count - start + 1))
        for offset, col in enumerate(cols):
            opp_id = start + offset
            with col:
                st.markdown(f"**Oponente {opp_id}**")
                render_slot_group(f"OPP {opp_id}", state.opponents.get(opp_id, []) or [], 2, "opponent")


def choose_equity_method(board_cards: Sequence[Card]) -> Literal["EXACT", "MONTE_CARLO"]:
    """Define o método (EXACT ou MONTE_CARLO) com base nas cartas comunitárias conhecidas."""
    missing = 5 - len(board_cards)
    if missing <= 2:
        return "EXACT"
    return "MONTE_CARLO"


def estimate_exact_scenarios(deck_size: int, missing_board: int, random_opponents: int) -> int:
    """Estimativa do número de cenários do modo exato (usado para evitar travar a UI)."""
    if deck_size < 0 or missing_board < 0 or random_opponents < 0:
        return 0
    if missing_board > deck_size:
        return 0
    cards_for_opponents = 2 * random_opponents
    remaining = deck_size - missing_board
    if cards_for_opponents > remaining:
        return 0
    return math.comb(deck_size, missing_board) * math.comb(remaining, cards_for_opponents)


@st.cache_data(show_spinner=False)
def simulate_exact(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    num_opponents: int,
    known_opponents: Optional[Sequence[Sequence[Card]]] = None,
) -> Dict[str, float]:
    """Enumera exaustivamente as cartas faltantes do board para um resultado determinístico."""
    hero_cards = list(hero_cards)
    board_cards = list(board_cards)
    known_cards, known_labels = normalize_known_opponents_entries(known_opponents)
    flattened_known: List[Card] = []
    for opp_cards in known_cards:
        if len(opp_cards) != 2:
            raise ValueError("Cada oponente conhecido deve possuir exatamente 2 cartas.")
        flattened_known.extend(opp_cards)
    missing_board = 5 - len(board_cards)
    if missing_board < 0:
        raise ValueError("A mesa não pode conter mais de 5 cartas.")
    if missing_board > 2:
        raise ValueError("Enumeração exata só suporta até 2 cartas faltando.")
    _log(
        "debug-session",
        "run1",
        "SIM",
        "app.py:542",
        "simulate_exact entrada",
        {
            "len_hero": len(hero_cards),
            "len_board": len(board_cards),
            "num_opponents": num_opponents,
            "known_opponents": len(known_cards),
        },
    )
    deck = remove_known_cards(build_deck(), hero_cards + board_cards + flattened_known)
    random_opponents = num_opponents - len(known_cards)
    if random_opponents < 0:
        raise ValueError("Número de oponentes conhecidos maior que o total configurado.")
    cards_needed = missing_board + 2 * random_opponents
    if cards_needed > len(deck):
        raise ValueError("Cartas insuficientes para completar o cálculo.")
    wins = ties = losses = 0
    hero_category_counter: Counter = Counter()
    hero_win_category_counter: Counter = Counter()
    loss_category_counter: Counter = Counter()
    loss_winner_counter: Counter = Counter()
    losing_examples_data: Dict[int, Counter] = defaultdict(Counter)
    tie_category_counter: Counter = Counter()
    tie_size_counter: Counter = Counter()
    board_only_ties = 0
    random_labels = [f"Oponente {len(known_labels) + idx + 1}" for idx in range(random_opponents)]

    for board_draw in combos(deck, missing_board):
        simulated_board = list(board_cards) + list(board_draw)
        remaining_deck = [card for card in deck if card not in board_draw]
        hero_rank = best_hand_rank_7(hero_cards, simulated_board)
        board_rank = board_only_rank_value(simulated_board)

        base_known_hands: List[Tuple[Tuple[int, int], List[Card], str]] = []
        for idx, opp_cards in enumerate(known_cards):
            rank = best_hand_rank_7(opp_cards, simulated_board)
            label = known_labels[idx]
            base_known_hands.append((rank, list(opp_cards), label))

        for opp_combo in combos(remaining_deck, 2 * random_opponents):
            opponent_cards_iter = iter(opp_combo)
            temp_opponent_hands = list(base_known_hands)
            for rand_idx in range(random_opponents):
                pair = [next(opponent_cards_iter), next(opponent_cards_iter)]
                rank = best_hand_rank_7(pair, simulated_board)
                label = random_labels[rand_idx]
                temp_opponent_hands.append((rank, pair, label))

            best_opponent_rank, best_opponent_cards, best_label = (
                max(temp_opponent_hands, key=lambda item: item[0]) if temp_opponent_hands else ((-1, 0), [], "")
            )
            hero_category_counter[hero_rank[0]] += 1
            if hero_rank > best_opponent_rank:
                wins += 1
                hero_win_category_counter[hero_rank[0]] += 1
            elif hero_rank == best_opponent_rank:
                ties += 1
                tie_category_counter[hero_rank[0]] += 1
                tied_players = 1 + sum(1 for entry in temp_opponent_hands if entry[0] == hero_rank)
                tie_size_counter[tied_players] += 1
                if board_rank and board_rank == hero_rank:
                    board_only_ties += 1
            else:
                losses += 1
                loss_category_value = best_opponent_rank[0]
                loss_category_counter[loss_category_value] += 1
                loss_winner_counter[(loss_category_value, best_label or "Oponente desconhecido")] += 1
                if best_opponent_cards:
                    formatted = format_hand(best_opponent_cards)
                    losing_examples_data[loss_category_value][formatted] += 1

    if wins != sum(hero_win_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar vitórias do Hero.")
    if losses != sum(loss_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar derrotas do Hero.")
    if ties != sum(tie_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar empates do Hero.")

    result = _build_result_dict(
        wins,
        ties,
        losses,
        hero_category_counter,
        loss_category_counter,
        losing_examples_data,
    )
    result["hero_most_common_category"] = (
        category_label(hero_category_counter.most_common(1)[0][0]) if hero_category_counter else None
    )
    result["hero_most_common_category_wins"] = (
        category_label(hero_win_category_counter.most_common(1)[0][0]) if hero_win_category_counter else None
    )
    result["loss_breakdown"] = build_loss_breakdown(loss_category_counter, loss_winner_counter)
    result["tie_breakdown"] = build_tie_breakdown(tie_category_counter, tie_size_counter, board_only_ties)
    # Stats: CI only for MC
    result["confidence"] = None
    _log(
        "debug-session",
        "run1",
        "SIM",
        "app.py:570",
        "simulate_exact saída",
        {
            "result": result,
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "total": result.get("total_scenarios"),
        },
    )
    return result


def simulate_monte_carlo(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    num_opponents: int,
    time_budget: float,
    known_opponents: Optional[Sequence[Sequence[Card]]] = None,
    batch_size: int = 2000,
    collect_breakdown: bool = False,
    use_parallel: bool = False,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Delegador que escolhe o modo rápido ou o modo análise."""
    if collect_breakdown:
        return simulate_monte_carlo_analysis(
            hero_cards,
            board_cards,
            num_opponents,
            time_budget,
            known_opponents,
            batch_size,
        )
    return simulate_monte_carlo_fast(
        hero_cards,
        board_cards,
        num_opponents,
        time_budget,
        known_opponents,
        batch_size,
        use_parallel,
    )


def simulate_monte_carlo_fast(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    num_opponents: int,
    time_budget: float,
    known_opponents: Optional[Sequence[Sequence[Card]]] = None,
    batch_size: int = 2000,
    use_parallel: bool = False,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Modo rápido: apenas win/tie/lose, sem Counters ou estruturas extras no hot loop."""
    hero_tuple = tuple(hero_cards)
    board_tuple = tuple(board_cards)
    known_cards, _ = normalize_known_opponents_entries(known_opponents)
    flattened_known: List[Card] = []
    for opp_cards in known_cards:
        if len(opp_cards) != 2:
            raise ValueError("Cada oponente conhecido deve possuir exatamente 2 cartas.")
        flattened_known.extend(opp_cards)
    deck = remove_known_cards(build_deck(), hero_tuple + board_tuple + tuple(flattened_known))
    missing_board = 5 - len(board_tuple)
    random_opponents = num_opponents - len(known_cards)
    if random_opponents < 0:
        raise ValueError("Número de oponentes conhecidos maior que o total configurado.")
    cards_needed = missing_board + 2 * random_opponents
    if cards_needed > len(deck):
        raise ValueError("Cartas insuficientes para completar a simulação.")
    max_seconds = max(0.5, min(time_budget, 10.0))
    batch_size = max(200, batch_size)
    if use_parallel:
        pool = get_monte_carlo_pool()
        if pool:
            wins, ties, losses, elapsed_parallel, profile = _run_parallel_fast(
                pool,
                hero_tuple,
                board_tuple,
                num_opponents,
                tuple(tuple(cards) for cards in known_cards),
                tuple(deck),
                max_seconds,
                batch_size,
            )
            result = build_fast_mode_result(wins, ties, losses)
            result["confidence"] = _compute_confidence_intervals(wins, ties, losses, result["total_scenarios"])
            meta = {
                "iterations": wins + ties + losses,
                "elapsed": elapsed_parallel,
                "iter_per_sec": (wins + ties + losses) / elapsed_parallel if elapsed_parallel > 0 else 0.0,
                "time_budget": max_seconds,
                "analysis_mode": False,
                "profile": profile,
            }
            result["mc_meta"] = meta
            return result, meta
    # Single-process hot loop.
    hero_list = list(hero_tuple)
    board_base = list(board_tuple)
    board_extra = [0] * missing_board
    board_buffer = board_base + board_extra
    base_len = len(board_base)
    deck_buffer = list(deck)
    start = time.perf_counter()
    wins = ties = losses = 0
    iterations = 0
    while time.perf_counter() - start < max_seconds:
        for _ in range(batch_size):
            if time.perf_counter() - start >= max_seconds:
                break
            random.shuffle(deck_buffer)
            for idx in range(missing_board):
                board_buffer[base_len + idx] = deck_buffer[idx]
            hero_rank = best_hand_rank_7(hero_list, board_buffer)
            best_opponent_rank: Tuple[int, int] = (-1, 0)
            for opp_cards in known_cards:
                rank = best_hand_rank_7(opp_cards, board_buffer)
                if rank > best_opponent_rank:
                    best_opponent_rank = rank
            offset = missing_board
            for _ in range(random_opponents):
                card_a = deck_buffer[offset]
                card_b = deck_buffer[offset + 1]
                offset += 2
                rank = best_hand_rank_7((card_a, card_b), board_buffer)
                if rank > best_opponent_rank:
                    best_opponent_rank = rank
            if hero_rank > best_opponent_rank:
                wins += 1
            elif hero_rank == best_opponent_rank:
                ties += 1
            else:
                losses += 1
            iterations += 1
    elapsed = time.perf_counter() - start
    result = build_fast_mode_result(wins, ties, losses)
    result["confidence"] = _compute_confidence_intervals(wins, ties, losses, result["total_scenarios"])
    meta = {
        "iterations": iterations,
        "elapsed": elapsed,
        "iter_per_sec": iterations / elapsed if elapsed > 0 else 0.0,
        "time_budget": max_seconds,
        "analysis_mode": False,
        "profile": {},
    }
    result["mc_meta"] = meta
    return result, meta


def simulate_monte_carlo_analysis(
    hero_cards: Sequence[Card],
    board_cards: Sequence[Card],
    num_opponents: int,
    time_budget: float,
    known_opponents: Optional[Sequence[Sequence[Card]]] = None,
    batch_size: int = 2000,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Modo análise: coleta completa de breakdowns."""
    hero_cards = list(hero_cards)
    board_cards = list(board_cards)
    known_cards, known_labels = normalize_known_opponents_entries(known_opponents)
    flattened_known: List[Card] = []
    for opp_cards in known_cards:
        if len(opp_cards) != 2:
            raise ValueError("Cada oponente conhecido deve possuir exatamente 2 cartas.")
        flattened_known.extend(opp_cards)
    deck = remove_known_cards(build_deck(), hero_cards + board_cards + flattened_known)
    missing_board = 5 - len(board_cards)
    random_opponents = num_opponents - len(known_cards)
    if random_opponents < 0:
        raise ValueError("Número de oponentes conhecidos maior que o total configurado.")
    cards_needed = missing_board + 2 * random_opponents
    if cards_needed > len(deck):
        raise ValueError("Cartas insuficientes para completar a simulação.")
    max_seconds = max(0.2, min(time_budget, 2.0))
    batch_size = max(200, batch_size)
    random_labels = [f"Oponente {len(known_labels) + idx + 1}" for idx in range(random_opponents)]
    draw_buffer = list(deck)
    hero_category_counter: Counter = Counter()
    hero_win_category_counter: Counter = Counter()
    loss_category_counter: Counter = Counter()
    loss_winner_counter: Counter = Counter()
    losing_examples_data: Dict[int, Counter] = defaultdict(Counter)
    tie_category_counter: Counter = Counter()
    tie_size_counter: Counter = Counter()
    board_only_ties = 0
    wins = ties = losses = 0
    start = time.perf_counter()
    iterations = 0
    while time.perf_counter() - start < max_seconds:
        for _ in range(batch_size):
            if time.perf_counter() - start >= max_seconds:
                break
            random.shuffle(draw_buffer)
            board_draw = draw_buffer[:missing_board] if missing_board else []
            simulated_board = board_cards + board_draw
            hero_rank = best_hand_rank_7(hero_cards, simulated_board)
            hero_category_counter[hero_rank[0]] += 1
            board_rank = board_only_rank_value(simulated_board)
            opponent_hands: List[Tuple[Tuple[int, int], List[Card], str]] = []
            for idx, opp_cards in enumerate(known_cards):
                opponent_hands.append(((0, 0), list(opp_cards), known_labels[idx]))
            offset = missing_board
            for rand_idx in range(random_opponents):
                card_a = draw_buffer[offset]
                card_b = draw_buffer[offset + 1]
                offset += 2
                opponent_hands.append(((0, 0), [card_a, card_b], random_labels[rand_idx]))
            for idx, entry in enumerate(opponent_hands):
                cards = entry[1]
                rank = best_hand_rank_7(cards, simulated_board)
                opponent_hands[idx] = (rank, cards, entry[2])
            best_opponent_rank, best_opponent_cards, best_label = (
                max(opponent_hands, key=lambda item: item[0]) if opponent_hands else ((-1, 0), [], "")
            )
            if hero_rank > best_opponent_rank:
                wins += 1
                hero_win_category_counter[hero_rank[0]] += 1
            elif hero_rank == best_opponent_rank:
                ties += 1
                tie_category_counter[hero_rank[0]] += 1
                tied_players = 1 + sum(1 for entry in opponent_hands if entry[0] == hero_rank)
                tie_size_counter[tied_players] += 1
                if board_rank and board_rank == hero_rank:
                    board_only_ties += 1
            else:
                losses += 1
                loss_category_value = best_opponent_rank[0]
                loss_category_counter[loss_category_value] += 1
                loss_winner_counter[(loss_category_value, best_label or "Oponente desconhecido")] += 1
                if best_opponent_cards:
                    formatted = format_hand(best_opponent_cards)
                    losing_examples_data[loss_category_value][formatted] += 1
            iterations += 1
    if wins != sum(hero_win_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar vitórias do Hero (MC).")
    if losses != sum(loss_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar derrotas do Hero (MC).")
    if ties != sum(tie_category_counter.values()):
        raise ValueError("Inconsistência ao contabilizar empates do Hero (MC).")
    result = _build_result_dict(
        wins,
        ties,
        losses,
        hero_category_counter,
        loss_category_counter,
        losing_examples_data,
    )
    result["hero_most_common_category"] = (
        category_label(hero_category_counter.most_common(1)[0][0]) if hero_category_counter else None
    )
    result["hero_most_common_category_wins"] = (
        category_label(hero_win_category_counter.most_common(1)[0][0]) if hero_win_category_counter else None
    )
    result["loss_breakdown"] = build_loss_breakdown(loss_category_counter, loss_winner_counter)
    result["tie_breakdown"] = build_tie_breakdown(tie_category_counter, tie_size_counter, board_only_ties)
    result["confidence"] = _compute_confidence_intervals(wins, ties, losses, result["total_scenarios"])
    elapsed = time.perf_counter() - start
    meta = {
        "iterations": iterations,
        "elapsed": elapsed,
        "iter_per_sec": iterations / elapsed if elapsed > 0 else 0.0,
        "time_budget": max_seconds,
        "analysis_mode": True,
        "profile": {},
    }
    result["mc_meta"] = meta
    return result, meta


def identify_stage(board_size: int) -> str:
    """Retorna a fase atual do jogo baseada no número de cartas comunitárias conhecidas."""
    if board_size == 0:
        return "Pré-flop"
    if board_size == 3:
        return "Flop"
    if board_size == 4:
        return "Turn"
    if board_size == 5:
        return "River"
    return "Em andamento"


def detect_board_volatility(board_cards: Sequence[Card]) -> Literal["LOW", "MEDIUM", "HIGH"]:
    """Classifica o board conforme potencial de draws (LOW/MEDIUM/HIGH)."""
    if len(board_cards) < 3:
        return "LOW"
    suits = Counter(TreysCard.int_to_str(card)[1] for card in board_cards)
    if any(count >= 3 for count in suits.values()):
        return "HIGH"
    ranks = sorted({TreysCard.get_rank_int(card) for card in board_cards})
    ranks_extended = ranks[:]
    if 14 in ranks:
        ranks_extended.append(1)
    ranks_extended = sorted(set(ranks_extended))
    for idx in range(len(ranks_extended)):
        window = ranks_extended[idx : idx + 3]
        if len(window) == 3 and window[-1] - window[0] <= 4:
            return "HIGH"
    return "MEDIUM"


def determine_monte_carlo_min(board_cards: Sequence[Card], num_opponents: int, _: str) -> Tuple[int, List[str]]:
    """Retorna (mínimo requerido, motivos) para iterações Monte Carlo apenas nos casos pré-flop."""
    required = 0
    reasons: List[str] = []
    if len(board_cards) == 0:
        if num_opponents <= 1:
            required = 100_000
            reasons.append("Pré-flop heads-up recomenda ao menos 100.000 iterações.")
        elif num_opponents >= 2:
            required = 300_000
            reasons.append("Pré-flop multiway (3+ jogadores) recomenda 300.000 iterações.")
    return required, reasons


def main() -> None:
    _log(
        "debug-session",
        "run1",
        "UI",
        "app.py:167",
        "main início",
        {},
    )
    # UI ONLY — visual / layout
    st.set_page_config(page_title="Equity — Texas Hold'em", page_icon="♠️", layout="wide")
    st.markdown(POKER_THEME_CSS, unsafe_allow_html=True)

    st.title("Texas Hold'em — Calculadora de Equity")
    st.caption(
        "Equity = % de vezes que sua mão vence no longo prazo. "
        "Monte Carlo = estimativa estatística. Enumeração Exata = todos os runouts possíveis."
    )

    state = ensure_state()
    if "initial_cards_applied" not in st.session_state:
        if not state.hero:
            try:
                state.hero = [parse_card("As"), parse_card("Kd")]
            except ValueError:
                state.hero = []
            st.session_state["selection_state"] = state
        st.session_state["initial_cards_applied"] = True

    # UI ONLY — visual / layout
    # Paralelismo é opcional e deve ser sempre seguro; nunca falhar por detecção de ambiente.
    parallel_enabled = False
    try:
        parallel_enabled = allow_parallel_workers()
    except Exception:
        parallel_enabled = False

    # UI ONLY — visual / layout
    # Controles no sidebar (melhor usabilidade e mais espaço para a mesa/baralho).
    with st.sidebar:
        st.markdown("### Controles")
        tournament_enabled = st.checkbox("Modo Torneio / Oponentes Conhecidos", value=False)

        opponent_slider_key = "known_opponents_slider" if tournament_enabled else "opponents_slider"
        opponents_label = "Número de oponentes conhecidos" if tournament_enabled else "Número de adversários"
        default_opponents = 2 if tournament_enabled else 3
        active_opponents = st.slider(
            opponents_label,
            min_value=1,
            max_value=8,
            value=default_opponents,
            key=opponent_slider_key,
            help="Número de jogadores adversários no pote.",
        )

        st.divider()
        st.markdown("### Monte Carlo")
        time_budget_seconds = st.slider(
            "Tempo (segundos)",
            min_value=0.5,
            max_value=10.0,
            value=1.0,
            step=0.5,
            help="Controla diretamente o orçamento de tempo do Monte Carlo.",
        )
        analysis_mode = st.checkbox(
            "Mostrar explicações detalhadas (modo mais lento)",
            value=False,
            help="Ative para ver por que o Hero ganha/perde (coleta breakdown completo).",
        )
        effective_time_budget = time_budget_seconds
        if analysis_mode:
            analysis_cap = 1.0
            effective_time_budget = min(time_budget_seconds, analysis_cap)
            st.warning("Modo análise é mais lento por coletar explicações detalhadas.")
            st.caption(f"Tempo efetivo limitado a {effective_time_budget:.2f}s (≈10k–50k iterações).")

        st.divider()
        st.markdown("### Cálculo")
        # UI ONLY — visual / layout (marker para estilizar apenas este botão)
        st.markdown("<div class='calc-marker'></div>", unsafe_allow_html=True)
        if "manual_trigger" not in st.session_state:
            st.session_state["manual_trigger"] = 0
        if st.button("Calcular", use_container_width=True):
            st.session_state["manual_trigger"] += 1
        st.caption("Clique em Calcular para atualizar os resultados.")

    sync_opponent_slots(state, tournament_enabled, active_opponents if tournament_enabled else 0)

    st.markdown("<div class='poker-panel'>", unsafe_allow_html=True)
    st.subheader("Mesa e cartas")
    st.markdown(CARD_STYLE_BLOCK, unsafe_allow_html=True)
    slot_cols = st.columns(2, gap="large")
    with slot_cols[0]:
        st.markdown("**Hero**")
        render_slot_group("Hero", state.hero, 2, "hero")
    with slot_cols[1]:
        st.markdown("**Mesa**")
        render_slot_group("Mesa", state.board, 5, "board")

    if tournament_enabled:
        st.divider()
        render_opponent_sections(state, active_opponents)

    st.divider()
    st.markdown("**Seleção pelo baralho**")
    target_options = build_target_options(tournament_enabled, active_opponents if tournament_enabled else 0)
    if "active_target_selection" not in st.session_state:
        st.session_state["active_target_selection"] = target_options[0]
    elif st.session_state["active_target_selection"] not in target_options:
        st.session_state["active_target_selection"] = target_options[0]

    active_target = st.radio(
        "Destino ao clicar no baralho",
        options=target_options,
        format_func=format_target_label,
        horizontal=True,
        key="active_target_selection",
    )
    st.caption("Selecione o destino e clique nas cartas para adicionar/remover.")
    render_card_deck(state, active_target, tournament_enabled=tournament_enabled)
    feedback = st.session_state.pop("deck_feedback", None)
    if feedback:
        st.warning(feedback)
    st.markdown("</div>", unsafe_allow_html=True)

    parsed_hero: List[Card] = list(state.hero)
    parsed_board: List[Card] = list(state.board)
    hero_tokens = [TreysCard.int_to_str(card) for card in parsed_hero]
    board_tokens = [TreysCard.int_to_str(card) for card in parsed_board]
    _log(
        "debug-session",
        "run1",
        "UI",
        "app.py:198",
        "tokens lidos",
        {"hero_tokens": hero_tokens, "board_tokens": board_tokens},
    )
    if len(parsed_hero) != 2:
        st.info("Selecione exatamente 2 cartas para o Hero.")
        st.stop()
    if len(parsed_board) > 5:
        st.error("A mesa pode conter no máximo 5 cartas.")
        st.stop()
    combined_cards = parsed_hero + parsed_board
    known_opponent_pairs: List[Tuple[int, Tuple[Card, Card]]] = []
    if tournament_enabled:
        for opp_id in range(1, active_opponents + 1):
            cards = state.opponents.get(opp_id, [])
            if len(cards) != 2:
                st.info(f"Informe 2 cartas para o Oponente {opp_id}.")
                st.stop()
            known_opponent_pairs.append((opp_id, (cards[0], cards[1])))
            combined_cards.extend(cards)
    if len(combined_cards) != len(set(combined_cards)):
        st.error("Existem cartas duplicadas entre os slots.")
        st.stop()
    known_opponents_tuple = tuple(known_opponent_pairs)

    stage_label = identify_stage(len(parsed_board))
    st.subheader(f"Fase: {stage_label}")

    if len(parsed_board) not in (0, 3, 4, 5):
        st.warning("Adicione cartas seguindo a ordem do jogo (Flop com 3, Turn com 4, River com 5).")

    board_volatility = detect_board_volatility(parsed_board)
    equity_method = choose_equity_method(parsed_board)

    # Enumeração completa explode combinatoriamente com múltiplos oponentes e pode travar a UI.
    exact_fallback_reason: Optional[str] = None
    if equity_method == "EXACT":
        known_count = len(known_opponents_tuple) if tournament_enabled else 0
        random_opponents = max(0, active_opponents - known_count)
        missing_board = max(0, 5 - len(parsed_board))
        deck_size = 52 - len(set(combined_cards))
        estimated = estimate_exact_scenarios(deck_size, missing_board, random_opponents)
        max_exact_scenarios = 2_000_000
        if estimated > max_exact_scenarios:
            exact_fallback_reason = (
                f"Enumeração completa estimada em {estimated:,} cenários "
                f"(limite: {max_exact_scenarios:,})."
            )
            equity_method = "MONTE_CARLO"

    if equity_method == "EXACT":
        st.markdown("🔵 **Cálculo Exato (Enumeração Completa)**")
    else:
        if exact_fallback_reason:
            st.markdown("🟡 **Estimativa Monte Carlo (fallback por performance)**")
            st.warning(
                f"{exact_fallback_reason} Para cálculo exato, reduza o número de oponentes "
                "ou informe cartas conhecidas no modo torneio."
            )
        else:
            st.markdown("🟡 **Estimativa Monte Carlo**")

    min_required = 0
    mc_reasons: List[str] = []
    if equity_method == "MONTE_CARLO" and not analysis_mode:
        min_required, mc_reasons = determine_monte_carlo_min(parsed_board, active_opponents, board_volatility)

    hero_tuple = tuple(parsed_hero)
    board_tuple = tuple(parsed_board)

    params_signature = {
        "hero": hero_tuple,
        "board": board_tuple,
        "opponents": active_opponents,
        "time_budget": time_budget_seconds,
        "effective_budget": effective_time_budget,
        "manual": st.session_state["manual_trigger"],
        "tournament": tournament_enabled,
        "known": known_opponents_tuple,
        "method": equity_method,
        "exact_fallback": exact_fallback_reason,
        "analysis": analysis_mode,
        "parallel": parallel_enabled,
        "min_required": min_required,
    }
    # Debounce simples: só recalcula se algo relevante mudou ou o usuário clicou no botão.
    if (
        "last_result" not in st.session_state
        or st.session_state.get("last_params") != params_signature
    ):
        spinner_label = (
            "Enumerando todos os cenários possíveis..." if equity_method == "EXACT" else "Executando simulação Monte Carlo..."
        )
        with st.spinner(spinner_label):
            try:
                if equity_method == "EXACT":
                    exact_start = time.perf_counter()
                    st.session_state["last_result"] = simulate_exact(
                        hero_tuple,
                        board_tuple,
                        active_opponents,
                        known_opponents_tuple if tournament_enabled else None,
                    )
                    exact_elapsed = time.perf_counter() - exact_start
                    st.session_state["last_meta"] = {"elapsed": exact_elapsed}
                else:
                    result, meta = simulate_monte_carlo(
                        hero_tuple,
                        board_tuple,
                        active_opponents,
                        effective_time_budget,
                        known_opponents_tuple if tournament_enabled else None,
                        batch_size=3000 if parallel_enabled else 1500,
                        collect_breakdown=analysis_mode,
                        use_parallel=parallel_enabled and not analysis_mode,
                    )
                    st.session_state["last_result"] = result
                    st.session_state["last_meta"] = meta
                st.session_state["last_params"] = params_signature
            except ValueError as exc:
                _log(
                    "debug-session",
                    "run1",
                    "UI",
                    "app.py:251",
                    "equity_calc ValueError",
                    {"error": str(exc)},
                )
                st.error(str(exc))
                st.stop()
            except Exception as exc:
                _log(
                    "debug-session",
                    "run1",
                    "UI",
                    "app.py:256",
                    "equity_calc Exception",
                    {"error": str(exc), "type": str(type(exc))},
                )
                st.error(f"Erro inesperado: {str(exc)}")
                st.stop()

    result = st.session_state["last_result"]
    result_meta = st.session_state.get("last_meta")
    # UI: EXACT vs MC — padroniza campos sem alterar equity.
    display_method: Literal["exact", "monte_carlo"] = "exact" if equity_method == "EXACT" else "monte_carlo"
    display = build_display_result(display_method, result, result_meta)
    _log(
        "debug-session",
        "run1",
        "UI",
        "app.py:258",
        "resultado exibido",
        {"result": result},
    )

    # UI ONLY — visual / layout
    st.divider()
    st.markdown("<div class='poker-panel'>", unsafe_allow_html=True)
    st.subheader("Equity do Hero")
    # UI: EXACT vs MC — validação leve de consistência de apresentação.
    total_pct = float(display["win"]) + float(display["tie"]) + float(display["lose"])
    if abs(total_pct - 100.0) > 0.01:
        st.warning("Aviso: soma de Win/Tie/Lose não fecha 100% (arredondamento inesperado).")
    equity_html = f"""
    <div class="equity-grid">
        <div class="equity-card win">
            <div class="label">🟢 Equity de Vitória</div>
            <div class="value">{display['win']:.2f}%</div>
            <div class="sub">Win</div>
        </div>
        <div class="equity-card tie">
            <div class="label">🟡 Equity de Empate</div>
            <div class="value">{display['tie']:.2f}%</div>
            <div class="sub">Tie</div>
        </div>
        <div class="equity-card lose">
            <div class="label">🔴 Equity de Derrota</div>
            <div class="value">{display['lose']:.2f}%</div>
            <div class="sub">Lose</div>
        </div>
    </div>
    """
    st.markdown(equity_html, unsafe_allow_html=True)
    st.divider()

    if display["method"] == "exact":
        st.markdown("🔵 **Resultado exato (enumeração completa)**")
        st.caption(f"Cenários avaliados: {display['n_samples']:,}")
    else:
        st.markdown("🟡 **Monte Carlo (Estimativa)**")

    metrics_line: List[str] = []
    if display["method"] == "monte_carlo":
        metrics_line.append(f"Amostras: {display['n_samples']:,}")
        if display.get("it_per_s") is not None:
            metrics_line.append(f"Iterações/s: {display['it_per_s']:.0f}")
        if display.get("elapsed_s") is not None:
            metrics_line.append(f"Tempo: {display['elapsed_s']:.2f}s")
        if display.get("ci95_win"):
            metrics_line.append(
                "IC95% — Win "
                f"{display['ci95_win']['low']:.2f}%–{display['ci95_win']['high']:.2f}%, "
                "Tie "
                f"{display['ci95_tie']['low']:.2f}%–{display['ci95_tie']['high']:.2f}%, "
                "Lose "
                f"{display['ci95_lose']['low']:.2f}%–{display['ci95_lose']['high']:.2f}%"
            )
    else:
        if display.get("elapsed_s") is not None:
            metrics_line.append(f"Tempo: {display['elapsed_s']:.2f}s")
    if metrics_line:
        st.caption(" • ".join(metrics_line))

    if display["method"] == "monte_carlo":
        actual_iterations = int(display.get("n_samples") or 0)
        if min_required and actual_iterations < min_required and not analysis_mode:
            st.warning(
                "Número de iterações abaixo do recomendado para este cenário. "
                "Considere aumentar o tempo do Monte Carlo."
            )

    st.markdown("</div>", unsafe_allow_html=True)

    breakdown_expander = st.expander("Análise Detalhada da Mão")
    with breakdown_expander:
        hero_overall = result.get("hero_most_common_category")
        hero_wins_category = result.get("hero_most_common_category_wins")
        if hero_overall:
            st.markdown(f"**Mão mais comum do Hero (todos os runouts):** {hero_overall}")
        if hero_wins_category:
            st.markdown(f"**Mão mais comum quando o Hero vence:** {hero_wins_category}")
        st.divider()

        counts = result.get("counts") or {}
        loss_breakdown = result.get("loss_breakdown")
        tie_breakdown = result.get("tie_breakdown")
        if not loss_breakdown or not tie_breakdown:
            st.caption("Ative o modo análise ou use a enumeração exata para ver o detalhamento completo.")
        else:
            loss_total = counts.get("loss", 0)
            tie_total = counts.get("tie", 0)
            breakdown_cols = st.columns(2, gap="large")
            with breakdown_cols[0]:
                st.markdown("**Como o Hero perde**")
                st.caption(f"Total de derrotas: {loss_total}")
                loss_categories = loss_breakdown.get("categories") or []
                if loss_categories:
                    for entry in loss_categories:
                        st.write(f"- {entry['category']}: {entry['count']}")
                st.divider()
                st.markdown("**Contra quem perde**")
                loss_winners = loss_breakdown.get("winners") or []
                if loss_winners:
                    for entry in loss_winners:
                        opponent = entry.get("opponent", "Oponente")
                        st.write(f"- {opponent} ({entry['category']}): {entry['count']}")
            with breakdown_cols[1]:
                st.markdown("**Tipos de empate**")
                st.caption(f"Total de empates: {tie_total}")
                tie_categories = tie_breakdown.get("categories") or []
                tie_sizes = tie_breakdown.get("players") or []
                if tie_categories:
                    for entry in tie_categories:
                        st.write(f"- {entry['category']}: {entry['count']}")
                st.divider()
                st.markdown("**Quantos jogadores empatam**")
                if tie_sizes:
                    for entry in tie_sizes:
                        st.write(f"- {entry['players']} jogadores: {entry['count']}")
                st.caption(f"Empates formados apenas pelo board: {tie_breakdown.get('board_only_ties', 0)}")


if __name__ == "__main__":
    main()
