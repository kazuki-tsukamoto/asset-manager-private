import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ページ基本設定
st.set_page_config(page_title="資産管理＆ローンシミュレータ", layout="wide")

# ==========================================
# 0. 共通関数 & session_state 初期化（デフォルト値）
# ==========================================

# 住宅ローン計算エンジン
def simulate_loan(principal, annual_rates, years, prepay_enabled=False, prepay_year=0, prepay_amount=0, prepay_type="返済額軽減型"):
    total_months = years * 12
    balance = principal
    monthly_payment = 0
    yearly_logs = []
    
    is_cleared = False
    actual_cleared_month = total_months

    for y in range(years):
        if is_cleared:
            yearly_logs.append({
                "経過年": y + 1,
                "適用金利(%)": annual_rates[y],
                "月返済額(円)": 0,
                "年間元金返済(円)": 0,
                "年間利息支払(円)": 0,
                "繰り上げ返済額(円)": 0,
                "年末残高(円)": 0,
            })
            continue

        annual_rate = annual_rates[y]
        monthly_rate = (annual_rate / 100) / 12

        yearly_principal = 0
        yearly_interest = 0
        yearly_prepay = 0

        for m_idx in range(12):
            m = y * 12 + m_idx + 1
            remaining_months = total_months - m + 1

            if prepay_enabled and (y + 1) == prepay_year and m_idx == 0:
                actual_prepay = min(balance, prepay_amount)
                balance -= actual_prepay
                yearly_prepay += actual_prepay

                if prepay_type == "返済額軽減型":
                    if monthly_rate > 0:
                        monthly_payment = balance * (monthly_rate * (1 + monthly_rate) ** remaining_months) / ((1 + monthly_rate) ** remaining_months - 1)
                    else:
                        monthly_payment = balance / remaining_months

            if m == 1 or (m - 1) % 60 == 0:
                if monthly_rate > 0:
                    calculated_payment = balance * (monthly_rate * (1 + monthly_rate) ** remaining_months) / ((1 + monthly_rate) ** remaining_months - 1)
                else:
                    calculated_payment = balance / remaining_months

                if m == 1:
                    monthly_payment = calculated_payment
                else:
                    max_payment = monthly_payment * 1.25
                    if prepay_enabled and prepay_type == "期間短縮型" and (y + 1) >= prepay_year:
                        monthly_payment = min(max(monthly_payment, calculated_payment), max_payment)
                    else:
                        monthly_payment = min(calculated_payment, max_payment)

            interest_p = balance * monthly_rate
            principal_p = monthly_payment - interest_p

            if principal_p < 0:
                principal_p = 0

            if balance <= principal_p:
                yearly_principal += balance
                yearly_interest += interest_p
                balance = 0
                is_cleared = True
                actual_cleared_month = m
                break
            else:
                balance -= principal_p
                yearly_principal += principal_p
                yearly_interest += interest_p

        yearly_logs.append({
            "経過年": y + 1,
            "適用金利(%)": annual_rate,
            "月返済額(円)": int(monthly_payment) if not is_cleared or yearly_principal > 0 else 0,
            "年間元金返済(円)": int(yearly_principal),
            "年間利息支払(円)": int(yearly_interest),
            "繰り上げ返済額(円)": int(yearly_prepay),
            "年末残高(円)": int(balance),
        })

    df = pd.DataFrame(yearly_logs)
    return df, is_cleared, actual_cleared_month, balance


# --- session_state 初期化（公開用デフォルト値） ---
if "current_assets" not in st.session_state:
    st.session_state.current_assets = 500  # 初期資産 (万円)

if "cash_ratio" not in st.session_state:
    st.session_state.cash_ratio = 50.0    # 総資産のうち現金の割合 (%)
if "cash_savings_ratio" not in st.session_state:
    st.session_state.cash_savings_ratio = 50.0 # 毎月の貯蓄のうち現金で残す割合 (%)

# 夫の収入
if "husband_monthly_income" not in st.session_state:
    st.session_state.husband_monthly_income = 30.0  # 夫 手取り月収入 (万円)
if "husband_bonus_income" not in st.session_state:
    st.session_state.husband_bonus_income = 60.0    # 夫 年間ボーナス (万円)

# 妻の収入
if "wife_monthly_income" not in st.session_state:
    st.session_state.wife_monthly_income = 20.0     # 妻 手取り月収入 (万円)
