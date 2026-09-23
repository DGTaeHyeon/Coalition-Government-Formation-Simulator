import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import itertools
import numpy as np
import math

# --- 1. 데이터 정제 ---
def clean_input_df(df):
    df_clean = df.copy()
    if df_clean.empty:
        return df_clean

    df_clean['정당명'] = df_clean['정당명'].fillna('무명정당').astype(str)
    df_clean['득표율(%)'] = pd.to_numeric(df_clean['득표율(%)'], errors='coerce').fillna(0.0).astype(float).clip(0.0, 100.0)
    
    if '이전 득표율(%)' not in df_clean.columns:
        df_clean['이전 득표율(%)'] = 0.0
    df_clean['이전 득표율(%)'] = pd.to_numeric(df_clean['이전 득표율(%)'], errors='coerce').fillna(0.0).astype(float).clip(0.0, 100.0)
    
    if '정당 상태' not in df_clean.columns:
        df_clean['정당 상태'] = '기성'
        
    if '지역구의석' in df_clean.columns:
        df_clean['지역구의석'] = pd.to_numeric(df_clean['지역구의석'], errors='coerce').fillna(0).astype(int).clip(lower=0)
    else:
        df_clean['지역구의석'] = 0

    df_clean['이념위치(1-10)'] = pd.to_numeric(df_clean['이념위치(1-10)'], errors='coerce').fillna(5.0).astype(float).clip(1.0, 10.0)
    return df_clean

# --- 2. 비례대표 의석 배분 공식 (최고평균법 / 최대잔여법) ---
def allocate_pr_seats(votes, num_seats, method):
    seats = pd.Series(0, index=votes.index)
    if num_seats <= 0 or votes.sum() <= 0: return seats
    
    if method == "최대잔여법 (헤어 쿼터)":
        quota = votes.sum() / num_seats
        seats = np.floor(votes / quota).astype(int)
        rem_seats = num_seats - seats.sum()
        if rem_seats > 0:
            remainders = (votes / quota) - seats
            for idx in remainders.nlargest(rem_seats).index:
                seats[idx] += 1
    else: # 최고평균법
        for _ in range(num_seats):
            if method == "최고평균법 (동트)":
                quotients = votes / (seats + 1)
            else: # 최고평균법 (생-라귀)
                quotients = votes / (2 * seats + 1)
            max_idx = quotients.idxmax()
            seats[max_idx] += 1
    return seats

# --- 3. 선거제도 연산 모듈 ---
def calc_pure_pr(df, total_seats, threshold, pr_method, premium_percent=0):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    if df_res.empty: return df_res

    premium_seats = int(total_seats * (premium_percent / 100.0))
    rem_seats = total_seats - premium_seats

    df_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    if df_valid.empty: return df_res

    valid_votes = df_valid['득표율(%)'].sum()
    if valid_votes <= 0: return df_res

    if premium_seats > 0:
        winner_idx = df_valid['득표율(%)'].idxmax()
        df_valid.loc[winner_idx, '최종의석'] += premium_seats

    df_valid['비례의석'] = allocate_pr_seats(df_valid['득표율(%)'], rem_seats, pr_method)
    df_valid['최종의석'] += df_valid['비례의석']
    df_res.update(df_valid[['최종의석']])
    return df_res

def calc_parallel(df, pr_seats, threshold, pr_method):
    df_res = clean_input_df(df)
    df_res['최종의석'] = df_res['지역구의석'].copy()
    if df_res.empty: return df_res

    df_pr_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    df_res['비례의석'] = 0
    if not df_pr_valid.empty:
        df_pr_valid['비례의석'] = allocate_pr_seats(df_pr_valid['득표율(%)'], pr_seats, pr_method)
        df_res.update(df_pr_valid[['비례의석']])

    df_res['최종의석'] = df_res['지역구의석'] + df_res['비례의석'].astype(int)
    return df_res

