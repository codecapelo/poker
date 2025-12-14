import random
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import streamlit as st
from treys import Card as TreysCard, Evaluator

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


def build_deck() -> List[Card]:
    """Retorna um novo baralho padrão de 52 cartas."""
    deck = []
    for rank in RANK_SYMBOLS:
        for suit in SUITS:
            deck.append(TreysCard.new(f"{rank}{suit}"))
    return deck


def remove_known_cards(deck: Sequence[Card], known_cards: Sequence[Card]) -> List[Card]:
    """Remove cartas já conhecidas (Hero + mesa) do baralho restante."""
    known_set = set(known_cards)
    return [card for card in deck if card not in known_set]


def best_hand_rank_7(cards: Sequence[Card], board_cards: Optional[Sequence[Card]] = None) -> Tuple[int, int]:
    """Determina o ranking de uma mão usando o avaliador Treys."""
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
    return category, -rank_value


def simulate_equity(
    hero_cards: Sequence[Card], board_cards: Sequence[Card], num_opponents: int, iterations: int
) -> Dict[str, float]:
    """Executa uma simulação de Monte Carlo e retorna as probabilidades de vitória/empate/derrota."""
    deck = remove_known_cards(build_deck(), hero_cards + board_cards)
    missing_board = 5 - len(board_cards)
    cards_needed = missing_board + 2 * num_opponents
    if cards_needed > len(deck):
        raise ValueError("Cartas insuficientes para completar a simulação.")
    wins = ties = losses = 0
    category_counter: Counter = Counter()

    base_hero = list(hero_cards)
    base_board = list(board_cards)

    for _ in range(iterations):
        draw = random.sample(deck, cards_needed)
        simulated_board = base_board + draw[:missing_board]
        hero_rank = best_hand_rank_7(base_hero, simulated_board)
        category_counter[hero_rank[0]] += 1

        opponent_offset = missing_board
        opponent_ranks = []
        for _ in range(num_opponents):
            opp_cards = draw[opponent_offset : opponent_offset + 2]
            opponent_offset += 2
            opponent_ranks.append(best_hand_rank_7(opp_cards, simulated_board))

        best_opponent = max(opponent_ranks)
        if hero_rank > best_opponent:
            wins += 1
        elif hero_rank == best_opponent:
            ties += 1
        else:
            losses += 1

    total = wins + ties + losses
    win_pct = wins / total * 100
    tie_pct = ties / total * 100
    loss_pct = losses / total * 100
    most_common_category = category_counter.most_common(1)
    result = {
        "win_pct": win_pct,
        "tie_pct": tie_pct,
        "loss_pct": loss_pct,
        "most_likely_category": CATEGORY_NAMES.get(most_common_category[0][0]) if most_common_category else None,
    }
    return result


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


def main() -> None:
    st.set_page_config(page_title="Probabilidades Texas Hold'em", page_icon="♠️", layout="centered")
    st.title("Calculadora de Probabilidades - Texas Hold'em")
    st.caption("Simulação Monte Carlo em tempo real para estimar equidade do Hero")
    st.markdown(
        "Use formato `valor+naipe` para cada carta: valores `2-9`, `T`, `J`, `Q`, `K`, `A` "
        "ou `10`, e naipes `s` (espadas), `h` (copas), `d` (ouros) e `c` (paus). "
        "Exemplo: `As Kd` para Ás de espadas e Rei de ouros."
    )

    col1, col2 = st.columns(2)
    with col1:
        hero_input = st.text_input("Cartas do Hero (ex: 'As Kd')", value="As Kd")
    with col2:
        board_input = st.text_input("Cartas da Mesa (até 5 cartas)", value="")

    col3, col4 = st.columns(2)
    with col3:
        opponents = st.slider("Número de adversários", min_value=1, max_value=8, value=3)
    with col4:
        iterations_option = st.selectbox(
            "Iterações da simulação",
            options=[5000, 20000, 50000, 100000],
            index=1,
            help="Quanto maior o número de iterações, maior a precisão."
        )

    if "manual_trigger" not in st.session_state:
        st.session_state["manual_trigger"] = 0
    if st.button("Calcular Probabilidades"):
        st.session_state["manual_trigger"] += 1

    hero_tokens = [token for token in hero_input.replace(",", " ").split() if token]
    board_tokens = [token for token in board_input.replace(",", " ").split() if token]
    errors = []
    parsed_hero: List[Card] = []
    parsed_board: List[Card] = []

    try:
        if len(hero_tokens) != 2:
            raise ValueError("Informe exatamente 2 cartas para o Hero.")
        parsed_hero = [parse_card(token) for token in hero_tokens]
    except ValueError as exc:
        errors.append(str(exc))

    try:
        if len(board_tokens) > 5:
            raise ValueError("A mesa pode conter no máximo 5 cartas.")
        parsed_board = [parse_card(token) for token in board_tokens]
    except ValueError as exc:
        errors.append(str(exc))

    all_cards = parsed_hero + parsed_board
    if len(all_cards) != len(set(all_cards)):
        errors.append("Existem cartas duplicadas entre as cartas informadas.")

    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    stage_label = identify_stage(len(parsed_board))
    st.subheader(f"Fase: {stage_label}")

    if len(parsed_board) not in (0, 3, 4, 5):
        st.warning("Adicione cartas seguindo a ordem do jogo (Flop com 3, Turn com 4, River com 5).")

    params_signature = {
        "hero": tuple(parsed_hero),
        "board": tuple(parsed_board),
        "opponents": opponents,
        "iterations": iterations_option,
        "manual": st.session_state["manual_trigger"],
    }
    # Debounce simples: só recalcula se algo relevante mudou ou o usuário clicou no botão.
    if (
        "last_result" not in st.session_state
        or st.session_state.get("last_params") != params_signature
    ):
        with st.spinner("Executando simulação Monte Carlo..."):
            try:
                st.session_state["last_result"] = simulate_equity(
                    parsed_hero, parsed_board, opponents, iterations_option
                )
                st.session_state["last_params"] = params_signature
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            except Exception as exc:
                st.error(f"Erro inesperado: {str(exc)}")
                st.stop()

    result = st.session_state["last_result"]

    metric_cols = st.columns(3)
    metric_cols[0].metric("Probabilidade de Vitória", f"{result['win_pct']:.2f}%")
    metric_cols[1].metric("Probabilidade de Empate", f"{result['tie_pct']:.2f}%")
    metric_cols[2].metric("Probabilidade de Derrota", f"{result['loss_pct']:.2f}%")

    if result["most_likely_category"]:
        st.info(f"Categoria mais frequente para o Hero: {result['most_likely_category']}")


if __name__ == "__main__":
    main()