if "wife_bonus_income" not in st.session_state:
    st.session_state.wife_bonus_income = 0.0       # 妻 年間ボーナス (万円)

# 夫の昇給スケジュール設定のデフォルト
if "husband_salary_changes" not in st.session_state:
    st.session_state.husband_salary_changes = [
        {"経過年": 1, "月手取り(万円)": 30.0, "年間ボーナス(万円)": 60.0},
        {"経過年": 5, "月手取り(万円)": 35.0, "年間ボーナス(万円)": 80.0},
        {"経過年": 10, "月手取り(万円)": 40.0, "年間ボーナス(万円)": 100.0},
    ]

if "investment_return" not in st.session_state:
    st.session_state.investment_return = 3.0  # 運用利回り (%)
if "sim_years" not in st.session_state:
    st.session_state.sim_years = 30  # シミュレーション年数

# 固定費のデフォルト
if "fixed_expenses" not in st.session_state:
    st.session_state.fixed_expenses = [
        {"項目": "家賃・住宅ローン", "金額(万円)": 10.0, "開始年": 1, "終了年": 30},
        {"項目": "水道光熱費", "金額(万円)": 2.0, "開始年": 1, "終了年": 30},
        {"項目": "通信費", "金額(万円)": 1.0, "開始年": 1, "終了年": 30},
        {"項目": "保険料", "金額(万円)": 1.5, "開始年": 1, "終了年": 30},
    ]

# 変動費のデフォルト
if "variable_expenses" not in st.session_state:
    st.session_state.variable_expenses = [
        {"項目": "食費", "金額(万円)": 6.0, "開始年": 1, "終了年": 30},
        {"項目": "日用品", "金額(万円)": 1.5, "開始年": 1, "終了年": 30},
        {"項目": "娯楽・交際費", "金額(万円)": 2.0, "開始年": 1, "終了年": 30},
        {"項目": "お小遣い", "金額(万円)": 3.0, "開始年": 1, "終了年": 30},
    ]

# ライフイベントのデフォルト
if "life_events" not in st.session_state:
    st.session_state.life_events = [
        {"経過年": 3, "イベント名": "車の買い替え", "金額(万円)": -200},
        {"経過年": 10, "イベントName": "子供の大学入学", "金額(万円)": -300},
    ]

# 児童手当・NISAシミュレータ用の初期値
if "child1_allowance" not in st.session_state:
    st.session_state.child1_allowance = 1.5
if "child1_years" not in st.session_state:
    st.session_state.child1_years = 15
if "child2_allowance" not in st.session_state:
    st.session_state.child2_allowance = 1.0
if "child2_years" not in st.session_state:
    st.session_state.child2_years = 18
if "child_nisa_return" not in st.session_state:
    st.session_state.child_nisa_return = 5.0

# 確定拠出年金 (DC) 初期値
if "dc_self_monthly" not in st.session_state:
    st.session_state.dc_self_monthly = 1.0
if "dc_company_monthly" not in st.session_state:
    st.session_state.dc_company_monthly = 1.0
if "dc_current_assets" not in st.session_state:
    st.session_state.dc_current_assets = 100.0
if "dc_return_rate" not in st.session_state:
    st.session_state.dc_return_rate = 5.0
if "dc_years" not in st.session_state:
    st.session_state.dc_years = 30


def get_total_expenses_for_year(year):
    """指定した年（経過年）に発生している固定費・変動費の合計を計算する"""
    df_fixed = pd.DataFrame(st.session_state.fixed_expenses)
    df_var = pd.DataFrame(st.session_state.variable_expenses)
    
    fixed_sum = 0.0
    if not df_fixed.empty and "金額(万円)" in df_fixed.columns:
        for _, row in df_fixed.iterrows():
            start = row.get("開始年", 1)
            end = row.get("終了年", 30)
            if pd.isna(start): start = 1
            if pd.isna(end): end = 30
            if int(start) <= year <= int(end):
                fixed_sum += float(row["金額(万円)"])

    var_sum = 0.0
    if not df_var.empty and "金額(万円)" in df_var.columns:
        for _, row in df_var.iterrows():
            start = row.get("開始年", 1)
            end = row.get("終了年", 30)
            if pd.isna(start): start = 1
            if pd.isna(end): end = 30
            if int(start) <= year <= int(end):
                var_sum += float(row["金額(万円)"])
                
    return float(fixed_sum), float(var_sum), float(fixed_sum + var_sum)


