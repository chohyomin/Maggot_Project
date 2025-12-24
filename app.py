import streamlit as st
import pandas as pd
import datetime
import io
import json
import xlsxwriter
import numpy as np
import plotly.graph_objects as go
from meteostat import Point, Hourly

# ------------------------------------------------------
# 0. 시스템 설정
# ------------------------------------------------------
st.set_page_config(
    page_title="Forensic PMI Expert V16.0 (Korea Edition)", 
    layout="wide", 
    page_icon="🇰🇷",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------
# 1. 계산 엔진 (한국형 데이터 & 동적 모델 탑재)
# ------------------------------------------------------
class HenssgeCalculator:
    def __init__(self):
        self.NORMAL_BODY_TEMP = 37.2
    
    def calculate(self, rectal_temp, ambient_temp, body_weight, clothing_factor):
        temp_diff = rectal_temp - ambient_temp
        initial_diff = self.NORMAL_BODY_TEMP - ambient_temp
        
        if temp_diff <= 0 or initial_diff <= 0:
             return None, "계산 불가 (체온 <= 기온)"
        
        weight_correction = (body_weight / 70.0)**0.333
        total_factor = weight_correction * clothing_factor
        
        y = temp_diff / initial_diff
        
        if y >= 1.0:
            estimated_hours = 0
        else:
            COOLING_CONSTANT = 10.0 
            estimated_hours = -COOLING_CONSTANT * np.log(y) * total_factor

        confidence_interval = 2.0 + (estimated_hours * 0.1)
        return estimated_hours, confidence_interval

class MasterPMICalculatorV16:
    def __init__(self):
        self.insect_db = {
            # [기존] 비교용 해외 데이터
            "Lucilia sericata (Global/Avg)": {
                "Type": "일반", 
                "LDT": 9.0, 
                "UDT": 35.0,
                "stages": {"egg": 20, "instar_1": 300, "instar_2": 800, "instar_3_feed": 1400, "instar_3_wander": 2400, "pupa": 4000}
            },
            
            # [NEW] ⭐ 한국형 데이터 (정재봉·윤명희, 2015 논문 기반)
            # 출처: 한국경찰연구 제14권 제1호, pp. 225~240
            "Lucilia sericata (Korea - Busan)": {
                "Type": "한국형(저온적응)", 
                "Source": "Jung & Yoon (2015), Korean Police Studies", 
                "LDT": 4.5,   # 논문 p.231 표3: 발육영점온도 4.5도 (매우 낮음)
                "UDT": 35.0,  # 상한온도는 일반값 차용
                "stages": {
                    # 논문 데이터: 알~유충(702), 번데기(4199), 총(6483)
                    # 702 ADH 내에서 1/2/3령 비율은 일반적 성장 모델 비율로 세분화함
                    "egg": 35,              
                    "instar_1": 150,        
                    "instar_2": 350,        
                    "instar_3_feed": 550,   # 3령 섭식기 (마곳 매스 발열 구간)
                    "instar_3_wander": 702, # 논문: 알~유충 완료 시점
                    "pupa": 4901,           # 논문: 유충(702) + 번데기(4199)
                    "adult": 6483           # 논문: 알~성충 우화 완료
                }
            },
            
            "Chrysomya megacephala (대동파리)": {
                "Type": "고온성", "LDT": 10.0, "UDT": 40.0,
                "stages": {"egg": 15, "instar_1": 300, "instar_2": 700, "instar_3_feed": 1300, "instar_3_wander": 2200, "pupa": 3800}
            },
        }

    # [동적 발열 모델]
    def get_dynamic_heat(self, current_bio_adh, stages, max_heat):
        """
        구더기의 생물학적 나이(ADH)에 따라 발열량 차등 적용
        - 알/1령: 0
        - 2령: 30%
        - 3령 섭식(L3 Feeding): 100% (MAX)
        - 3령 배회/번데기: 0~20%
        """
        s2_limit = stages.get('instar_2', 0)
        s3_feed_limit = stages.get('instar_3_feed', 0)
        s3_wander_limit = stages.get('instar_3_wander', 0)
        
        if current_bio_adh < stages.get('instar_1', 0):
            return 0.0
        elif current_bio_adh < s2_limit:
            return max_heat * 0.3
        elif current_bio_adh < s3_feed_limit:
            return max_heat * 1.0 # 섭식기 풀가동 🔥
        elif current_bio_adh < s3_wander_limit:
            return max_heat * 0.2
        else:
            return 0.0

    def calculate(self, species_name, stage, df_weather, correction=1.0, max_maggot_heat=0.0, sun_exposure=0.0, event_params=None, soil_params=None):
        data = self.insect_db[species_name]
        ldt = data['LDT']
        udt = data['UDT']
        stages = data['stages']
        target_adh = stages[stage] # 목표(발견 당시) 총점
        
        accumulated_adh = 0.0
        adh_history = [] 
        estimated_oviposition_time = None
        discovery_time = df_weather['Time'].max()
        avg_air_temp = df_weather['Temp'].mean()

        # 역추적 시작 (현재 -> 과거)
        for idx, row in df_weather.iterrows():
            base_temp = row['Temp']
            time_val = row['Time']
            current_temp = base_temp
            
            # 1. 토양/매장 보정 (Damping Effect)
            if soil_params and soil_params['active']:
                if soil_params['use_measured']:
                    current_temp = soil_params['measured_temp']
                else:
                    depth = soil_params['depth']
                    # 깊이 10cm당 변동폭 1.5% 감소 가정
                    damp = min(1.0, depth * 0.015) 
                    current_temp = (base_temp * (1 - damp)) + (avg_air_temp * damp)
                    # 깊을수록 여름엔 시원함
                    if base_temp > 20: 
                        current_temp -= (depth * 0.05)

            # 2. 동적 마곳 매스 (Dynamic Heat)
            # 현재 시점의 가상 나이(잔존 ADH) 계산
            virtual_age_adh = target_adh - accumulated_adh
            if virtual_age_adh < 0: virtual_age_adh = 0
            
            dynamic_heat = 0.0
            if max_maggot_heat > 0:
                dynamic_heat = self.get_dynamic_heat(virtual_age_adh, stages, max_maggot_heat)
            
            current_temp += dynamic_heat
            current_temp += sun_exposure
            
            # 3. 시나리오 이벤트 (이동, 전기장판 등)
            hours_diff = (discovery_time - time_val).total_seconds() / 3600
            is_event = False
            if event_params and event_params['active']:
                start_window = event_params['end_hours_ago']
                end_window = event_params['end_hours_ago'] + event_params['duration']
                if start_window <= hours_diff <= end_window:
                    current_temp += event_params['temp_increase']
                    is_event = True
            
            # 4. ADH 적산 (LDT 반영)
            eff_heat = 0
            is_over = False
            if current_temp >= udt:
                is_over = True # 상한 초과 시 성장 정체 가정
            elif current_temp > ldt:
                eff_heat = (current_temp - ldt) * correction
            
            accumulated_adh += eff_heat
            
            adh_history.append({
                "Time": time_val,
                "Base_Temp": base_temp,
                "Final_Temp": current_temp,
                "Applied_Maggot_Heat": dynamic_heat,
                "Accumulated_ADH_Reverse": accumulated_adh,
                "Target_ADH": target_adh,
                "Overheat_Status": is_over,
                "Event_Active": is_event
            })
            
            if accumulated_adh >= target_adh:
                estimated_oviposition_time = time_val
                break
        
        return estimated_oviposition_time, accumulated_adh, pd.DataFrame(adh_history)

# ------------------------------------------------------
# 2. UI 및 세션 관리
# ------------------------------------------------------
st.title("⚖️ Forensic PMI Expert V16.0 (Korea Edition)")
st.markdown("##### with Dynamic Heat Model & Jung/Yoon(2015) Data")

# [사이드바] 파일 관리 및 사건 정보
with st.sidebar:
    st.header("💾 사건 파일 관리")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        # 현재 세션 상태 저장
        save_data = {k: v for k, v in st.session_state.items() if isinstance(v, (str, int, float, bool))}
        st.download_button("내보내기 (Save)", json.dumps(save_data), "case_backup.json", "application/json", use_container_width=True)
    with col_s2:
        uploaded_file = st.file_uploader("불러오기", type=['json'], label_visibility="collapsed")
        if uploaded_file is not None:
            data = json.load(uploaded_file)
            st.session_state.update(data)
            st.success("로드 완료")

    st.divider()
    st.header("📝 사건 개요")
    case_id = st.text_input("사건 번호", "2025-KCSI-Busan-01", key="case_id")
    investigator = st.text_input("수사관", "김형사", key="investigator")

# [메인 탭]
tab_henssge, tab_insect, tab_report = st.tabs(["🌡️ 체온 분석(초기)", "🐛 곤충/토양 분석(중기)", "📄 최종 보고서"])

# TAB 1: 헨스게 (초기)
with tab_henssge:
    st.subheader("1. 초기 사망 추정 (Henssge Nomogram)")
    h_calc = HenssgeCalculator()
    c1, c2 = st.columns(2)
    with c1:
        rectal_temp = st.number_input("직장 온도 (°C)", 20.0, 42.0, 36.0, key="rt")
        ambient_temp_h = st.number_input("주변 기온 (°C)", -20.0, 40.0, 20.0, key="at")
    with c2:
        b_weight = st.number_input("체중 (kg)", 30, 150, 70)
        c_factor = st.selectbox("의복/환경", [1.0, 1.2, 1.4, 1.8], format_func=lambda x: f"보정계수 {x}")
    
    if st.button("체온 분석 실행"):
        h_est, h_ci = h_calc.calculate(rectal_temp, ambient_temp_h, b_weight, c_factor)
        if h_est:
            st.session_state['henssge_res'] = f"{h_est:.1f}시간 (±{h_ci:.1f})"
            st.success(f"추정 결과: {st.session_state['henssge_res']}")
        else:
            st.error(h_ci)

# TAB 2: 곤충/토양 (중기) - 핵심 기능
with tab_insect:
    st.subheader("2. 곤충 및 환경 정밀 분석")
    cal_v16 = MasterPMICalculatorV16()
    
    # 설정 패널
    with st.expander("⚙️ 분석 설정 (Dynamic Heat & Event)", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            # 파리 종 선택 (한국형 데이터 강조)
            sp_options = list(cal_v16.insect_db.keys())
            sp = st.selectbox("파리 종 (Species)", sp_options, index=1, help="Jung & Yoon(2015) 데이터는 'Korea-Busan'을 선택하세요.")
            
            # 성장 단계 선택
            stage_opts = list(cal_v16.insect_db[sp]['stages'].keys())
            stg = st.selectbox("성장 단계 (Stage)", stage_opts, index=3)
            
            # 동적 마곳 매스
            use_maggot = st.checkbox("마곳 매스 (발열) 적용", value=True)
            max_heat = st.slider("최대 발열량 (Max Heat)", 0.0, 20.0, 5.0, disabled=not use_maggot)
            if use_maggot: st.caption("ℹ️ 동적 모델: 3령 섭식기에만 발열이 적용됩니다.")

        with col_b:
            # 일사량
            sun = st.radio("일사량", ["양지(+5)", "음지(-2)", "없음/매장(0)"], index=1, horizontal=True)
            sun_v = 5.0 if "양지" in sun else (-2.0 if "음지" in sun else 0.0)
            
            # 매장/토양
            is_burial = st.checkbox("매장 시신 (Soil Correction)", value=False)
            soil_d = st.slider("매장 깊이 (cm)", 0, 200, 30, disabled=not is_burial)
            soil_cfg = {"active": is_burial, "use_measured": False, "depth": soil_d}
            
            # [NEW] 이벤트 시뮬레이션 (이동/유기)
            st.markdown("---")
            use_event = st.checkbox("이벤트 시뮬레이션 (이동/유기)", value=False)
            ev_temp = st.number_input("변화 온도 (+/-)", -20.0, 50.0, 15.0, disabled=not use_event, help="예: 트렁크 안이라면 +15도")
            ev_dur = st.number_input("지속 시간 (h)", 1, 48, 2, disabled=not use_event)
            ev_end = st.number_input("종료 시점 (시간 전)", 0, 72, 6, disabled=not use_event, help="발견 몇 시간 전에 끝났나요?")
            ev_cfg = {"active": use_event, "temp_increase": ev_temp, "duration": ev_dur, "end_hours_ago": ev_end}

    # 날씨 데이터 확보
    st.divider()
    cw1, cw2, cw3 = st.columns([2, 2, 1])
    with cw1:
        # 주요 도시 좌표
        loc_map = {"부산 (Busan)": (35.1796, 129.0756), "서울 (Seoul)": (37.5665, 126.9780), "대구 (Daegu)": (35.8714, 128.6014)}
        sel_loc = st.selectbox("기상 관측소", list(loc_map.keys()))
    with cw2:
        rng = st.date_input("분석 기간", (datetime.date.today()-datetime.timedelta(days=30), datetime.date.today()))
    with cw3:
        st.write("") 
        if st.button("📡 날씨 데이터 로드 (API)"):
            pt = Point(*loc_map[sel_loc])
            dt = Hourly(pt, datetime.datetime.combine(rng[0], datetime.time.min), datetime.datetime.combine(rng[1], datetime.time.max)).fetch()
            if not dt.empty:
                st.session_state['w_data_v16'] = dt.reset_index().rename(columns={'time':'Time','temp':'Temp'}).sort_values('Time', ascending=False).interpolate()
                st.success(f"데이터 확보: {len(dt)}건")
            else:
                st.error("데이터 없음")

    # 계산 실행
    if 'w_data_v16' in st.session_state:
        est_ovi, tot_adh, df_log = cal_v16.calculate(
            sp, stg, st.session_state['w_data_v16'], 
            max_maggot_heat=max_heat if use_maggot else 0, 
            sun_exposure=sun_v, 
            soil_params=soil_cfg,
            event_params=ev_cfg
        )
        
        if est_ovi:
            st.divider()
            st.success(f"🏁 추정 산란(사망) 시각: {est_ovi.strftime('%Y-%m-%d %H:%M')}")
            
            # 야간 산란 경고
            if est_ovi.hour >= 20 or est_ovi.hour < 6:
                st.warning(f"⚠️ 야간({est_ovi.hour}시) 산란 경고: 실제 산란은 '전날 일몰 직전'일 가능성이 높습니다.")
            
            # 그래프 시각화
            fig = go.Figure()
            t_data = df_log.sort_values('Time')
            
            # 1. 기온 (Base)
            fig.add_trace(go.Scatter(x=t_data['Time'], y=t_data['Base_Temp'], name='기상청 기온', line=dict(color='gray', dash='dot')))
            # 2. 최종 적용 온도
            fig.add_trace(go.Scatter(x=t_data['Time'], y=t_data['Final_Temp'], name='보정된 현장 온도', line=dict(color='red')))
            # 3. 마곳 발열 (보조축)
            fig.add_trace(go.Scatter(x=t_data['Time'], y=t_data['Applied_Maggot_Heat'], name='구더기 발열량', fill='tozeroy', line=dict(color='orange'), yaxis='y2'))
            # 4. 이벤트 구간
            if use_event:
                event_active = t_data[t_data['Event_Active']==True]
                if not event_active.empty:
                    fig.add_vrect(x0=event_active['Time'].min(), x1=event_active['Time'].max(), fillcolor="blue", opacity=0.1, annotation_text="Event")

            fig.update_layout(
                title="시간 흐름에 따른 온도 변화 및 발열 추적",
                yaxis=dict(title="온도 (°C)"),
                yaxis2=dict(title="발열량", overlaying='y', side='right', range=[0, 20]),
                height=500, hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 결과 저장
            st.session_state['final_report_data'] = df_log
            st.session_state['final_meta'] = {"Case": case_id, "Investigator": investigator, "Species": sp, "Result": str(est_ovi)}

# TAB 3: 보고서
with tab_report:
    st.header("📄 수사 보고서 생성")
    if 'final_report_data' in st.session_state:
        st.markdown(f"**사건번호:** {st.session_state['final_meta']['Case']}")
        st.markdown(f"**분석결과:** {st.session_state['final_meta']['Result']}")
        st.info("데이터 출처: Jung & Yoon (2015), Meteostat API")
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            # 메타데이터
            pd.DataFrame([st.session_state['final_meta']]).to_excel(writer, sheet_name='Summary', index=False)
            # 로그 데이터
            st.session_state['final_report_data'].to_excel(writer, sheet_name='Log_Data', index=False)
            
        st.download_button("📥 전체 리포트 다운로드 (XLSX)", buf, f"Report_{case_id}.xlsx", "application/vnd.ms-excel", type="primary")
    else:
        st.info("분석을 먼저 수행해주세요.")