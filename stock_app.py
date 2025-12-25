import streamlit as st
import akshare as ak
import pandas as pd
import re
import time

# --- 网页配置 ---
st.set_page_config(page_title="10日线实战系统", layout="wide")

# 初始化缓存：获取全A股代码和名字的映射表
@st.cache_data(ttl=3600) # 缓存1小时，避免频繁请求全量表
def get_name_map():
    try:
        df_spot = ak.stock_zh_a_spot_em()
        return dict(zip(df_spot['代码'], df_spot['名称']))
    except:
        return {}

name_map = get_name_map()

if 'monitor_list' not in st.session_state:
    st.session_state['monitor_list'] = []

st.title("🛡️ 10日线回踩监控 (含中文名称与深度建议)")

# --- 侧边栏 ---
with st.sidebar:
    st.header("📥 股票管理")
    manual_code = st.text_input("手动添加代码", placeholder="如: 301005")
    if st.button("添加"):
        if re.match(r'^\d{6}$', manual_code):
            if manual_code not in st.session_state['monitor_list']:
                st.session_state['monitor_list'].append(manual_code)
                st.rerun()
    
    st.divider()
    batch_input = st.text_area("批量粘贴自选股 (Ctrl+A, Ctrl+C)", height=150)
    if st.button("一键同步"):
        codes = re.findall(r'\d{6}', batch_input)
        if codes:
            st.session_state['monitor_list'] = list(set(st.session_state['monitor_list'] + codes))
            st.success(f"同步成功")

    if st.button("清空名单"):
        st.session_state['monitor_list'] = []
        st.rerun()

# --- 核心分析函数 ---
def analyze_stock(code):
    try:
        # 获取中文名字
        s_name = name_map.get(code, "未知股票")
        
        # 获取K线数据
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
        if df.empty: return None
        
        df = df.rename(columns={'日期': 'Date', '收盘': 'Close', '成交量': 'Volume'})
        df['MA10'] = df['Close'].rolling(window=10).mean()
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        dist = (curr['Close'] - curr['MA10']) / curr['MA10']
        vol_avg = df['Volume'].iloc[-6:-1].mean()
        
        # --- 深度购买建议逻辑 ---
        score = 0
        advice = "观望"
        color = "white"

        if curr['MA10'] > prev['MA10']: # 均线向上
            if 0 <= dist <= 0.025: # 踩线
                if curr['Volume'] < vol_avg:
                    advice = "💎 绝佳买点：缩量回踩强支撑，风险收益比极高，可逢低布局。"
                    score = 3
                else:
                    advice = "⚠️ 警惕：虽在支撑位但抛压尚存，建议分批建仓或等放量止跌。"
                    score = 2
            elif dist > 0.10:
                advice = "🔥 极度超买：远离均线，谨防高位回落，切勿追涨。"
                score = -1
            else:
                advice = "📈 趋势向上：暂未回踩，建议设定10日线预埋单等待。"
                score = 1
        elif curr['Close'] < curr['MA10']:
            advice = "🚫 破位：跌破短线生命线，趋势转坏，建议离场或止损。"
            score = -2
        else:
            advice = "💤 震荡：趋势不明，暂无参与价值。"
            
        return {
            "代码": code,
            "名称": s_name,
            "现价": curr['Close'],
            "10日线": round(curr['MA10'], 2),
            "距均线": f"{dist*100:.2f}%",
            "购买建议": advice,
            "排序分": score
        }
    except:
        return None

# --- 主界面展示 ---
if not st.session_state['monitor_list']:
    st.info("👈 请在左侧添加股票开始监控。")
else:
    results = []
    progress_bar = st.progress(0)
    
    for idx, code in enumerate(st.session_state['monitor_list']):
        res = analyze_stock(code)
        if res: results.append(res)
        progress_bar.progress((idx + 1) / len(st.session_state['monitor_list']))
    
    progress_bar.empty()
    
    if results:
        res_df = pd.DataFrame(results).sort_values(by="排序分", ascending=False)
        
        st.subheader("📊 全自动化实时监控表")
        
        # 优化表格列排序
        display_df = res_df[["名称", "代码", "现价", "10日线", "距均线", "购买建议"]]
        
        # 使用 color-coded 表格
        st.table(display_df)
        
        # 重点推荐区域
        picks = [r for r in results if r['排序分'] >= 3]
        if picks:
            st.divider()
            st.balloons() # 发现高分股时放个气球庆祝一下
            st.success("🎯 发现符合【回踩起爆】条件的极品标的：")
            for p in picks:
                with st.expander(f"查看详情: {p['名称']} ({p['代码']})"):
                    col1, col2 = st.columns(2)
                    col1.metric("现价", f"{p['现价']} 元")
                    col1.write(f"**操作方案：** {p['购买建议']}")
                    col2.metric("回踩深度", p['距均线'])
                    col2.write("**技术面：** 10日线呈上升趋势且今日成功缩量企稳。")
    else:
        st.warning("暂无有效数据。")