def get_husband_income_for_year(year):
    """指定した経過年における夫の手取り月給とボーナスを取得する"""
    df_changes = pd.DataFrame(st.session_state.husband_salary_changes)
    if df_changes.empty or "経過年" not in df_changes.columns:
        return st.session_state.husband_monthly_income, st.session_state.husband_bonus_income
    
    valid_changes = df_changes[df_changes["経過年"] <= year].sort_values(by="経過年")
    if valid_changes.empty:
        return st.session_state.husband_monthly_income, st.session_state.husband_bonus_income
    
    latest = valid_changes.iloc[-1]
    m_inc = float(latest["月手取り(万円)"]) if "月手取り(万円)" in latest else st.session_state.husband_monthly_income
    b_inc = float(latest["年間ボーナス(万円)"]) if "年間ボーナス(万円)" in latest else st.session_state.husband_bonus_income
    return m_inc, b_inc


# ==========================================
# サイドバーメニュー
# ==========================================
st.sidebar.title("📌 メニュー")
page = st.sidebar.radio(
    "ページ選択",
    [
        "🎯 必要現金・キャッシュフロー逆算",
        "📊 資産推移ダッシュボード", 
        "📝 収支・ライフイベント設定", 
        "🏠 住宅ローンシミュレータ",
        "👶 児童手当・積立シミュレータ",
        "🏢 確定拠出年金シミュレータ"
    ]
)

