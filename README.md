# Poker Odds (Texas Hold'em)

Aplicativo Streamlit que calcula em tempo real a probabilidade do Hero ganhar, empatar ou perder uma mão de Texas Hold'em usando simulação de Monte Carlo.

## Requisitos

- Python 3.9+
- Dependências: `streamlit` e `treys`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install streamlit treys
```

## Execução

```bash
streamlit run app.py
```

## Uso

1. Informe as duas cartas do Hero (ex.: `As Kd`).
2. Informe as cartas comunitárias disponíveis (0 a 5 cartas, ex.: `7h 8h 9h`).
3. Escolha o número de adversários (1 a 8) e o número de iterações (5k, 20k, 50k, 100k).
4. O app recalcula automaticamente a equidade sempre que qualquer parâmetro mudar. Use o botão **"Calcular Probabilidades"** se quiser forçar uma nova simulação com o mesmo cenário.

A tela mostra a fase atual do jogo, as probabilidades de vitória/empate/derrota e a categoria de mão mais frequente encontrada para o Hero durante a simulação.

## Detalhes técnicos

- Simulação Monte Carlo seguindo as etapas clássicas: baralho padrão, remoção de cartas conhecidas, completação da mesa, distribuição de mãos adversárias e avaliação de todas as combinações de 5 cartas entre as 7 disponíveis.
- Avaliador otimizado pré-calcula as 21 combinações possíveis (7 ➝ 5) para acelerar cada iteração.
- Debounce via `st.session_state`: apenas quando os parâmetros mudam (ou o botão é pressionado) uma nova simulação é executada, evitando recomputações desnecessárias enquanto o usuário edita os campos.
