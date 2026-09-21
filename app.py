import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import itertools

# --- 1. 선거제도별 의석 산출 로직 (정밀 가공 및 오류 예방 통합) ---
def clean_input_df(df):
    df_clean = df.copy()
    if df_clean.empty:
        return df_clean

    # 입력 데이터 타입 충돌 방지 및 결측치(NaN) 정리
    df_clean['정당명'] = df_clean['정당명'].fillna('무명정당').astype(str)
    df_clean['득표율(%)'] = pd.to_numeric(df_clean['득표율(%)'], errors='coerce').fillna(0.0).astype(float).clip(0.0, 100.0)

    if '지역구의석' in df_clean.columns:
        df_clean['지역구의석'] = pd.to_numeric(df_clean['지역구의석'], errors='coerce').fillna(0).astype(int).clip(lower=0)
    else:
        df_clean['지역구의석'] = 0

    df_clean['이념위치(1-10)'] = pd.to_numeric(df_clean['이념위치(1-10)'], errors='coerce').fillna(5.0).astype(float).clip(1.0, 10.0)
    return df_clean

def calc_pure_pr(df, total_seats, threshold):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    if df_res.empty: return df_res

    df_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    if df_valid.empty: return df_res

    valid_votes = df_valid['득표율(%)'].sum()
    if valid_votes <= 0: return df_res

    # 단순 비례대표제 산출 및 반올림 오차 보정
    df_valid['비례의석'] = (df_valid['득표율(%)'] / valid_votes * total_seats).round().astype(int)
    diff = total_seats - df_valid['비례의석'].sum()
    if diff != 0 and not df_valid.empty:
        max_idx = df_valid['득표율(%)'].idxmax()
        df_valid.loc[max_idx, '비례의석'] += diff

    df_valid['최종의석'] = df_valid['비례의석']
    df_res.update(df_valid[['최종의석']])
    return df_res

def calc_parallel(df, pr_seats, threshold):
    df_res = clean_input_df(df)
    df_res['최종의석'] = df_res['지역구의석'].copy()
    if df_res.empty: return df_res

    df_pr_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    df_res['비례의석'] = 0
    if not df_pr_valid.empty:
        valid_votes = df_pr_valid['득표율(%)'].sum()
        if valid_votes > 0:
            df_pr_valid['비례의석'] = (df_pr_valid['득표율(%)'] / valid_votes * pr_seats).round().astype(int)
            diff = pr_seats - df_pr_valid['비례의석'].sum()
            if diff != 0:
                max_idx = df_pr_valid['득표율(%)'].idxmax()
                df_pr_valid.loc[max_idx, '비례의석'] += diff
            df_res.update(df_pr_valid[['비례의석']])

    df_res['최종의석'] = df_res['지역구의석'] + df_res['비례의석'].astype(int)
    return df_res

def calc_mmp(df, total_target_seats, threshold):
    df_res = clean_input_df(df)
    df_res['최종의석'] = df_res['지역구의석'].copy()
    if df_res.empty: return df_res

    df_pr_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    df_res['비례의석'] = 0
    if not df_pr_valid.empty:
        valid_votes = df_pr_valid['득표율(%)'].sum()
        if valid_votes > 0:
            df_pr_valid['목표의석'] = (df_pr_valid['득표율(%)'] / valid_votes * total_target_seats).round().astype(int)
            # 초과의석을 허용하는 연동형 계산
            df_pr_valid['비례의석'] = (df_pr_valid['목표의석'] - df_pr_valid['지역구의석']).clip(lower=0)
            df_res.update(df_pr_valid[['비례의석']])

    df_res['최종의석'] = df_res['지역구의석'] + df_res['비례의석'].fillna(0).astype(int)
    return df_res