# ==========================================
# PAGE 0: 🎯 必要現金・キャッシュフロー逆算
# ==========================================
if page == "🎯 必要現金・キャッシュフロー逆算":
    st.title("🎯 必要現金・キャッシュフロー動的逆算シミュレータ")
    st.caption("手持ちの現金資産と今後の貯蓄推移を踏まえ、すべてのライフイベントを乗り切るために『その時々で月々最低いくら現金貯蓄に回せていなければいけないか』を動的に算出・可視化します。")

    st.subheader("1. 現金と投資の基本配分設定")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.session_state.cash_ratio = st.slider(
            "現在の総資産のうち『現金』で保有している割合 (%)", 
            min_value=0.0, max_value=100.0, value=float(st.session_state.cash_ratio), step=5.0
        )
        current_cash = st.session_state.current_assets * (st.session_state.cash_ratio / 100.0)
        st.info(f"💡 初期現金クッション: **{current_cash:,.1f} 万円** （総資産 {st.session_state.current_assets:,} 万円）")

    with col_a2:
        st.session_state.cash_savings_ratio = st.slider(
            "毎月の余剰資金のうち『現金貯蓄』に回す割合 (%)", 
            min_value=0.0, max_value=100.0, value=float(st.session_state.cash_savings_ratio), step=5.0
        )
        st.caption(f"※残り {100.0 - st.session_state.cash_savings_ratio:.1f}% は投資やNISA等の運用資産へ回す想定です。")

    st.divider()

    events_df = pd.DataFrame(st.session_state.life_events)
    sim_years = st.session_state.sim_years

    event_exp_map = {}
    event_names_map = {}
    for y in range(1, sim_years + 1):
        if not events_df.empty and "経過年" in events_df.columns:
            y_events = events_df[events_df["経過年"] == y]
            if not y_events.empty:
                net_exp = -1.0 * y_events["金額(万円)"].sum()
                valid_names = y_events["イベント名"].dropna().astype(str).tolist()
                names = " / ".join([n.strip() for n in valid_names if n.strip()])
            else:
                net_exp = 0.0
                names = ""
        else:
            net_exp = 0.0
            names = ""
        event_exp_map[y] = net_exp
        event_names_map[y] = names

    running_cash = current_cash
    cf_logs = []

    for y in range(1, sim_years + 1):
        _, _, monthly_exp = get_total_expenses_for_year(y)
        h_m, h_b = get_husband_income_for_year(y)
        w_m = st.session_state.wife_monthly_income
        w_b = st.session_state.wife_bonus_income
        
        tot_m = h_m + w_m
        tot_b = h_b + w_b
        
        annual_surplus = (tot_m - monthly_exp) * 12 + tot_b
        planned_monthly_cash_savings = (annual_surplus / 12.0) * (st.session_state.cash_savings_ratio / 100.0)

        max_req_monthly = 0.0
        cum_events = 0.0

        for k in range(y, sim_years + 1):
            cum_events += event_exp_map[k]
            months_count = (k - y + 1) * 12
            needed_monthly = (cum_events - running_cash) / months_count
            if needed_monthly > max_req_monthly:
                max_req_monthly = needed_monthly

        req_monthly_savings = max(0.0, max_req_monthly)
        curr_event_exp = event_exp_map[y]
        curr_event_name = event_names_map[y]

        end_cash = running_cash + (planned_monthly_cash_savings * 12) - curr_event_exp

        nisa_drawdown = 0.0
        if end_cash < 0:
            nisa_drawdown = abs(end_cash)
            end_cash = 0.0

        cf_logs.append({
            "経過年": y,
            "期首現金残高(万円)": round(running_cash, 1),
            "年末現金残高(万円)": round(end_cash, 1),
            "予定月間現金貯蓄(万円/月)": round(planned_monthly_cash_savings, 2),
            "必要月間現金貯蓄(万円/月)": round(req_monthly_savings, 2),
            "イベント支出(万円)": round(curr_event_exp, 1),
            "発生イベント": curr_event_name if curr_event_name else "-",
            "不足補填額(万円)": round(nisa_drawdown, 1)
        })

        running_cash = end_cash

    df_cf = pd.DataFrame(cf_logs)
    shortage_rows = df_cf[df_cf["不足補填額(万円)"] > 0]

    if not shortage_rows.empty:
        st.error("⚠️ **現金資金のショートが検知されました！**")
        first_bad = shortage_rows.iloc[0]
        max_bad = shortage_rows.loc[shortage_rows["不足補填額(万円)"].idxmax()]
        
        st.write(
            f"・ **【最初の資金不足】{first_bad['経過年']}年目** にて、"
            f"現金が **約 {first_bad['不足補填額(万円)']:,.1f} 万円** 不足します。"
            f"（イベント: {first_bad['発生イベント']}）"
        )
        
        if max_bad["経過年"] != first_bad["経過年"]:
            st.write(
                f"・ **【最大の資金不足】{max_bad['経過年']}年目** にて、"
                f"単年で最も大きい **約 {max_bad['不足補填額(万円)']:,.1f} 万円** の現金不足が発生します。"
                f"（イベント: {max_bad['発生イベント']}）"
            )
            
        total_shortage = shortage_rows["不足補填額(万円)"].sum()
        st.caption(f"※期間中の累積現金不足額は合計 **約 {total_shortage:,.1f} 万円** です。")
    else:
        st.success("🎉 **クリア！** 設定したすべてのライフイベントにおいて現金が不足することなく乗り切ることができます。")

    st.subheader("2. 📊 キャッシュフロー推移と必要貯蓄額の分析")
    fig_cash = go.Figure()

    fig_cash.add_trace(
        go.Bar(
            x=df_cf["経過年"],
            y=df_cf["イベント支出(万円)"],
            name="ライフイベント支出",
            marker_color="#FFA07A",
            opacity=0.7,
            text=df_cf["発生イベント"],
            textposition="auto",
            hovertemplate="%{x}年目: %{y}万円<br>イベント: %{text}<extra></extra>"
        )
    )

    fig_cash.add_trace(
        go.Scatter(
            x=df_cf["経過年"],
            y=df_cf["年末現金残高(万円)"],
            name="年末現金残高",
            line=dict(color="#1f77b4", width=2.5),
            mode="lines+markers",
            hovertemplate="%{x}年目 現金残高: %{y}万円<extra></extra>"
        )
    )

    fig_cash.update_layout(
        xaxis_title="経過年（年目）",
        yaxis_title="金額・現金残高 (万円)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=20),
        height=400
    )
    st.plotly_chart(fig_cash, use_container_width=True)

    st.divider()
    st.subheader("3. 📋 年別詳細シミュレーションデータ")
    st.dataframe(
        df_cf, 
        use_container_width=True,
        column_config={
            "必要月間現金貯蓄(万円/月)": st.column_config.NumberColumn(
                "最低必要月額(万円)", format="%.2f 万円"
            ),
            "予定月間現金貯蓄(万円/月)": st.column_config.NumberColumn(
                "予定月額(万円)", format="%.2f 万円"
            )
        }
    )

