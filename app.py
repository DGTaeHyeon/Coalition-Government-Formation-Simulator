import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import itertools
import numpy as np
import math

# --- 1. 데이터 정제 ---
def clean_input_df(df):
    df_clean = df.copy()
    if df_clean.empty: return df_clean

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

# --- 2. 비례대표 의석 배분 공식 ---
def allocate_pr_seats(votes, num_seats, method):
    seats = pd.Series(0, index=votes.index)
    if num_seats <= 0 or votes.sum() <= 0: return seats
    
    if method == "최대잔여법 (헤어 쿼터)":
        quota = votes.sum() / num_seats
        seats = np.floor(votes / quota).astype(int)
        rem_seats = num_seats - seats.sum()
        if rem_seats > 0:
            remainders = (votes / quota) - seats
            for idx in remainders.nlargest(int(rem_seats)).index:
                seats[idx] += 1
    else:
        for _ in range(int(num_seats)):
            if method == "최고평균법 (동트)":
                quotients = votes / (seats + 1)
            else:
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
                total_planned = df_res['비례의석'].sum()
                if total_planned > 0:
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

def calc_two_round_proxy(df, total_seats, apply_republican_front=False):
    df_res = clean_input_df(df)
    df_res['최종의석'] = 0
    df_res['1차득표'] = df_res['득표율(%)'].copy()
    df_res['2차득표'] = df_res['득표율(%)'].copy()
    
    if df_res.empty or total_seats <= 0: return df_res
    
    # 2차 결선 진출 3당
    top3 = df_res.nlargest(3, '1차득표')
    top3_indices = top3.index.tolist()
    eliminated = df_res[~df_res.index.isin(top3_indices)]
    
    extreme_idx = None
    if apply_republican_front and len(top3_indices) == 3:
        # 이념 중심(5.5)에서 가장 멀리 떨어진 극단 정당 탐색
        distances_from_center = (top3['이념위치(1-10)'] - 5.5).abs()
        extreme_idx = distances_from_center.idxmax()
        
        # 나머지 온건 2당 간의 단일화 (공화국 전선)
        moderates = [idx for idx in top3_indices if idx != extreme_idx]
        stronger_mod = moderates[0] if df_res.loc[moderates[0], '1차득표'] > df_res.loc[moderates[1], '1차득표'] else moderates[1]
        weaker_mod = moderates[1] if stronger_mod == moderates[0] else moderates[0]
        
        # 3위 온건 정당이 1,2위 온건 정당으로 사퇴하며 표 몰아주기
        df_res.loc[stronger_mod, '2차득표'] += df_res.loc[weaker_mod, '1차득표']
        df_res.loc[weaker_mod, '2차득표'] = 0.0
        active_indices = [extreme_idx, stronger_mod]
    else:
        active_indices = top3_indices
        
    # 결선 탈락 정당들의 표 이동 (가장 가까운 생존 정당에게 이동, 투표율 저하 고려 70%만 이동)
    for idx, row in eliminated.iterrows():
        distances = [(t_idx, abs(row['이념위치(1-10)'] - df_res.loc[t_idx, '이념위치(1-10)'])) for t_idx in active_indices]
        closest_idx = min(distances, key=lambda x: x[1])[0]
        df_res.loc[closest_idx, '2차득표'] += row['1차득표'] * 0.7
        df_res.loc[idx, '2차득표'] = 0.0

    # 다수대표제 효과를 위한 제곱 산출 (세제곱은 너무 극단적이므로 제곱 적용)
    df_res['득표_제곱'] = df_res['2차득표'] ** 2
    
    # 공화국 전선 발동 시, 극단 정당은 1:1 대결 구도에서 불리하므로 의석 전환 페널티 부과 (프랑스 RN 사례 반영)
    if apply_republican_front and extreme_idx is not None:
        df_res.loc[extreme_idx, '득표_제곱'] *= 0.5  # 전환 효율 50% 페널티

    total_sq_votes = df_res['득표_제곱'].sum()
    
    if total_sq_votes > 0:
        df_res['최종의석'] = allocate_pr_seats(df_res['득표_제곱'], total_seats, "최대잔여법 (헤어 쿼터)")
        
    return df_res