def calc_mmp(df, total_target_seats, threshold, pr_method, allow_overhang=True):
    df_res = clean_input_df(df)
    df_res['최종의석'] = df_res['지역구의석'].copy()
    if df_res.empty: return df_res

    df_pr_valid = df_res[df_res['득표율(%)'] >= threshold].copy()
    df_res['비례의석'] = 0
    if not df_pr_valid.empty:
        df_pr_valid['목표의석'] = allocate_pr_seats(df_pr_valid['득표율(%)'], total_target_seats, pr_method)
        df_pr_valid['비례의석'] = (df_pr_valid['목표의석'] - df_pr_valid['지역구의석']).clip(lower=0)
        df_res.update(df_pr_valid[['비례의석']])

    if not allow_overhang:
        current_total = df_res['지역구의석'].sum() + df_res['비례의석'].sum()
        if current_total > total_target_seats:
            available_pr = total_target_seats - df_res['지역구의석'].sum()
            if available_pr <= 0:
                df_res['비례의석'] = 0
            else:
                df_res['비례의석'] = allocate_pr_seats(df_res['비례의석'], available_pr, pr_method)

    df_res['최종의석'] = df_res['지역구의석'] + df_res['비례의석'].fillna(0).astype(int)
    return df_res

def calc_stv_proxy(df, total_seats):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    if df_res.empty or total_seats <= 0: return df_res

    df_sim = df_res.copy()
    df_sim['현재득표'] = df_sim['득표율(%)'].copy()
    quota = 100.0 / (total_seats + 1)
    seats_allocated = 0
    loop_guard = 0
    
    while seats_allocated < total_seats and len(df_sim[df_sim['현재득표'] > 0]) > 0 and loop_guard < 500:
        loop_guard += 1
        for idx, row in df_sim.iterrows():
            if row['현재득표'] >= quota and seats_allocated < total_seats:
                df_sim.loc[idx, '최종의석'] += 1
                df_sim.loc[idx, '현재득표'] -= quota
                seats_allocated += 1
                
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
            else: break
                
    df_res['최종의석'] = df_sim['최종의석']
    return df_res

def calc_two_round_proxy(df, total_seats, pr_method, premium_percent=0):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    df_res['1차득표'] = df_res['득표율(%)'].copy()
    df_res['2차득표'] = 0.0
    df_res['비례의석'] = 0
    
    if df_res.empty or total_seats <= 0: return df_res
    premium_seats = int(total_seats * (premium_percent / 100.0))
    rem_seats = total_seats - premium_seats
    
    if df_res['1차득표'].max() > 50.0:
        winner_idx = df_res['1차득표'].idxmax()
        df_res.loc[winner_idx, '최종의석'] += premium_seats
        df_res['비례의석'] = allocate_pr_seats(df_res['1차득표'], rem_seats, pr_method)
        df_res['최종의석'] += df_res['비례의석']
        return df_res
        
    top2 = df_res.nlargest(2, '1차득표')
    top2_indices = top2.index.tolist()
    df_res.loc[top2_indices, '2차득표'] = df_res.loc[top2_indices, '1차득표']
    
    eliminated = df_res[~df_res.index.isin(top2_indices)]
    for idx, row in eliminated.iterrows():
        dist_0 = abs(row['이념위치(1-10)'] - top2.iloc[0]['이념위치(1-10)'])
        dist_1 = abs(row['이념위치(1-10)'] - top2.iloc[1]['이념위치(1-10)'])
        if dist_0 <= dist_1: df_res.loc[top2_indices[0], '2차득표'] += row['1차득표']
        else: df_res.loc[top2_indices[1], '2차득표'] += row['1차득표']
            
    winner_idx_2nd = df_res['2차득표'].idxmax()
    df_res.loc[winner_idx_2nd, '최종의석'] += premium_seats
    df_res.loc[top2_indices, '비례의석'] = allocate_pr_seats(df_res.loc[top2_indices, '2차득표'], rem_seats, pr_method)
    df_res['최종의석'] += df_res['비례의석'].fillna(0).astype(int)
    return df_res

def calc_fptp_cube_rule(df, total_seats):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    if df_res.empty or total_seats <= 0: return df_res

    df_res['득표_세제곱'] = df_res['득표율(%)'] ** 3
    total_cube_votes = df_res['득표_세제곱'].sum()
    if total_cube_votes <= 0: return df_res

    df_res['최종의석'] = allocate_pr_seats(df_res['득표_세제곱'], total_seats, "최대잔여법 (헤어 쿼터)")
    return df_res

# --- 4. 정치학 지표 연산 모듈 ---
def calculate_gallagher_index(df, total_seats_actual):
    if df.empty or total_seats_actual <= 0: return 0.0
    seat_share = (df['최종의석'] / total_seats_actual) * 100.0
    vote_share = df['득표율(%)']
    return round(np.sqrt(0.5 * ((vote_share - seat_share) ** 2).sum()), 2)

