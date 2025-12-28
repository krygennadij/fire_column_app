import streamlit as st
import requests

st.set_page_config(page_title="EvacGPT", layout="wide")

YANDEX_API_KEY = "14ca51d3-0445-4192-b619-98dac8c40a02"

st.markdown('''
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Montserrat', sans-serif !important;
        background: #f6f8fa;
    }
    .main-title {
        font-size: 2.8rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #222;
        margin-bottom: 0.2em;
        margin-top: 0.2em;
        text-align: left;
        display: flex;
        align-items: center;
        gap: 0.5em;
    }
    .subtitle {
        font-size: 1.3rem;
        font-weight: 500;
        color: #555;
        margin-bottom: 1.2em;
    }
    .card {
        background: #fff;
        border-radius: 18px;
        box-shadow: 0 4px 24px 0 rgba(60,60,60,0.07);
        padding: 2.2em 2em 1.5em 2em;
        margin-bottom: 1.2em;
        min-height: 120px;
        transition: box-shadow 0.2s;
    }
    .card:hover {
        box-shadow: 0 8px 32px 0 rgba(60,60,60,0.13);
    }
    .level-blue {
        background: linear-gradient(90deg, #e3f0ff 0%, #cbe3ff 100%);
        color: #1a4e89;
    }
    .level-yellow {
        background: linear-gradient(90deg, #fffbe3 0%, #fff3c6 100%);
        color: #a67c00;
    }
    .level-red {
        background: linear-gradient(90deg, #ffe3e3 0%, #ffc6c6 100%);
        color: #b71c1c;
    }
    .result-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5em;
        color: #222;
    }
    .result-value {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2em;
    }
    .icon {
        font-size: 2.2rem;
        vertical-align: middle;
        margin-right: 0.2em;
    }
    .action-card {
        font-size: 1.1rem;
        font-weight: 500;
        border-left: 6px solid #3578e5;
        background: #f7faff;
        color: #1a4e89;
        border-radius: 12px;
        padding: 1.2em 1.2em 1.2em 1.5em;
        margin-bottom: 1em;
    }
    .action-card.yellow {
        border-left: 6px solid #ffc107;
        background: #fffbe3;
        color: #a67c00;
    }
    .action-card.red {
        border-left: 6px solid #e74c3c;
        background: #ffeaea;
        color: #b71c1c;
    }
    .stButton > button {
        background: linear-gradient(90deg, #3578e5 0%, #6fb1fc 100%);
        color: #fff;
        border: none;
        border-radius: 10px;
        font-size: 1.1rem;
        font-weight: 600;
        padding: 0.7em 2.2em;
        margin-top: 1.2em;
        margin-bottom: 0.5em;
        box-shadow: 0 2px 8px 0 rgba(60,60,60,0.07);
        transition: background 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #255fa8 0%, #3578e5 100%);
    }
    .stSelectbox > div, .stTextInput > div {
        border-radius: 8px !important;
    }
    </style>
''', unsafe_allow_html=True)

st.markdown('<div class="main-title">🧠 EvacGPT</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Интеллектуальная система мониторинга и оценки уровня пожарной опасности</div>', unsafe_allow_html=True)
st.markdown("<hr style='margin-bottom:2em;margin-top:0.5em;'>", unsafe_allow_html=True)

def get_address_suggestions(query, api_key):
    if not query or len(query) < 4:
        return []
    url = "https://suggest-maps.yandex.ru/v1/suggest"
    params = {
        "apikey": api_key,
        "text": query,
        "lang": "ru_RU",
        "results": 5,
    }
    try:
        resp = requests.get(url, params=params, timeout=2)
        resp.raise_for_status()
        suggestions = resp.json().get("results", [])
        return [s["title"] for s in suggestions]
    except Exception:
        return []