def calc_fptp_actual(df):
    df_res = clean_input_df(df)
    # 단순다수제: 지역구 의석을 그대로 최종 의석으로 인정. 득표율은 갤러거 인덱스 계산용으로만 사용됨.
    df_res['최종의석'] = df_res['지역구의석'].copy()
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

def classify_party_system_jung(df, total_seats_actual):
    if df.empty or total_seats_actual <= 0: return "판별 불가"
    seats = df[df['최종의석'] > 0]['최종의석'].sort_values(ascending=False).tolist()
    n = len(seats)
    if n == 0: return "판별 불가"
    s_total = total_seats_actual
    s1 = seats[0]
    s2 = seats[1] if n > 1 else 0
    s3 = seats[2] if n > 2 else 0
    r1 = s1 / s_total
    rem1 = s_total - s1
    majority_req = (s_total // 2) + 1
    
    if r1 >= (2 / 3): return "일당지배제"
    if s1 >= majority_req:
        if s2 < (2 / 3) * rem1: return "일당우위제"
        else: return "양당제"
    else:
        if s2 >= (2 / 3) * rem1: return "양당 중심제"
        if n >= 3:
            if (s2 + s3) > s1 and (s2 + s3) >= majority_req and s2 < 2 * s3:
                return "삼당제"
        if n >= 4: return "다당제"
        else: return "다당제 (기타)"

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

# --- 6. 의회 다이어그램 생성 (점 기반) ---
def get_arch_coords(total_seats):
    if total_seats == 0: return [], []
    rows = max(3, int(math.ceil(math.sqrt(total_seats / 2.0))))
    row_radii = [3.0 + i for i in range(rows)]
    total_weight = sum(row_radii)
    
    seats_per_row = [int(round(total_seats * (r / total_weight))) for r in row_radii]
    diff = total_seats - sum(seats_per_row)
    while diff > 0: seats_per_row[-1] += 1; diff -= 1
    while diff < 0: seats_per_row[-1] -= 1; diff += 1
        
    points = []
    for r, num_seats in zip(row_radii, seats_per_row):
        if num_seats == 0: continue
        if num_seats == 1:
            points.append({'x': 0, 'y': r, 'angle': math.pi / 2, 'r': r})
        else:
            for i in range(num_seats):
                theta = math.pi - (math.pi * i / (num_seats - 1))
                points.append({'x': r * math.cos(theta), 'y': r * math.sin(theta), 'angle': theta, 'r': r})
    points.sort(key=lambda p: (p['angle'], p['r']), reverse=True)
    return [p['x'] for p in points], [p['y'] for p in points]

def get_westminster_coords(total_seats):
    if total_seats == 0: return [], []
    left_seats = total_seats // 2
    right_seats = total_seats - left_seats
    rows = max(5, int(math.ceil(math.sqrt(total_seats / 4.0))))
    
    def get_bank(num_seats, is_right):
        x_dir = 1 if is_right else -1
        coords = []
        for i in range(num_seats):
            col = i // rows
            row = i % rows
            coords.append({'x': (2 * x_dir) + (col * x_dir * 1.5), 'y': row * 1.5})
        return coords

    all_coords = get_bank(left_seats, False) + get_bank(right_seats, True)
    all_coords.sort(key=lambda p: p['x'])
    return [p['x'] for p in all_coords], [p['y'] for p in all_coords]

def draw_parliament_chart(df, style="Arch"):
    df_valid = df[df['최종의석'].fillna(0) > 0].copy()
    if df_valid.empty: return go.Figure()
    
    df_sorted = df_valid.sort_values('이념위치(1-10)')
    total_seats = int(df_sorted['최종의석'].sum())
    if total_seats == 0: return go.Figure()
    
    def get_color(ideology):
        try:
            n = max(0.0, min(1.0, (float(ideology) - 1.0) / 9.0))
            return f'rgb({int(255 * (1.0 - n))}, {int(200 * (1.0 - abs(n - 0.5) * 2.0))}, {int(255 * n)})'
        except: return 'rgb(128,128,128)'

    seat_parties, seat_colors = [], []
    for _, row in df_sorted.iterrows():
        seats = int(row['최종의석'])
        seat_parties.extend([row['정당명']] * seats)
        seat_colors.extend([get_color(row['이념위치(1-10)'])] * seats)

    if style == "Arch":
        x_coords, y_coords = get_arch_coords(total_seats)
    else:
        x_coords, y_coords = get_westminster_coords(total_seats)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_coords, y=y_coords, mode='markers',
        marker=dict(size=12, color=seat_colors, line=dict(width=1, color='white')),
        text=seat_parties, hoverinfo='text'
    ))
    
    fig.update_layout(
        showlegend=False, margin=dict(t=30, b=10, l=10, r=10),
        height=400, title_text=f"최종 의회 구성 (총 {total_seats}석)", title_x=0.5,
        xaxis=dict(visible=False, showgrid=False, zeroline=False),
        yaxis=dict(visible=False, showgrid=False, zeroline=False),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
    )
    if style == "Arch":
        fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig

# ==========================================
# --- 7. Streamlit UI 렌더링 (화면 구성부) ---
# ==========================================
st.set_page_config(page_title="의회 및 연정 구성 시뮬레이터", layout="wide")
st.title("🏛️ 의회 및 연정 구성 시뮬레이터")

if 'party_data' not in st.session_state:
    st.session_state.party_data = pd.DataFrame([
        {'정당명': '정당 A', '정당 상태': '기성', '이전 득표율(%)': 30.0, '득표율(%)': 35.0, '지역구의석': 90, '이념위치(1-10)': 3.0},
        {'정당명': '정당 B', '정당 상태': '기성', '이전 득표율(%)': 35.0, '득표율(%)': 28.0, '지역구의석': 85, '이념위치(1-10)': 7.0},
        {'정당명': '정당 C', '정당 상태': '기성', '이전 득표율(%)': 20.0, '득표율(%)': 15.0, '지역구의석': 15, '이념위치(1-10)': 5.0},
        {'정당명': '정당 D', '정당 상태': '기성', '이전 득표율(%)': 6.0, '득표율(%)': 8.0, '지역구의석': 2, '이념위치(1-10)': 2.0},
        {'정당명': '정당 E', '정당 상태': '신설/분열', '이전 득표율(%)': 0.0, '득표율(%)': 4.5, '지역구의석': 0, '이념위치(1-10)': 9.0}
    ])

with st.sidebar:
    st.header("⚙️ 선거제도 설정")
    election_system = st.selectbox(
        "적용할 선거제도",
        ["단순 비례대표제", "병립형 비례대표제 (혼합형)", "연동형 비례대표제 (MMP)", "단기이양식 선호투표제 (STV 간이모델)", "결선투표제 (프랑스식 2024 모델)", "단순다수제 (소선거구제 - 지역구의석 직접반영)"]
    )
    
    chart_style = st.selectbox("의회 다이어그램 스타일", ["Arch", "Westminster"])
    
    apply_comparative_mode = st.toggle("📊 제도 비교 모드 켜기", value=False, help="현재 선택한 제도와 단순 비례대표제(PR)의 결과를 나란히 대조합니다.")
    st.divider()

    if election_system not in ["결선투표제 (프랑스식 2024 모델)", "단순다수제 (소선거구제 - 지역구의석 직접반영)"]:
        pr_method = st.selectbox("비례대표 의석 배분 공식", ["최고평균법 (동트)", "최고평균법 (생-라귀)", "최대잔여법 (헤어 쿼터)"])
    else:
        pr_method = "최대잔여법 (헤어 쿼터)"

    premium_percent = 0
    if election_system == "단순 비례대표제":
        apply_premium = st.checkbox("다수당 프리미엄 적용 (1위 당에 의석 선지급)")
        if apply_premium:
            premium_percent = st.slider("프리미엄 의석 비율 (%)", 10, 50, 50, 5)
            
    apply_republican_front = False
    if election_system == "결선투표제 (프랑스식 2024 모델)":
        apply_republican_front = st.checkbox("공화국 전선 (전략적 단일화) 적용", value=True)
        st.caption("1~3위 중 가장 극단적인 정당을 고립시키기 위해 온건 성향의 정당들이 3위 사퇴로 단일화를 이룹니다. (2024년 프랑스 총선 NFP-앙상블 전략 반영)")

    st.divider()
    
    allow_overhang = True
    if election_system == "단순다수제 (소선거구제 - 지역구의석 직접반영)":
        st.info("💡 소선거구제 모드에서는 사용자가 입력한 '지역구의석'이 그대로 100% 최종 의석에 반영됩니다. 총 의석수는 자동 계산됩니다.")
        total_seats = 0 # 나중에 합산으로 결정
        electoral_threshold = 0.0
    elif election_system in ["단순 비례대표제", "단기이양식 선호투표제 (STV 간이모델)", "결선투표제 (프랑스식 2024 모델)"]:
        total_seats = st.number_input("의회 총 의석수", 50, 1000, 300)
        electoral_threshold = st.slider("봉쇄조항 (%)", 0.0, 10.0, 5.0, 0.5) if election_system == "단순 비례대표제" else 0.0
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
    column_config={"정당 상태": st.column_config.SelectboxColumn("정당 상태", options=["기성", "신설/분열", "소멸"], required=True)},
    num_rows="dynamic", use_container_width=True
)
cleaned_edit = clean_input_df(edited_df)
st.divider()