def calculate_enp(df, total_seats_actual):
    if df.empty or total_seats_actual <= 0: return 0.0
    seat_shares = df['최종의석'] / total_seats_actual
    sum_sq = (seat_shares ** 2).sum()
    if sum_sq == 0: return 0.0
    return round(1.0 / sum_sq, 2)

def calculate_powell_tucker_volatility(df):
    if df.empty: return 0.0, 0.0, 0.0
    df_calc = df.copy()
    df_calc['절대변동'] = (df_calc['득표율(%)'] - df_calc['이전 득표율(%)']).abs()
    
    type_a_mask = df_calc['정당 상태'].isin(['신설/분열', '소멸'])
    type_b_mask = df_calc['정당 상태'] == '기성'
    
    type_a_vol = df_calc.loc[type_a_mask, '절대변동'].sum() / 2.0
    type_b_vol = df_calc.loc[type_b_mask, '절대변동'].sum() / 2.0
    total_vol = type_a_vol + type_b_vol
    
    return round(total_vol, 2), round(type_a_vol, 2), round(type_b_vol, 2)

def calculate_banzhaf_index(df, total_seats_actual):
    df_active = df[df['최종의석'].fillna(0) > 0].copy()
    party_names = df_active['정당명'].tolist()
    seats_dict = dict(zip(df_active['정당명'], df_active['최종의석']))
    
    majority = (total_seats_actual // 2) + 1
    critical_counts = {p: 0 for p in party_names}
    
    for r in range(1, len(party_names) + 1):
        for combo in itertools.combinations(party_names, r):
            combo_seats = sum(seats_dict[p] for p in combo)
            if combo_seats >= majority:
                for p in combo:
                    if combo_seats - seats_dict[p] < majority:
                        critical_counts[p] += 1
                        
    total_criticals = sum(critical_counts.values())
    if total_criticals == 0: return {p: 0.0 for p in party_names}
    return {p: round((critical_counts[p] / total_criticals) * 100, 1) for p in party_names}

def calculate_shapley_shubik_index(df, total_seats_actual):
    df_active = df[df['최종의석'].fillna(0) > 0].copy()
    party_names = df_active['정당명'].tolist()
    seats_dict = dict(zip(df_active['정당명'], df_active['최종의석']))
    
    n = len(party_names)
    majority = (total_seats_actual // 2) + 1
    shapley_scores = {p: 0.0 for p in party_names}
    
    if n == 0: return shapley_scores
    for r in range(1, n + 1):
        for combo in itertools.combinations(party_names, r):
            combo_seats = sum(seats_dict[p] for p in combo)
            if combo_seats >= majority:
                for p in combo:
                    if combo_seats - seats_dict[p] < majority:
                        weight = (math.factorial(r - 1) * math.factorial(n - r)) / math.factorial(n)
                        shapley_scores[p] += weight
    return {p: round(score * 100, 1) for p, score in shapley_scores.items()}

# --- 5. 연립정부 시나리오 탐색 ---
def simulate_coalitions(df_valid, total_parliament_seats, shapley_dict):
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
                weighted_ideology = (combo_df['이념위치(1-10)'] * combo_df['최종의석']).sum() / seats
                
                combo_power = {p: shapley_dict.get(p, 0.0) for p in combo}
                formateur = max(combo_power, key=combo_power.get)
                
                gamson_allocation = {}
                for p in combo:
                    p_seats = df_active.loc[df_active['정당명'] == p, '최종의석'].values[0]
                    share = (p_seats / seats) * 100.0
                    gamson_allocation[p] = round(share, 1)
                
                valid_coalitions.append({
                    'coalition': combo, 'total_seats': int(seats),
                    'ideological_spread': round(ideological_spread, 2),
                    'weighted_ideology': round(weighted_ideology, 2),
                    'formateur': formateur, 'gamson': gamson_allocation
                })
    return sorted(valid_coalitions, key=lambda x: (x['ideological_spread'], x['total_seats']))

# --- 6. Hemicircle 차트 그리기 ---
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
            r, b = int(255 * (1.0 - normalized)), int(255 * normalized)
            g = int(200 * (1.0 - abs(normalized - 0.5) * 2.0))
            return f'rgb({r},{g},{b})'
        except: return 'rgb(128,128,128)'

    df_sorted['Color'] = df_sorted['이념위치(1-10)'].apply(get_color)
    
    labels = df_sorted['정당명'].tolist() + ['Dummy']
    values = df_sorted['최종의석'].tolist() + [total_seats]
    colors = df_sorted['Color'].tolist() + ['rgba(0,0,0,0)']

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color='#ffffff', width=2)),
        hole=0.4, rotation=270, direction='clockwise',
        textinfo='label+value', textposition='inside', hoverinfo='label+value+percent'
    )])
    
    fig.update_layout(
        showlegend=False, margin=dict(t=30, b=0, l=0, r=0),
        height=400, title_text=f"최종 의회 구성 (총 {total_seats}석)", title_x=0.5
    )
    fig.update_traces(texttemplate="%{label}%{value}석", selector=dict(type='pie'))