# ==========================================
# PAGE 1: 📊 資産推移ダッシュボード
# ==========================================
elif page == "📊 資産推移ダッシュボード":
    st.title("📊 将来資産シミュレーション・ダッシュボード")

    init_f_tot, init_v_tot, init_m_exp = get_total_expenses_for_year(1)
    init_h_m, init_h_b = get_husband_income_for_year(1)
    init_total_monthly = init_h_m + st.session_state.wife_monthly_income
    init_total_bonus = init_h_b + st.session_state.wife_bonus_income
    init_annual_savings = (init_total_monthly - init_m_exp) * 12 + init_total_bonus

    st.info(
        f"💡 **1年目の世帯総手取り収入: {init_total_monthly * 12 + init_total_bonus:,.1f} 万円/年**\n\n"
        f"💡 **1年目の基本年間貯蓄額: {init_annual_savings:,.1f} 万円/年** "
        f"（月手取り世帯計 {init_total_monthly:.1f}万円 - 月支出 {init_m_exp:.1f}万円 [固定費 {init_f_tot:.1f}万 + 変動費 {init_v_tot:.1f}万]）× 12か月 + ボーナス計 {init_total_bonus:.1f}万円"
    )

    sim_logs = []
    assets = st.session_state.current_assets * 10000
    events_df = pd.DataFrame(st.session_state.life_events)

    for y in range(1, st.session_state.sim_years + 1):
        _, _, monthly_exp = get_total_expenses_for_year(y)
        h_m, h_b = get_husband_income_for_year(y)
        w_m = st.session_state.wife_monthly_income
        w_b = st.session_state.wife_bonus_income
        
        tot_m = h_m + w_m
        tot_b = h_b + w_b
        annual_savings = (tot_m - monthly_exp) * 12 + tot_b
        annual_savings_yen = annual_savings * 10000

        if not events_df.empty and "経過年" in events_df.columns:
            year_events = events_df[events_df["経過年"] == y]
            event_total = year_events["金額(万円)"].sum() * 10000 if not year_events.empty else 0
            
            if not year_events.empty and "イベント名" in year_events.columns:
                valid_names = year_events["イベント名"].dropna().astype(str).tolist()
                valid_names = [name.strip() for name in valid_names if name.strip()]
                event_names = " / ".join(valid_names) if valid_names else "-"
            else:
                event_names = "-"
        else:
            event_total = 0
            event_names = "-"

        investment_gain = assets * (st.session_state.investment_return / 100)
        net_annual_flow = annual_savings_yen + event_total
        assets = assets + investment_gain + net_annual_flow

        sim_logs.append({
            "経過年": y,
            "年末総資産(万円)": int(assets / 10000),
            "夫手取り月収(万円)": h_m,
            "夫ボーナス(万円)": h_b,
            "基本年間貯蓄(万円)": round(annual_savings, 1),
            "イベント影響(万円)": int(event_total / 10000),
            "運用益(万円)": int(investment_gain / 10000),
            "発生イベント": event_names
        })

    df_sim = pd.DataFrame(sim_logs)

    col1, col2, col3 = st.columns(3)
    col1.metric("現在の資産額", f"{st.session_state.current_assets:,} 万円")
    col2.metric(f"{st.session_state.sim_years}年後の想定資産額", f"{df_sim['年末総資産(万円)'].iloc[-1]:,} 万円")
    
    min_asset = df_sim['年末総資産(万円)'].min()
    min_year = df_sim[df_sim['年末総資産(万円)'] == min_asset]['経過年'].values[0]
    col3.metric("最少資産額 (リスク期)", f"{min_asset:,} 万円", f"{min_year}年目")

    if min_asset < 0:
        st.error(f"⚠️ 警告: {min_year}年目に資産が底をつく（赤字になる）可能性があります！")

    st.subheader("📈 総資産額の推移 (万円)")
    st.line_chart(df_sim.set_index("経過年")["年末総資産(万円)"])

    st.subheader("🧱 年間収支とイベント影響の内訳 (万円)")
    st.bar_chart(df_sim.set_index("経過年")[["基本年間貯蓄(万円)", "イベント影響(万円)", "運用益(万円)"]], stack=True)

    with st.expander("年別シミュレーション詳細表を表示"):
        st.dataframe(df_sim, use_container_width=True, column_config={"発生イベント": st.column_config.TextColumn("発生イベント", width="large")})


