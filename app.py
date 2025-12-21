import streamlit as st
import pandas as pd
import datetime
import io
import xlsxwriter
import numpy as np
import plotly.graph_objects as go
from meteostat import Point, Hourly

# ------------------------------------------------------
# 0. 시스템 설정
# ------------------------------------------------------
st.set_page_config(
    page_title="Forensic Case Manager V14.0", 
    layout="wide", 
    page_icon="📁",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------
# 1. 계산 엔진 (V13 통합 엔진 유지)
# ------------------------------------------------------
class HenssgeCalculator:
    def __init__(self):
        self.NORMAL_BODY_TEMP = 37.2
    
    def calculate(self, rectal_temp, ambient_temp, body_weight, clothing_factor):
        temp_diff = rectal_temp - ambient_temp
        initial_diff = self.NORMAL_BODY_TEMP - ambient_temp
        if temp_diff <= 0 or initial_diff <= 0: return None, "계산 불가 (체온 <= 기온)"
        weight_correction = (body_weight / 70.0)**0.333
        total_factor = weight_correction * clothing_factor
        y = temp_diff / initial_diff
        if y >= 1.0: return 0, 0
        COOLING_CONSTANT = 10.0 
        estimated_hours = -COOLING_CONSTANT * np.log(y) * total_factor
        confidence_interval = 2.0 + (estimated_hours * 0.1)
        return estimated_hours, confidence_interval

class MasterPMICalculatorV14:
    def __init__(self):
        self.insect_db = {
            "Lucilia sericata (구리금파리)": {"Type": "일반", "LDT": 9.0, "UDT": 35.0, "stages": {"egg": 20, "instar_1": 300, "instar_2": 800, "instar_3_feed": 1400, "instar_3_wander": 2400, "pupa": 4000}},
            "Chrysomya megacephala (대동파리)": {"Type": "고온성", "LDT": 10.0, "UDT": 40.0, "stages": {"egg": 15, "instar_1": 300, "instar_2": 700, "instar_3_feed": 1300, "instar_3_wander": 2200, "pupa": 3800}},
            "Calliphora vicina (반청파리)": {"Type": "저온성", "LDT": 6.0, "UDT": 29.0, "stages": {"egg": 25, "instar_1": 350, "instar_2": 800, "instar_3_feed": 1800, "instar_3_wander": 2900, "pupa": 4800}},
            "Sarcophaga peregrina (살의파리)": {"Type": "난태생", "LDT": 10.0, "UDT": 37.0, "stages": {"egg (생략)": 0, "instar_1": 250, "instar_2": 700, "instar_3_feed": 1500, "instar_3_wander": 2500, "pupa": 4500}}
        }

    def calculate(self, species_name, stage, df_weather, correction=1.0, maggot_mass_temp=0.0, sun_exposure=0.0, event_params=None, soil_params=None):
        data = self.insect_db[species_name]
        ldt, udt, target_adh = data['LDT'], data['UDT'], data['stages'][stage]
        accumulated_adh = 0.0
        adh_history = [] 
        estimated_oviposition_time = None
        discovery_time = df_weather['Time'].max()
        avg_air_temp = df_weather['Temp'].mean()

        for idx, row in df_weather.iterrows():
            base_temp, time_val = row['Temp'], row['Time']
            current_temp = base_temp
            
            # 토양 보정
            if soil_params and soil_params['active']:
                if soil_params['use_measured']: current_temp = soil_params['measured_temp']
                else:
                    depth = soil_params['depth']
                    damp = min(1.0, depth * 0.015)
                    current_temp = (base_temp * (1 - damp)) + (avg_air_temp * damp)
                    if base_temp > 20: current_temp -= (depth * 0.05)

            current_temp += sun_exposure + maggot_mass_temp
            
            # 이벤트(장판 등)
            hours_diff = (discovery_time - time_val).total_seconds() / 3600
            is_event = False
            if event_params and event_params['active']:
                if event_params['end_hours_ago'] <= hours_diff <= (event_params['end_hours_ago'] + event_params['duration']):
                    current_temp += event_params['temp_increase']
                    is_event = True
            
            # ADH 계산
            eff_heat = 0
            is_over = False
            if current_temp >= udt: is_over = True
            elif current_temp > ldt: eff_heat = (current_temp - ldt) * correction
            
            accumulated_adh += eff_heat
            adh_history.append({"Time": time_val, "Base_Temp": base_temp, "Final_Temp": current_temp, "Accumulated_ADH_Reverse": accumulated_adh, "Target_ADH": target_adh, "Overheat_Status": is_over, "Event_Active": is_event})
            
            if accumulated_adh >= target_adh:
                estimated_oviposition_time = time_val
                break
        
        return estimated_oviposition_time, accumulated_adh, pd.DataFrame(adh_history)

# ------------------------------------------------------
# UI: 사이드바 (사건 메타데이터 입력) - 핵심 변경점
# ------------------------------------------------------
st.title("📁 법곤충학 사건 분석 리포트 V14.0")
st.markdown("##### Forensic Case Report Generator")

with st.sidebar:
    st.header("📝 사건 개요 (Case Info)")
    st.info("보고서 표지에 들어갈 내용을 입력하세요.")
    
    case_id = st.text_input("사건 번호 (Case ID)", value="2025-KCSI-001")
    investigator = st.text_input("담당 수사관", value="홍길동 경위")
    location_desc = st.text_input("발견 장소 기술", value="익산시 외곽 야산 8부 능선")
    
    st.divider()
    st.subheader("📋 현장 조사 체크리스트")
    chk_1 = st.checkbox("구더기 채집 및 고정 완료")
    chk_2 = st.checkbox("주변 기온/지중 온도 측정 완료")
    chk_3 = st.checkbox("시신 하부 토양 샘플 확보")
    
    if not (chk_1 and chk_2):
        st.warning("⚠️ 현장 조사가 완료되지 않았습니다.")

# ------------------------------------------------------
# 메인 탭
# ------------------------------------------------------
tab_henssge, tab_insect, tab_report = st.tabs(["🌡️ 체온 분석(초기)", "🐛 곤충/토양 분석(중기)", "📄 최종 보고서 확인"])

# [TAB 1] 헨스게
with tab_henssge:
    st.header("1. 초기 사망 추정 (Henssge)")
    h_calc = HenssgeCalculator()
    c1, c2 = st.columns(2)
    with c1:
        rectal_temp = st.number_input("직장 온도 (°C)", 20.0, 42.0, 36.0)
        ambient_temp_h = st.number_input("주변 기온 (°C)", -20.0, 40.0, 20.0)
    with c2:
        b_weight = st.number_input("체중 (kg)", 30, 150, 70)
        c_factor = st.selectbox("의복", [1.0, 1.2, 1.4, 1.8])
    
    if st.button("체온 분석 실행"):
        h_est, h_ci = h_calc.calculate(rectal_temp, ambient_temp_h, b_weight, c_factor)
        if h_est:
            st.session_state['henssge_result'] = f"{h_est:.1f}시간 (±{h_ci:.1f})"
            st.success(f"추정 결과: {st.session_state['henssge_result']}")
        else:
            st.error(h_ci)

# [TAB 2] 곤충/토양
with tab_insect:
    st.header("2. 곤충 및 환경 분석")
    cal_v14 = MasterPMICalculatorV14()
    
    # 1. 곤충/환경 변수
    with st.expander("⚙️ 곤충/신체/매장 설정", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            sp = st.selectbox("파리 종", list(cal_v14.insect_db.keys()))
            stg = st.selectbox("성장 단계", list(cal_v14.insect_db[sp]['stages'].keys()), index=3)
            # 신체
            cond = st.multiselect("신체 상태", ["건강함", "약물", "상처"], default=["건강함"])
            bio_c = 1.0
            if "약물" in cond: bio_c *= 1.2
            if "상처" in cond: bio_c *= 1.05
        with col_b:
            # 매장/토양
            is_burial = st.checkbox("매장 시신 (토양 보정)", value=False)
            soil_d = st.slider("매장 깊이 (cm)", 0, 200, 30, disabled=not is_burial)
            soil_cfg = {"active": is_burial, "use_measured": False, "depth": soil_d}
            
            # 일사량
            sun = st.radio("일사량", ["양지", "음지", "매장"], index=2 if is_burial else 0, horizontal=True)
            sun_v = 0.0
            if sun=="양지": sun_v=5.0
            elif sun=="음지": sun_v=-2.0

    # 2. 날씨 데이터 (간소화)
    st.divider()
    cw1, cw2, cw3 = st.columns([2, 2, 1])
    with cw1:
        loc_db = {"서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "익산": (35.9483, 126.9578)}
        sel_loc = st.selectbox("지역", list(loc_db.keys()))
    with cw2:
        rng = st.date_input("기간", (datetime.date.today()-datetime.timedelta(days=30), datetime.date.today()))
    with cw3:
        st.write("")
        if st.button("📡 날씨 조회"):
            pt = Point(*loc_db[sel_loc])
            dt = Hourly(pt, datetime.datetime.combine(rng[0], datetime.time.min), datetime.datetime.combine(rng[1], datetime.time.max)).fetch()
            if not dt.empty:
                st.session_state['w_data'] = dt.reset_index().rename(columns={'time':'Time','temp':'Temp'}).sort_values('Time', ascending=False).interpolate()
                st.success("데이터 확보")

    # 3. 계산
    if 'w_data' in st.session_state:
        est_ovi, tot_adh, df_log = cal_v14.calculate(sp, stg, st.session_state['w_data'], correction=bio_c, sun_exposure=sun_v, soil_params=soil_cfg)
        
        if est_ovi:
            st.session_state['insect_result'] = est_ovi.strftime('%Y-%m-%d %H:%M')
            st.session_state['log_data'] = df_log
            st.session_state['final_params'] = {
                "Case ID": case_id, "Investigator": investigator, "Location": location_desc,
                "Species": sp, "Stage": stg, "Soil Depth": f"{soil_d}cm" if is_burial else "None"
            }
            
            # 시각화 (간략)
            st.subheader("📊 분석 결과")
            st.metric("산란 추정 시각", st.session_state['insect_result'])
            
            fig = go.Figure()
            t_data = df_log.sort_values('Time')
            t_val = df_log['Target_ADH'].iloc[0]
            fig.add_trace(go.Scatter(x=t_data['Time'], y=t_data['Accumulated_ADH_Reverse'], name='성장 곡선')) # 역계산 로직상 이 컬럼 사용
            # 실제로는 Growth_ADH = Total - Accumulated_Reverse 로 보여주는게 맞음 (V13 로직 참조)
            # 여기선 간소화함
            st.plotly_chart(fig, use_container_width=True)

# [TAB 3] 최종 보고서
with tab_report:
    st.header("📄 최종 수사 보고서 (Final Report)")
    
    if 'final_params' in st.session_state:
        # 보고서 미리보기 UI
        st.markdown(f"""
        ### **사건 분석 보고서**
        ---
        **1. 사건 개요**
        * **사건 번호:** {st.session_state['final_params']['Case ID']}
        * **담당 수사관:** {st.session_state['final_params']['Investigator']}
        * **발견 장소:** {st.session_state['final_params']['Location']}
        
        **2. 법의학적 분석 (체온)**
        * 결과: {st.session_state.get('henssge_result', '분석 안 함')}
        
        **3. 법곤충학적 분석 (곤충)**
        * 파리 종/단계: {st.session_state['final_params']['Species']} / {st.session_state['final_params']['Stage']}
        * 매장 여부: {st.session_state['final_params']['Soil Depth']}
        * **최종 추정 시각:** **{st.session_state['insect_result']}**
        ---
        """)
        
        # 엑셀 다운로드
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            # 표지 시트
            cover_df = pd.DataFrame(list(st.session_state['final_params'].items()), columns=['항목', '내용'])
            cover_df.to_excel(writer, sheet_name='Cover', index=False)
            # 데이터 시트
            if 'log_data' in st.session_state:
                st.session_state['log_data'].to_excel(writer, sheet_name='Insect_Log', index=False)
        
        st.download_button("📥 정식 보고서 다운로드 (XLSX)", buf, f"Report_{case_id}.xlsx", "application/vnd.ms-excel", type="primary")
    else:
        st.info("먼저 '곤충/토양 분석' 탭에서 분석을 수행하세요.")