try: fig.data[0].textfont.color = ['white'] * len(df_sorted) + ['rgba(0,0,0,0)']
except: pass
return fig

--- 7. Streamlit UI 렌더링 ---
st.set_page_config(page_title="고급 선거 및 연정 시뮬레이터", layout="wide")
st.title("🏛️ 정치학 선거제도 및 연립정부 시뮬레이터 V2.1.0")

if 'party_data' not in st.session_state:
st.session_state.party_data = pd.DataFrame([
{'정당명': '노동당', '정당 상태': '기성', '이전 득표율(%)': 30.0, '득표율(%)': 35.0, '지역구의석': 90, '이념위치(1-10)': 3.0},
{'정당명': '녹색당', '정당 상태': '기성', '이전 득표율(%)': 6.0, '득표율(%)': 8.0, '지역구의석': 2, '이념위치(1-10)': 2.0},
{'정당명': '자유당', '정당 상태': '기성', '이전 득표율(%)': 20.0, '득표율(%)': 15.0, '지역구의석': 15, '이념위치(1-10)': 5.0},
{'정당명': '보수당', '정당 상태': '기성', '이전 득표율(%)': 35.0, '득표율(%)': 28.0, '지역구의석': 85, '이념위치(1-10)': 7.0},
{'정당명': '대안우파당', '정당 상태': '신설/분열', '이전 득표율(%)': 0.0, '득표율(%)': 4.5, '지역구의석': 0, '이념위치(1-10)': 9.0}
])

with st.sidebar:
st.header("⚙️ 선거제도 설정")
election_system = st.selectbox(
"적용할 선거제도",
["단순 비례대표제", "병립형 비례대표제 (혼합형)", "연동형 비례대표제 (MMP)", "단기이양식 선호투표제 (STV 간이모델)", "결선투표제 (간이모델)", "단순다수제 (소선거구제 - 큐브의 법칙 적용)", "제도 비교 모드 (PR vs 단순다수제)"]
)

pr_method = st.selectbox(
    "비례대표 의석 배분 공식",
    ["최고평균법 (동트)", "최고평균법 (생-라귀)", "최대잔여법 (헤어 쿼터)"]
)

st.divider()

apply_premium = st.checkbox("다수당 프리미엄 적용 (1위 당에 의석 선지급)")
premium_percent = 0
if apply_premium:
    premium_percent = st.slider("프리미엄 의석 비율 (%)", 10, 50, 50, 5)
    st.caption(f"1위 정당에게 총 의석의 {premium_percent}%를 먼저 지급합니다.")
    
st.divider()

allow_overhang = True
if election_system in ["단순 비례대표제", "단기이양식 선호투표제 (STV 간이모델)", "결선투표제 (간이모델)", "단순다수제 (소선거구제 - 큐브의 법칙 적용)", "제도 비교 모드 (PR vs 단순다수제)"]:
    total_seats = st.number_input("의회 총 의석수", 50, 1000, 300)
    electoral_threshold = st.slider("봉쇄조항 (%)", 0.0, 10.0, 5.0, 0.5) if ("단순 비례" in election_system or "비교 모드" in election_system) else 0.0
else:
    district_seats = st.number_input("총 지역구 의석수", 0, 1000, 299)
    pr_seats = st.number_input("총 비례대표 의석수", 0, 1000, 299)
    total_seats = district_seats + pr_seats
    electoral_threshold = st.slider("봉쇄조항 (%)", 0.0, 10.0, 5.0, 0.5)
    
    if election_system == "연동형 비례대표제 (MMP)":
        allow_overhang = st.checkbox("초과의석 허용", value=True)
        st.caption("체크 해제 시 총 의석수에 맞춰 비례의석을 축소 조정합니다.")
st.subheader("📊 정당 데이터 입력 (파웰-터커 변동성 분석 포함)")
st.caption("‘이전 득표율’과 ‘정당 상태’를 입력하면 파웰-터커(Powell-Tucker) 변동성 지수가 자동 산출됩니다.")