# ==========================================
# PAGE 2: 📝 収支・ライフイベント設定
# ==========================================
elif page == "📝 収支・ライフイベント設定":
    st.title("📝 収支＆ライフイベント設定")

    st.header("1. 基本収入・資産設定")
    st.session_state.current_assets = st.number_input("現在の貯蓄・資産額 (万円)", value=st.session_state.current_assets, step=50)

    st.subheader("👨‍💼 夫の収入・昇給設定")
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.session_state.husband_monthly_income = st.number_input("夫 手取り月収入 (初期値: 万円)", value=float(st.session_state.husband_monthly_income), step=1.0)
    with col_h2:
        st.session_state.husband_bonus_income = st.number_input("夫 年間ボーナス (初期値: 万円)", value=float(st.session_state.husband_bonus_income), step=10.0)

    edited_h_salary = st.data_editor(pd.DataFrame(st.session_state.husband_salary_changes), num_rows="dynamic", use_container_width=True, key="husband_salary_editor")
    st.session_state.husband_salary_changes = edited_h_salary.to_dict(orient="records")

    st.subheader("👩‍💼 妻の収入設定")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.session_state.wife_monthly_income = st.number_input("妻 手取り月収入 (万円)", value=float(st.session_state.wife_monthly_income), step=1.0)
    with col_w2:
        st.session_state.wife_bonus_income = st.number_input("妻 年間ボーナス (万円)", value=float(st.session_state.wife_bonus_income), step=10.0)

    st.subheader("⚙️ 運用・シミュレーション条件")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.session_state.investment_return = st.number_input("想定運用利回り (年利 %)", value=float(st.session_state.investment_return), step=0.5)
    with col_s2:
        st.session_state.sim_years = st.number_input("シミュレーション年数 (年)", value=int(st.session_state.sim_years), min_value=10, max_value=50)

    st.divider()

    st.header("2. 月間支出の内訳（期間設定対応）")
    col_f, col_v = st.columns(2)

    with col_f:
        st.subheader("📌 固定費")
        edited_fixed = st.data_editor(
            pd.DataFrame(st.session_state.fixed_expenses),
            num_rows="dynamic",
            use_container_width=True,
            key="fixed_editor"
        )
        f_sum_1, _, _ = get_total_expenses_for_year(1)
        st.metric("1年目の固定費 合計", f"{f_sum_1:.1f} 万円/月")

    with col_v:
        st.subheader("🛒 変動費")
        edited_variable = st.data_editor(
            pd.DataFrame(st.session_state.variable_expenses),
            num_rows="dynamic",
            use_container_width=True,
            key="variable_editor"
        )
        _, v_sum_1, _ = get_total_expenses_for_year(1)
        st.metric("1年目の変動費 合計", f"{v_sum_1:.1f} 万円/月")

    if st.button("支出設定（固定費・変動費）を保存"):
        st.session_state.fixed_expenses = edited_fixed.to_dict(orient="records")
        st.session_state.variable_expenses = edited_variable.to_dict(orient="records")
        st.success("固定費・変動費の設定を保存しました！")

    st.divider()

    st.header("3. ライフイベントの登録・編集")
    edited_events = st.data_editor(pd.DataFrame(st.session_state.life_events), num_rows="dynamic", use_container_width=True, key="event_editor")

    if st.button("ライフイベントの設定を保存"):
        st.session_state.life_events = edited_events.to_dict(orient="records")
        st.success("ライフイベントを更新しました！")


