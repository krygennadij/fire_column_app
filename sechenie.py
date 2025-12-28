import streamlit as st
import plotly.graph_objects as go
import numpy as np

# Параметры круга
radius = 250  # 500/2 мм
center_x, center_y = 0, 0

# Создаем точки для внешнего круга
theta = np.linspace(0, 2*np.pi, 100)
x_outer = center_x + radius * np.cos(theta)
y_outer = center_y + radius * np.sin(theta)

# Создаем точки для первого внутреннего круга (на 10 мм меньше)
x_inner1 = center_x + (radius - 10) * np.cos(theta)
y_inner1 = center_y + (radius - 10) * np.sin(theta)

# Создаем точки для второго внутреннего круга (еще на 10 мм меньше)
x_inner2 = center_x + (radius - 20) * np.cos(theta)
y_inner2 = center_y + (radius - 20) * np.sin(theta)

# Создаем точки для третьего внутреннего круга (еще на 20 мм меньше)
x_inner3 = center_x + (radius - 40) * np.cos(theta)
y_inner3 = center_y + (radius - 40) * np.sin(theta)

# Создаем точки для четвертого внутреннего круга (еще на 10 мм меньше)
x_inner4 = center_x + (radius - 60) * np.cos(theta)
y_inner4 = center_y + (radius - 60) * np.sin(theta)

# Создаем точки для пятого внутреннего круга (еще на 20 мм меньше)
x_inner5 = center_x + (radius - 80) * np.cos(theta)
y_inner5 = center_y + (radius - 80) * np.sin(theta)

# Создаем точки для шестого внутреннего круга (еще на 20 мм меньше)
x_inner6 = center_x + (radius - 100) * np.cos(theta)
y_inner6 = center_y + (radius - 100) * np.sin(theta)

# Создаем точки для седьмого внутреннего круга (еще на 30 мм меньше)
x_inner7 = center_x + (radius - 120) * np.cos(theta)
y_inner7 = center_y + (radius - 120) * np.sin(theta)

# Создаем точки для слоев без армирования
x_inner1_no = center_x + (radius - 10) * np.cos(theta)
y_inner1_no = center_y + (radius - 10) * np.sin(theta)

x_inner2_no = center_x + (radius - 30) * np.cos(theta)
y_inner2_no = center_y + (radius - 30) * np.sin(theta)

x_inner3_no = center_x + (radius - 50) * np.cos(theta)
y_inner3_no = center_y + (radius - 50) * np.sin(theta)

x_inner4_no = center_x + (radius - 70) * np.cos(theta)
y_inner4_no = center_y + (radius - 70) * np.sin(theta)

x_inner5_no = center_x + (radius - 100) * np.cos(theta)
y_inner5_no = center_y + (radius - 100) * np.sin(theta)

x_inner6_no = center_x + (radius - 130) * np.cos(theta)
y_inner6_no = center_y + (radius - 130) * np.sin(theta)

# Создаем точки армирования (8 точек на расстоянии 50 мм от внешнего диаметра)
reinforcement_radius = radius - 50
reinforcement_theta = np.linspace(0, 2*np.pi, 8, endpoint=False)
reinforcement_x = center_x + reinforcement_radius * np.cos(reinforcement_theta)
reinforcement_y = center_y + reinforcement_radius * np.sin(reinforcement_theta)

# Добавляем переключатель
show_reinforcement = st.radio("Отображение армирования:", ["С армированием", "Без армирования"])

fig = go.Figure()

# Внешний круг (заливка)
fig.add_trace(go.Scatter(
    x=x_outer, y=y_outer,
    fill='toself',
    fillcolor='rgb(0,0,0)',
    line=dict(width=0),
    showlegend=False
))