df_to_edit = clean_input_df(st.session_state.party_data)
edited_df = st.data_editor(
df_to_edit,
column_config={
"정당 상태": st.column_config.SelectboxColumn("정당 상태", options=["기성", "신설/분열", "소멸"], required=True)
},
num_rows="dynamic", use_container_width=True
)
cleaned_edit = clean_input_df(edited_df)

st.divider()
result_df = pd.DataFrame()

--- 비교 모드 분기 ---
if election_system == "제도 비교 모드 (PR vs 단순다수제)":
st.subheader("⚖️ 선거제도별 의석 확보 비교")

df_pr = calc_pure_pr(cleaned_edit, total_seats, electoral_threshold, pr_method, premium_percent)
df_cube = calc_fptp_cube_rule(cleaned_edit, total_seats)

actual_seats_pr = int(df_pr['최종의석'].sum())
actual_seats_cube = int(df_cube['최종의석'].sum())

pr_gal = calculate_gallagher_index(df_pr, actual_seats_pr)
pr_enp = calculate_enp(df_pr, actual_seats_pr)
cube_gal = calculate_gallagher_index(df_cube, actual_seats_cube)
cube_enp = calculate_enp(df_cube, actual_seats_cube)
total_vol, vol_a, vol_b = calculate_powell_tucker_volatility(cleaned_edit)

compare_df = pd.DataFrame({
    '정당명': cleaned_edit['정당명'],
    '득표율(%)': cleaned_edit['득표율(%)'].round(2).astype(str) + '%',
    '이념위치(1-10)': cleaned_edit['이념위치(1-10)'].round(1).astype(str),
    '비례대표제 확보의석': df_pr['최종의석'].astype(int).astype(str),
    '단순다수제(큐브) 확보의석': df_cube['최종의석'].astype(int).astype(str)
})

metrics_rows = pd.DataFrame([
    {'정당명': '📊 갤러거 인덱스 (불비례성)', '득표율(%)': '-', '이념위치(1-10)': '-', '비례대표제 확보의석': str(pr_gal), '단순다수제(큐브) 확보의석': str(cube_gal)},
    {'정당명': '🧩 유효 정당 수 (ENP)', '득표율(%)': '-', '이념위치(1-10)': '-', '비례대표제 확보의석': str(pr_enp), '단순다수제(큐브) 확보의석': str(cube_enp)},
    {'정당명': f'📈 총 투표 변동성 (A: {vol_a} / B: {vol_b})', '득표율(%)': '-', '이념위치(1-10)': '-', '비례대표제 확보의석': str(total_vol), '단순다수제(큐브) 확보의석': str(total_vol)}
])
compare_df = pd.concat([compare_df, metrics_rows], ignore_index=True)

st.markdown("##### 🏛️ 거시 지표 및 정당별 의석 비교표")
st.dataframe(compare_df, hide_index=True, use_container_width=True)

chart_df = compare_df.iloc[:-3]
fig_compare = go.Figure()
fig_compare.add_trace(go.Bar(
    x=chart_df['정당명'], y=chart_df['비례대표제 확보의석'].astype(int), 
    name=f'단순 비례대표제 ({pr_method})', marker_color='rgb(55, 83, 109)'
))
fig_compare.add_trace(go.Bar(
    x=chart_df['정당명'], y=chart_df['단순다수제(큐브) 확보의석'].astype(int), 
    name='단순다수제 (큐브의 법칙)', marker_color='rgb(26, 118, 255)'
))
fig_compare.update_layout(
    barmode='group', title='동일 득표율 하의 선거제도별 의석 배분 격차',
    xaxis_title='정당명', yaxis_title='확보 의석수',
    legend_title='선거제도', margin=dict(t=50, b=0, l=0, r=0)
)
st.plotly_chart(fig_compare, use_container_width=True)

csv_data = compare_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 통합 비교 데이터 CSV 다운로드", data=csv_data,
    file_name="선거제도_종합_비교결과.csv", mime="text/csv"
)
--- 단일 선거제도 분기 ---
else:
if election_system == "단순 비례대표제":
result_df = calc_pure_pr(cleaned_edit, total_seats, electoral_threshold, pr_method, premium_percent)
elif election_system == "병립형 비례대표제 (혼합형)":
result_df = calc_parallel(cleaned_edit, pr_seats, electoral_threshold, pr_method)
elif election_system == "연동형 비례대표제 (MMP)":
result_df = calc_mmp(cleaned_edit, total_seats, electoral_threshold, pr_method, allow_overhang)
elif election_system == "단기이양식 선호투표제 (STV 간이모델)":
result_df = calc_stv_proxy(cleaned_edit, total_seats)
elif election_system == "결선투표제 (간이모델)":
result_df = calc_two_round_proxy(cleaned_edit, total_seats, pr_method, premium_percent)
elif election_system == "단순다수제 (소선거구제 - 큐브의 법칙 적용)":
result_df = calc_fptp_cube_rule(cleaned_edit, total_seats)