# ==========================================
# PAGE 3: 🏠 住宅ローンシミュレータ
# ==========================================
elif page == "🏠 住宅ローンシミュレータ":
    st.title("🏠 変動金利ローンシミュレータ (フル機能版)")

    st.header("1. 基本設定")
    col1, col2, col3 = st.columns(3)
    with col1:
        principal_item = st.number_input("借入金額 (万円)", value=4000, step=100)
    with col2:
        init_annual_rate = st.number_input("初期金利 / 年利 (%)", value=1.0, step=0.1)
    with col3:
        years = st.number_input("返済期間 (年)", value=35, min_value=1, max_value=50)

    principal = principal_item * 10000

    st.header("2. 金利上昇シナリオの設定")
    mode = st.radio("設定パターン", ["一括設定 (定期上昇)", "カスタム設定 (年単位)"], horizontal=True)

    annual_rates = [init_annual_rate] * years

    if mode == "一括設定 (定期上昇)":
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            raise_interval = st.number_input("何年ごとに上昇するか", value=5, min_value=1, max_value=years)
        with col_r2:
            rate_increase = st.number_input("1回あたりの上昇幅 (%)", value=0.25, step=0.05)

        current_r = init_annual_rate
        for y in range(years):
            if y > 0 and y % raise_interval == 0:
                current_r += rate_increase
            annual_rates[y] = round(current_r, 3)
    else:
        cols = st.columns(10)
        for y in range(years):
            with cols[y % 10]:
                annual_rates[y] = st.number_input(f"{y+1}年", value=init_annual_rate, step=0.1, key=f"rate_{y}")

    st.header("3. 基本シミュレーション結果（繰り上げ返済なし）")
    df_base, is_cleared_base, cleared_month_base, final_balance_base = simulate_loan(
        principal, annual_rates, years, prepay_enabled=False
    )

    total_interest_base = df_base["年間利息支払(円)"].sum()
    total_payment_base = df_base["年間元金返済(円)"].sum() + total_interest_base

    col_b1, col_b2, col_b3 = st.columns(3)
    col_b1.metric("総返済額", f"{int(total_payment_base):,} 円")
    col_b2.metric("利息総額", f"{int(total_interest_base):,} 円")
    col_b3.metric("最終月の残高", f"{int(final_balance_base):,} 円" if final_balance_base > 0 else "0 円 (完済)")

    st.subheader("基本グラフ")
    tab1, tab2, tab3 = st.tabs(["内訳推移 (元金 vs 利息)", "月返済額の推移", "ローン残高の推移"])
    with tab1:
        st.bar_chart(df_base.set_index("経過年")[["年間元金返済(円)", "年間利息支払(円)"]], stack=True)
    with tab2:
        st.line_chart(df_base.set_index("経過年")["月返済額(円)"])
    with tab3:
        st.line_chart(df_base.set_index("経過年")["年末残高(円)"])

    st.divider()
    st.header("4. 繰り上げ返済シミュレーション")
    use_prepayment = st.checkbox("繰り上げ返済を実行する", value=False)

    if use_prepayment:
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            prepay_year = st.number_input("実行するタイミング (年目)", value=10, min_value=1, max_value=years)
        with col_p2:
            prepay_amount_item = st.number_input("繰り上げ返済額 (万円)", value=200, step=50)
            prepay_amount = prepay_amount_item * 10000
        with col_p3:
            prepay_type = st.selectbox("返済タイプ", ["返済額軽減型", "期間短縮型"])

        df_pre, is_cleared_pre, cleared_month_pre, final_balance_pre = simulate_loan(
            principal, annual_rates, years, 
            prepay_enabled=True, prepay_year=prepay_year, prepay_amount=prepay_amount, prepay_type=prepay_type
        )

        total_interest_pre = df_pre["年間利息支払(円)"].sum()
        total_payment_pre = df_pre["年間元金返済(円)"].sum() + df_pre["繰り上げ返済額(円)"].sum() + total_interest_pre
        saved_interest = total_interest_base - total_interest_pre

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("総返済額", f"{int(total_payment_pre):,} 円")
        col_r2.metric("利息総額", f"{int(total_interest_pre):,} 円", delta=f"-{int(saved_interest):,} 円", delta_color="inverse")
        col_r3.metric("完済時期", f"{(cleared_month_pre - 1) // 12 + 1}年目" if is_cleared_pre else f"{years}年目")