# ==========================================
# --- 8. 분기 1: 제도 비교 모드 ---
# ==========================================
if apply_comparative_mode:
    st.subheader(f"⚖️ {election_system} vs 단순 비례대표제 비교")
    
    # FPTP의 경우 total_seats가 0이므로 베이스를 계산할 임시 total_seats를 구함
    temp_total = int(cleaned_edit['지역구의석'].sum()) if election_system == "단순다수제 (소선거구제 - 지역구의석 직접반영)" else total_seats
    temp_total = temp_total if temp_total > 0 else 300
    
    df_base = calc_pure_pr(cleaned_edit, temp_total, electoral_threshold, "최고평균법 (동트)", 0)
    
    if election_system == "단순 비례대표제": df_target = calc_pure_pr(cleaned_edit, total_seats, electoral_threshold, pr_method, premium_percent)
    elif election_system == "병립형 비례대표제 (혼합형)": df_target = calc_parallel(cleaned_edit, pr_seats, electoral_threshold, pr_method)
    elif election_system == "연동형 비례대표제 (MMP)": df_target = calc_mmp(cleaned_edit, total_seats, electoral_threshold, pr_method, allow_overhang)
    elif election_system == "단기이양식 선호투표제 (STV 간이모델)": df_target = calc_stv_proxy(cleaned_edit, total_seats)
    elif election_system == "결선투표제 (프랑스식 2024 모델)": df_target = calc_two_round_proxy(cleaned_edit, total_seats, apply_republican_front)
    elif election_system == "단순다수제 (소선거구제 - 지역구의석 직접반영)": df_target = calc_fptp_actual(cleaned_edit)
    
    actual_seats_base = int(df_base['최종의석'].sum())
    actual_seats_target = int(df_target['최종의석'].sum())
    
    base_gal = calculate_gallagher_index(df_base, actual_seats_base)
    base_enp = calculate_enp(df_base, actual_seats_base)
    base_sys = classify_party_system_jung(df_base, actual_seats_base)
    
    target_gal = calculate_gallagher_index(df_target, actual_seats_target)
    target_enp = calculate_enp(df_target, actual_seats_target)
    target_sys = classify_party_system_jung(df_target, actual_seats_target)
    total_vol, vol_a, vol_b = calculate_powell_tucker_volatility(cleaned_edit)
    
    compare_df = pd.DataFrame({
        '정당명': cleaned_edit['정당명'],
        '득표율(%)': cleaned_edit['득표율(%)'].round(2).astype(str) + '%',
        '이념위치(1-10)': cleaned_edit['이념위치(1-10)'].round(1).astype(str),
        '단순 비례대표제 확보의석': df_base['최종의석'].astype(int).astype(str),
        f'{election_system} 확보의석': df_target['최종의석'].astype(int).astype(str)
    })
    
    metrics_rows = pd.DataFrame([
        {'정당명': '📊 갤러거 인덱스 (불비례성)', '득표율(%)': '-', '이념위치(1-10)': '-', '단순 비례대표제 확보의석': str(base_gal), f'{election_system} 확보의석': str(target_gal)},
        {'정당명': '🧩 정당체제 유형 (정병기)', '득표율(%)': '-', '이념위치(1-10)': '-', '단순 비례대표제 확보의석': f"{base_sys} ({base_enp})", f'{election_system} 확보의석': f"{target_sys} ({target_enp})"},
        {'정당명': f'📈 투표 변동성 (A: {vol_a}/B: {vol_b})', '득표율(%)': '-', '이념위치(1-10)': '-', '단순 비례대표제 확보의석': str(total_vol), f'{election_system} 확보의석': str(total_vol)}
    ])
    compare_df = pd.concat([compare_df, metrics_rows], ignore_index=True)
    
    st.markdown("##### 🏛️ 거시 지표 및 정당별 의석 비교표")
    st.dataframe(compare_df, hide_index=True, use_container_width=True)
    
    chart_df = compare_df.iloc[:-3]
    fig_compare = go.Figure()
    fig_compare.add_trace(go.Bar(x=chart_df['정당명'], y=chart_df['단순 비례대표제 확보의석'].astype(int), name='단순 비례대표제 (동트)', marker_color='rgb(55, 83, 109)'))
    fig_compare.add_trace(go.Bar(x=chart_df['정당명'], y=chart_df[f'{election_system} 확보의석'].astype(int), name=election_system, marker_color='rgb(26, 118, 255)'))
    fig_compare.update_layout(barmode='group', title='제도별 의석 배분 격차', xaxis_title='정당명', yaxis_title='확보 의석수', margin=dict(t=50, b=0, l=0, r=0))
    st.plotly_chart(fig_compare, use_container_width=True)

    csv_data = compare_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(label="📥 통합 비교 데이터 CSV 다운로드", data=csv_data, file_name="선거제도_종합_비교결과.csv", mime="text/csv")