if not result_df.empty and '최종의석' in result_df.columns:
    actual_total_seats = int(result_df['최종의석'].sum())
    majority_req = (actual_total_seats // 2) + 1
    
    gallagher_val = calculate_gallagher_index(result_df, actual_total_seats)
    enp_val = calculate_enp(result_df, actual_total_seats)
    total_vol, vol_a, vol_b = calculate_powell_tucker_volatility(cleaned_edit)
    
    banzhaf_dict = calculate_banzhaf_index(result_df, actual_total_seats)
    shapley_dict = calculate_shapley_shubik_index(result_df, actual_total_seats)
    
    col1, col2 = st.columns([1.2, 1])
    with col1:
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric(label="⚖️ 갤러거 인덱스", value=f"{gallagher_val}")
        with metric_col2:
            st.metric(label="🧩 유효 정당 수 (ENP)", value=f"{enp_val}")
        with metric_col3:
            st.metric(label="📈 총 투표 변동성", value=f"{total_vol}", help=f"파웰-터커 지수 (Type A: {vol_a} / Type B: {vol_b})")
            
        st.divider()
        st.subheader("🏛️ 의회 다이어그램")
        if actual_total_seats > total_seats:
            st.warning(f"초과의석 발생! 원래 정원({total_seats}석)에서 {actual_total_seats - total_seats}석 증가.")
        elif actual_total_seats < total_seats and election_system == "연동형 비례대표제 (MMP)" and not allow_overhang:
            st.info(f"초과의석 방지 작동: 목표 총 의석({total_seats}석)에 맞추어 비례의석이 축소 배분되었습니다.")
            
        fig_parliament = draw_parliament_chart(result_df)
        st.plotly_chart(fig_parliament, use_container_width=True)

        df_display = result_df[['정당명', '득표율(%)', '이전 득표율(%)', '최종의석', '이념위치(1-10)']].copy()
        df_display['반자프 지수'] = df_display['정당명'].map(banzhaf_dict).fillna(0.0)
        df_display['샤플리-슈빅'] = df_display['정당명'].map(shapley_dict).fillna(0.0)
        
        df_display['득표율(%)'] = df_display['득표율(%)'].round(2).astype(str) + '%'
        df_display['이전 득표율(%)'] = df_display['이전 득표율(%)'].round(2).astype(str) + '%'
        df_display['최종의석'] = df_display['최종의석'].astype(int)
        df_display['이념위치(1-10)'] = df_display['이념위치(1-10)'].round(1)
        df_display['반자프 지수'] = df_display['반자프 지수'].astype(str) + '%'
        df_display['샤플리-슈빅'] = df_display['샤플리-슈빅'].astype(str) + '%'

        st.dataframe(df_display.sort_values('최종의석', ascending=False), hide_index=True, use_container_width=True)
        
    with col2:
        st.subheader(f"🤝 연립정부 시나리오 (과반: {majority_req}석)")
        coalitions = simulate_coalitions(result_df, actual_total_seats, shapley_dict)
        
        if coalitions:
            for i, res in enumerate(coalitions[:5], 1):
                with st.expander(f"[{i}순위] {', '.join(res['coalition'])}", expanded=(i==1)):
                    st.write(f"- **합계 의석:** {res['total_seats']}석")
                    st.write(f"- **이념적 거리:** {res['ideological_spread']}")
                    st.write(f"- **내각 평균 이념 좌표:** {res['weighted_ideology']} (1: 좌파 ~ 10: 우파)")
                    st.write(f"- **연정 주도당(Formateur):** 👑 **{res['formateur']}**")
                    gamson_str = " / ".join([f"{p} {share}%" for p, share in res['gamson'].items()])
                    st.write(f"- **내각 지분(갬슨):** {gamson_str}")
                    st.progress(min(res['total_seats'] / actual_total_seats, 1.0))
        else:
            st.error("과반수를 확보할 수 있는 연합 조합이 없습니다.")
else:
    st.warning("의석 산출 조건에 맞는 데이터가 없습니다.")