# ==========================================
# PAGE 4: 👶 児童手当・積立シミュレータ
# ==========================================
elif page == "👶 児童手当・積立シミュレータ":
    st.title("👶 児童手当・扶養手当の積み立てシミュレーション")

    st.header("1. 積み立て条件の設定")
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        st.subheader("👦 1人目")
        c1_amt = st.number_input("月々の手当額 (万円)", value=float(st.session_state.child1_allowance), step=0.5, key="c1_amt_input")
        c1_yrs = st.number_input("受け取り残り年数 (年)", value=int(st.session_state.child1_years), min_value=0, max_value=22, step=1, key="c1_yrs_input")
    with col_c2:
        st.subheader("👧 2人目")
        c2_amt = st.number_input("月々の手当額 (万円)", value=float(st.session_state.child2_allowance), step=0.5, key="c2_amt_input")
        c2_yrs = st.number_input("受け取り残り年数 (年)", value=int(st.session_state.child2_years), min_value=0, max_value=22, step=1, key="c2_yrs_input")
    with col_c3:
        st.subheader("📈 つみたてNISA")
        nisa_rate = st.number_input("想定運用利回り (年利 %)", value=float(st.session_state.child_nisa_return), step=0.5, key="nisa_rate_input")

    st.session_state.child1_allowance = c1_amt
    st.session_state.child1_years = c1_yrs
    st.session_state.child2_allowance = c2_amt
    st.session_state.child2_years = c2_yrs
    st.session_state.child_nisa_return = nisa_rate

    max_yrs = max(c1_yrs, c2_yrs)
    if max_yrs > 0:
        monthly_r = (nisa_rate / 100) / 12
        c1_nisa, c1_cash, c1_principal = 0.0, 0.0, 0.0
        c2_nisa, c2_cash, c2_principal = 0.0, 0.0, 0.0
        logs = []

        for y in range(1, max_yrs + 1):
            c1_monthly = c1_amt if y <= c1_yrs else 0.0
            for m in range(12):
                c1_nisa = (c1_nisa * (1 + monthly_r)) + c1_monthly
            c1_principal += c1_monthly * 12
            c1_cash += c1_monthly * 12

            c2_monthly = c2_amt if y <= c2_yrs else 0.0
            for m in range(12):
                c2_nisa = (c2_nisa * (1 + monthly_r)) + c2_monthly
            c2_principal += c2_monthly * 12
            c2_cash += c2_monthly * 12

            logs.append({
                "経過年": y,
                "合算_NISA総額(万円)": round(c1_nisa + c2_nisa, 1),
                "合算_現金(万円)": round(c1_cash + c2_cash, 1),
            })

        df_child = pd.DataFrame(logs)
        last_row = df_child.iloc[-1]
        st.metric("世帯合算の最終金額", f"{last_row['合算_NISA総額(万円)']:,.1f} 万円")
        st.line_chart(df_child.set_index("経過年")[["合算_現金(万円)", "合算_NISA総額(万円)"]])


# ==========================================
# PAGE 5: 🏢 確定拠出年金シミュレータ
# ==========================================
elif page == "🏢 確定拠出年金シミュレータ":
    st.title("🏢 確定拠出年金 (企業型DC / iDeCo) シミュレータ")

    col_dc1, col_dc2, col_dc3 = st.columns(3)
    with col_dc1:
        dc_self = st.number_input("自己入金額 (万円/月)", value=float(st.session_state.dc_self_monthly), step=0.5, key="dc_self_input")
        dc_company = st.number_input("会社入金額 (万円/月)", value=float(st.session_state.dc_company_monthly), step=0.5, key="dc_company_input")
    with col_dc2:
        dc_assets = st.number_input("現在の資産額 (万円)", value=float(st.session_state.dc_current_assets), step=10.0, key="dc_assets_input")
    with col_dc3:
        dc_return = st.number_input("想定運用利回り (%)", value=float(st.session_state.dc_return_rate), step=0.5, key="dc_return_input")
        dc_yrs = st.number_input("運用年数 (年)", value=int(st.session_state.dc_years), min_value=1, max_value=40, step=1, key="dc_yrs_input")

    monthly_rate = (dc_return / 100) / 12
    current_val = dc_assets * 10000
    accumulated_self = 0.0
    accumulated_company = 0.0
    initial_assets = dc_assets * 10000

    dc_logs = []
    for y in range(1, dc_yrs + 1):
        for m in range(12):
            current_val = (current_val + (dc_self * 10000) + (dc_company * 10000)) * (1 + monthly_rate)
            accumulated_self += (dc_self * 10000)
            accumulated_company += (dc_company * 10000)

        total_principal = initial_assets + accumulated_self + accumulated_company
        dc_logs.append({
            "経過年": y,
            "最終評価額(万円)": round(current_val / 10000, 1),
        })

    df_dc = pd.DataFrame(dc_logs)
    st.metric("受取想定総額", f"{df_dc.iloc[-1]['最終評価額(万円)']:,.1f} 万円")
    st.line_chart(df_dc.set_index("経過年")["最終評価額(万円)"])