# ==========================================
# --- 9. 분기 2: 단일 선거제도 모드 ---
# ==========================================
else:
    if election_system == "단순 비례대표제": result_df = calc_pure_pr(cleaned_edit, total_seats, electoral_threshold, pr_method, premium_percent)
    elif election_system == "병립형 비례대표제 (혼합형)": result_df = calc_parallel(cleaned_edit, pr_seats, electoral_threshold, pr_method)
    elif election_system == "연동형 비례대표제 (MMP)": result_df = calc_mmp(cleaned_edit, total_seats, electoral_threshold, pr_method, allow_overhang)
    elif election_system == "단기이양식 선호투표제 (STV 간이모델)": result_df = calc_stv_proxy(cleaned_edit, total_seats)
    elif election_system == "결선투표제 (프랑스식 2024 모델)": result_df = calc_two_round_proxy(cleaned_edit, total_seats, apply_republican_front)
    elif election_system == "단순다수제 (소선거구제 - 지역구의석 직접반영)": result_df = calc_fptp_actual(cleaned_edit)

    if not result_df.empty and '최종의석' in result_df.columns:
        actual_total_seats = int(result_df['최종의석'].sum())
        majority_req = (actual_total_seats // 2) + 1
        
        gallagher_val = calculate_gallagher_index(result_df, actual_total_seats)
        enp_val = calculate_enp(result_df, actual_total_seats)
        party_sys_val = classify_party_system_jung(result_df, actual_total_seats)
        total_vol, vol_a, vol_b = calculate_powell_tucker_volatility(cleaned_edit)
        
        banzhaf_dict = calculate_banzhaf_index(result_df, actual_total_seats)
        shapley_dict = calculate_shapley_shubik_index(result_df, actual_total_seats)
        
        col1, col2 = st.columns([1.2, 1])
        with col1:
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1: st.metric(label="⚖️ 갤러거 인덱스", value=f"{gallagher_val}")
            with metric_col2: st.metric(label="🧩 정당체제 (정병기, 2024)", value=f"{party_sys_val}", help=f"라크소-타게페라 ENP: {enp_val}")
            with metric_col3: st.metric(label="📈 총 투표 변동성", value=f"{total_vol}", help=f"파웰-터커 지수 (Type A: {vol_a} / Type B: {vol_b})")
                
            st.divider()
            st.subheader("🏛️ 의회 다이어그램")
            if election_system != "단순다수제 (소선거구제 - 지역구의석 직접반영)":
                if actual_total_seats > total_seats:
                    st.warning(f"초과의석 발생! 원래 정원({total_seats}석)에서 {actual_total_seats - total_seats}석 증가.")
                elif actual_total_seats < total_seats and election_system == "연동형 비례대표제 (MMP)" and not allow_overhang:
                    st.info(f"초과의석 방지 작동: 목표 총 의석({total_seats}석)에 맞추어 비례의석이 축소 배분되었습니다.")
                
            fig_parliament = draw_parliament_chart(result_df, style=chart_style)
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