with st.form("evac_form"):
    col1, col2 = st.columns([1.2,1])
    with col1:
        address_query = st.text_input("Введите адрес объекта", "г. Москва, ")
        suggestions = get_address_suggestions(address_query, YANDEX_API_KEY)
        if suggestions:
            address = st.selectbox("Выберите адрес из подсказок", suggestions)
        else:
            address = address_query
        etalon_time = st.number_input("Эталонное время эвакуации (мин)", min_value=1.0, value=7.0, step=0.1)
        prog_time = st.number_input("Прогнозируемое время эвакуации (мин)", min_value=1.0, value=12.0, step=0.1)
        st.markdown("**Состояние систем пожарной безопасности:**")
        auto = st.selectbox("Состояние систем автоматики", ["Соответствует", "Нарушение"], key="auto")
        evac = st.selectbox("Состояние путей эвакуации", ["Соответствует", "Нарушение"], key="evac")
        edu = st.selectbox("Обучение персонала", ["Соответствует", "Нарушение"], key="edu")
        drill = st.selectbox("Проведение учений", ["Соответствует", "Нарушение"], key="drill")
    with col2:
        mchs = st.radio("Кто проводит мониторинг?", ["Руководитель организации (не МЧС)", "Сотрудник МЧС"], key="who")
        submitted = st.form_submit_button("Рассчитать")

if 'submitted' not in locals() or not submitted:
    st.stop()

violations = sum([auto == "Нарушение", evac == "Нарушение", edu == "Нарушение", drill == "Нарушение"])
coef = 1.25 ** violations
adj_prog_time = prog_time * coef
percent = ((adj_prog_time - etalon_time) / etalon_time) * 100

if percent < 50:
    level = 'Синий'
    color = 'level-blue'
    emoji = '🟦'
elif percent < 100:
    level = 'Жёлтый'
    color = 'level-yellow'
    emoji = '🟨'
else:
    level = 'Красный'
    color = 'level-red'
    emoji = '🟥'

actions_mchs = {
    'Синий': 'Предупреждение, инструктаж',
    'Жёлтый': 'Пожарно-техническое обследование',
    'Красный': 'Приостановка эксплуатации'
}
actions_non_mchs = {
    'Синий': 'Самообследование объекта, организация учений',
    'Жёлтый': 'Дополнительно: обучение персонала в учебных заведениях и приглашение внешних аудиторов',
    'Красный': 'Дополнительно: приглашение сотрудников МЧС для полного пожарно-технического обследования'
}

st.markdown("<hr style='margin-bottom:2em;margin-top:1em;'>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1.5, 1.1, 1.4])
with col1:
    st.markdown(f"<div class='card'><span class='result-title'>🏢 Объект</span><div class='result-value'>{address}</div>"
                f"<div class='result-title'>⏱ Эталонное время</div><div class='result-value'>{etalon_time:.1f} мин</div>"
                f"<div class='result-title'>⏳ Прогноз (с коэффициентами)</div><div class='result-value'>{adj_prog_time:.1f} мин</div>"
                f"<div class='result-title'>% превышения</div><div class='result-value'>{percent:.0f}%</div>"
                f"<div style='margin-top:1em;'><b>Автоматика:</b> {auto}<br><b>Пути эвакуации:</b> {evac}<br><b>Обучение:</b> {edu}<br><b>Учения:</b> {drill}</div>"
                f"</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"<div class='card {color}' style='text-align:center;'><span class='icon'>{emoji}</span><div class='result-title'>Уровень опасности</div><div class='result-value'>{level}</div></div>", unsafe_allow_html=True)

with col3:
    st.markdown(f"<div class='card' style='min-height:120px;'><div class='result-title'>Рекомендуемые действия</div>", unsafe_allow_html=True)
    if mchs == "Сотрудник МЧС":
        st.markdown(f"<div class='action-card {color[6:]}'> {actions_mchs[level]} </div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='action-card {color[6:]}'> {actions_non_mchs[level]} </div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True) 