def calc_stv_proxy(df, total_seats):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    if df_res.empty or total_seats <= 0: return df_res

    df_sim = df_res.copy()
    df_sim['현재득표'] = df_sim['득표율(%)'].copy()
    quota = 100.0 / (total_seats + 1) # Droop Quota
    seats_allocated = 0
    loop_guard = 0
    
    while seats_allocated < total_seats and len(df_sim[df_sim['현재득표'] > 0]) > 0 and loop_guard < 500:
        loop_guard += 1
        # 1. 쿼터 달성 정당 의석 배분
        for idx, row in df_sim.iterrows():
            if row['현재득표'] >= quota and seats_allocated < total_seats:
                df_sim.loc[idx, '최종의석'] += 1
                df_sim.loc[idx, '현재득표'] -= quota
                seats_allocated += 1
                
        # 2. 가장 득표가 적은 정당 탈락 및 이념적 표 이양
        if all(df_sim['현재득표'] < quota) and seats_allocated < total_seats:
            active_parties = df_sim[df_sim['현재득표'] > 0]
            if active_parties.empty: break
            loser_idx = active_parties['현재득표'].idxmin()
            transfer_votes = df_sim.loc[loser_idx, '현재득표']
            df_sim.loc[loser_idx, '현재득표'] = 0.0
            
            active_others = df_sim[df_sim['현재득표'] > 0]
            if not active_others.empty:
                loser_ideology = df_sim.loc[loser_idx, '이념위치(1-10)']
                distances = (active_others['이념위치(1-10)'] - loser_ideology).abs()
                closest_idx = distances.idxmin()
                df_sim.loc[closest_idx, '현재득표'] += transfer_votes
            else:
                break
                
    df_res['최종의석'] = df_sim['최종의석']
    return df_res

# --- 2. 최소 승리 연합 탐색 로직 ---
def simulate_coalitions(df_valid, total_parliament_seats):
    if total_parliament_seats <= 0: return []
    majority_threshold = (total_parliament_seats // 2) + 1
    valid_coalitions = []
    
    df_active = df_valid[df_valid['최종의석'].fillna(0) > 0]
    party_names = df_active['정당명'].dropna().unique().tolist()
    if len(party_names) < 2: return []
    
    r_max = min(len(party_names) + 1, 6)
    for r in range(2, r_max):
        for combo in itertools.combinations(party_names, r):
            combo_df = df_active[df_active['정당명'].isin(combo)]
            seats = combo_df['최종의석'].sum()
            if seats >= majority_threshold:
                min_ide = combo_df['이념위치(1-10)'].min()
                max_ide = combo_df['이념위치(1-10)'].max()
                ideological_spread = float(max_ide - min_ide)
                valid_coalitions.append({
                    'coalition': combo,
                    'total_seats': int(seats),
                    'ideological_spread': round(ideological_spread, 2)
                })
                
    return sorted(valid_coalitions, key=lambda x: (x['ideological_spread'], x['total_seats']))

# --- 3. 의회 반원형 다이어그램 시각화 (Hemicircle) ---
def draw_parliament_chart(df):
    df_valid = df[df['최종의석'].fillna(0) > 0].copy()
    if df_valid.empty: return go.Figure()
    
    df_sorted = df_valid.sort_values('이념위치(1-10)')
    total_seats = int(df_sorted['최종의석'].sum())
    if total_seats == 0: return go.Figure()

    def get_color(ideology):
        try:
            normalized = (float(ideology) - 1.0) / 9.0
            normalized = max(0.0, min(1.0, normalized))
            r = int(255 * (1.0 - normalized))
            b = int(255 * normalized)
            g = int(200 * (1.0 - abs(normalized - 0.5) * 2.0))
            return f'rgb({r},{g},{b})'
        except:
            return 'rgb(128,128,128)'

    df_sorted['Color'] = df_sorted['이념위치(1-10)'].apply(get_color)
    
    # 반원 구현을 위한 더미 데이터 추가
    labels = df_sorted['정당명'].tolist() + ['Dummy']
    values = df_sorted['최종의석'].tolist() + [total_seats]
    colors = df_sorted['Color'].tolist() + ['rgba(0,0,0,0)']

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors, line=dict(color='#ffffff', width=2)),
        hole=0.4,
        rotation=270,
        direction='clockwise',
        textinfo='label+value',
        textposition='inside',
        hoverinfo='label+value+percent'
    )])
    
    fig.update_layout(
        showlegend=False,
        margin=dict(t=30, b=0, l=0, r=0),
        height=400,
        title_text=f"최종 의회 구성 (총 {total_seats}석)",
        title_x=0.5
    )
    fig.update_traces(texttemplate="%{label}<br>%{value}석", selector=dict(type='pie'))
    
    try:
        fig.data[0].textfont.color = ['white'] * len(df_sorted) + ['rgba(0,0,0,0)']
    except:
        pass
        
    return fig

# --- 4. Streamlit UI 구성 ---
st.set_page_config(page_title="고급 선거 및 연정 시뮬레이터", layout="wide")
st.title("🏛️ 의회 선거제도 및 연립정부 시뮬레이터")