if show_reinforcement == "С армированием":
    # Первый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner1, y=y_inner1,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Второй внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner2, y=y_inner2,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Третий внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner3, y=y_inner3,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Четвертый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner4, y=y_inner4,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Пятый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner5, y=y_inner5,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Шестой внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner6, y=y_inner6,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Седьмой внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner7, y=y_inner7,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Контур первого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner1, y=y_inner1,
        mode='lines',
        line=dict(width=2, color='red'),
        name='Первый внутренний контур',
        showlegend=True
    ))

    # Контур второго внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner2, y=y_inner2,
        mode='lines',
        line=dict(width=2, color='green'),
        name='Второй внутренний контур',
        showlegend=True
    ))

    # Контур третьего внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner3, y=y_inner3,
        mode='lines',
        line=dict(width=2, color='purple'),
        name='Третий внутренний контур',
        showlegend=True
    ))

    # Контур четвертого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner4, y=y_inner4,
        mode='lines',
        line=dict(width=2, color='orange'),
        name='Четвертый внутренний контур',
        showlegend=True
    ))

    # Контур пятого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner5, y=y_inner5,
        mode='lines',
        line=dict(width=2, color='brown'),
        name='Пятый внутренний контур',
        showlegend=True
    ))

    # Контур шестого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner6, y=y_inner6,
        mode='lines',
        line=dict(width=2, color='pink'),
        name='Шестой внутренний контур',
        showlegend=True
    ))

    # Контур седьмого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner7, y=y_inner7,
        mode='lines',
        line=dict(width=2, color='gray'),
        name='Седьмой внутренний контур',
        showlegend=True
    ))

    # Точки армирования
    fig.add_trace(go.Scatter(
        x=reinforcement_x, y=reinforcement_y,
        mode='markers',
        marker=dict(
            size=10,  # Размер точки 10 мм
            color='red',
            line=dict(width=1, color='black')
        ),
        name='Армирование 8Ø10'
    ))

else:  # Без армирования
    # Первый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner1_no, y=y_inner1_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Второй внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner2_no, y=y_inner2_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Третий внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner3_no, y=y_inner3_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Четвертый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner4_no, y=y_inner4_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Пятый внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner5_no, y=y_inner5_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Шестой внутренний круг (заливка)
    fig.add_trace(go.Scatter(
        x=x_inner6_no, y=y_inner6_no,
        fill='toself',
        fillcolor='rgb(210,209,205)',
        line=dict(width=0),
        showlegend=False
    ))

    # Контур первого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner1_no, y=y_inner1_no,
        mode='lines',
        line=dict(width=2, color='red'),
        name='Первый внутренний контур',
        showlegend=True
    ))

    # Контур второго внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner2_no, y=y_inner2_no,
        mode='lines',
        line=dict(width=2, color='green'),
        name='Второй внутренний контур',
        showlegend=True
    ))

    # Контур третьего внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner3_no, y=y_inner3_no,
        mode='lines',
        line=dict(width=2, color='purple'),
        name='Третий внутренний контур',
        showlegend=True
    ))

    # Контур четвертого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner4_no, y=y_inner4_no,
        mode='lines',
        line=dict(width=2, color='orange'),
        name='Четвертый внутренний контур',
        showlegend=True
    ))

    # Контур пятого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner5_no, y=y_inner5_no,
        mode='lines',
        line=dict(width=2, color='brown'),
        name='Пятый внутренний контур',
        showlegend=True
    ))

    # Контур шестого внутреннего круга
    fig.add_trace(go.Scatter(
        x=x_inner6_no, y=y_inner6_no,
        mode='lines',
        line=dict(width=2, color='pink'),
        name='Шестой внутренний контур',
        showlegend=True
    ))

# Контур внешнего круга
fig.add_trace(go.Scatter(
    x=x_outer, y=y_outer,
    mode='lines',
    line=dict(width=2, color='blue'),
    name='Внешний контур',
    showlegend=True
))

# Настройки осей
fig.update_xaxes(range=[-270, 270], tickvals=[-250, -200, -150, -100, -50, 0, 50, 100, 150, 200, 250])
fig.update_yaxes(range=[-270, 270], tickvals=[-250, -200, -150, -100, -50, 0, 50, 100, 150, 200, 250])

fig.update_layout(
    width=500, height=600,
    plot_bgcolor='white',
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.35,
        xanchor="center",
        x=0.5,
        font=dict(size=12)
    ),
    margin=dict(l=40, r=40, t=40, b=120)
)

st.plotly_chart(fig, use_container_width=False)