if 'party_data' not in st.session_state:
    st.session_state.party_data = pd.DataFrame([
        {'정당명': '노동당', '득표율(%)': 35.0, '지역구의석': 90, '이념위치(1-10)': 3.0},
        {'정당명': '녹색당', '득표율(%)': 8.0, '지역구의석': 2, '이념위치(1-10)': 2.0},
        {'정당명': '자유당', '득표율(%)': 15.0, '지역구의석': 15, '이념위치(1-10)': 5.0},
        {'정당명': '보수당', '득표율(%)': 28.0, '지역구의석': 85, '이념위치(1-10)': 7.0},
        {'정당명': '대안우파당', '득표율(%)': 4.5, '지역구의석': 0, '이념위치(1-10)': 9.0}
    ])

with st.sidebar:
    st.header("⚙️ 선거제도 설정")
    election_system = st.selectbox(
        "적용할 선거제도",
        ["단순 비례대표제", "병립형 비례대표제 (혼합형)", "연동형 비례대표제 (MMP)", "단기이양식 선호투표제 (STV 간이모델)"]
    )
    if election_system in ["단순 비례대표제", "단기이양식 선호투표제 (STV 간이모델)"]:
        total_seats = st.number_input("의회 총 의석수", 50, 1000, 300)
        electoral_threshold = st.slider("봉쇄조항 (%)", 0.0, 10.0, 5.0, 0.5) if "STV" not in election_system else 0.0
    else:
        district_seats = st.number_input("총 지역구 의석수", 10, 800, 250)
        pr_seats = st.number_input("총 비례대표 의석수", 10, 300, 50)
        total_seats = district_seats + pr_seats
        electoral_threshold = st.slider("봉쇄조항 (%)", 0.0, 10.0, 5.0, 0.5)

st.subheader("📊 정당 데이터 입력")
st.caption("선택한 선거제도에 맞춰 득표율과 지역구 당선자를 조절하세요. 셀을 클릭하면 수정할 수 있습니다.")

# 세션 데이터 정제(타입 충돌 사전에 단절)
df_to_edit = clean_input_df(st.session_state.party_data)
edited_df = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True)

st.divider()

# 에디터에서 발생할 수 있는 에러 재정제
cleaned_edit = clean_input_df(edited_df)

result_df = pd.DataFrame()
if election_system == "단순 비례대표제":
    result_df = calc_pure_pr(cleaned_edit, total_seats, electoral_threshold)
elif election_system == "병립형 비례대표제 (혼합형)":
    result_df = calc_parallel(cleaned_edit, pr_seats, electoral_threshold)
elif election_system == "연동형 비례대표제 (MMP)":
    result_df = calc_mmp(cleaned_edit, total_seats, electoral_threshold)
elif election_system == "단기이양식 선호투표제 (STV 간이모델)":
    result_df = calc_stv_proxy(cleaned_edit, total_seats)

if not result_df.empty and '최종의석' in result_df.columns:
    actual_total_seats = int(result_df['최종의석'].sum())
    majority_req = (actual_total_seats // 2) + 1
    
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader("🏛️ 의회 다이어그램")
        if actual_total_seats > total_seats:
            st.warning(f"초과의석 발생! 원래 정원({total_seats}석)에서 {actual_total_seats - total_seats}석 증가하여 총 {actual_total_seats}석이 되었습니다.")
            
        fig_parliament = draw_parliament_chart(result_df)
        st.plotly_chart(fig_parliament, use_container_width=True)

        # 정당 데이터 출력 시 명시적으로 자료형을 정리해서 타입 오류 소지 원천 차단
        df_display = result_df[['정당명', '득표율(%)', '최종의석', '이념위치(1-10)']].copy()
        df_display['득표율(%)'] = df_display['득표율(%)'].round(2).astype(str) + '%'
        df_display['최종의석'] = df_display['최종의석'].astype(int)
        df_display['이념위치(1-10)'] = df_display['이념위치(1-10)'].round(1)

        st.dataframe(df_display.sort_values('최종의석', ascending=False), hide_index=True, use_container_width=True)
        
    with col2:
        st.subheader(f"🤝 연립정부 시나리오 (과반: {majority_req}석)")
        coalitions = simulate_coalitions(result_df, actual_total_seats)
        if coalitions:
            for i, res in enumerate(coalitions[:5], 1):
                with st.expander(f"[{i}순위] {', '.join(res['coalition'])}", expanded=(i==1)):
                    st.write(f"- **합계 의석:** {res['total_seats']}석")
                    st.write(f"- **이념적 거리:** {res['ideological_spread']} (낮을수록 이념적 동질성 높음)")
                    st.progress(min(res['total_seats'] / actual_total_seats, 1.0))
        else:
            st.error("과반수를 확보할 수 있는 연합 조합이 없습니다.")
else:
    st.warning("의석 산출 조건에 맞는 데이터가 없습니다.")
