import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import platform
import io
import xlsxwriter
import numpy as np # 통계 계산용

# ------------------------------------------------------
# 0. 시스템 설정
# ------------------------------------------------------
st.set_page_config(
    page_title="Forensic PMI Analyzer V6.0", 
    layout="wide", 
    page_icon="🧬",
    initial_sidebar_state="expanded"
)

def init_korean_font():
    system_name = platform.system()
    if system_name == 'Windows':
        plt.rc('font', family='Malgun Gothic')
    elif system_name == 'Darwin':
        plt.rc('font', family='AppleGothic')
    else:
        plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)

init_korean_font()

# ------------------------------------------------------
# 1. 계산 엔진 (Scientific Logic - UDT & CI 적용)
# ------------------------------------------------------
class MasterPMICalculatorV6:
    def __init__(self):
        self.insect_db = {
            "Lucilia sericata (구리금파리)": {
                "Type": "일반",
                "LDT": 9.0, 
                "UDT": 35.0, # [NEW] 35도 넘으면 성장 멈춤
                "stages": {"egg": 23, "instar_1": 400, "instar_2": 900, "instar_3_feed": 1500, "instar_3_wander": 2500, "pupa": 4500}
            },
            "Chrysomya megacephala (대동파리)": {
                "Type": "고온성",
                "LDT": 10.0,
                "UDT": 40.0, # 더위에 강함
                "stages": {"egg": 18, "instar_1": 350, "instar_2": 800, "instar_3_feed": 1400, "instar_3_wander": 2300, "pupa": 4000}
            },
            "Calliphora vicina (반청파리)": {
                "Type": "저온성",
                "LDT": 6.0,
                "UDT": 29.0, # [NEW] 29도만 넘어도 더워서 못 자람 (여름에 안 보임)
                "stages": {"egg": 25, "instar_1": 380, "instar_2": 850, "instar_3_feed": 1900, "instar_3_wander": 3000, "pupa": 5000}
            },
            "Sarcophaga peregrina (살의파리)": {
                "Type": "난태생",
                "LDT": 10.0,
                "UDT": 37.0,
                "stages": {"egg (생략)": 0, "instar_1": 300, "instar_2": 750, "instar_3_feed": 1600, "instar_3_wander": 2600, "pupa": 4800}
            }
        }

    def calculate(self, species_name, stage, df_weather, correction=1.0, maggot_mass_temp=0.0, sun_exposure=0.0):
        data = self.insect_db[species_name]
        ldt = data['LDT']
        udt = data['UDT'] # 상한 온도
        target_adh = data['stages'][stage]
        
        accumulated_adh = 0.0
        adh_history = [] 
        estimated_oviposition_time = None
        
        # 역계산 Loop
        for idx, row in df_weather.iterrows():
            base_temp = row['Temp']
            time_val = row['Time']
            
            # 1. 온도 보정 (기온 + 일사량 + 마곳매스)
            actual_temp = base_temp + sun_exposure + maggot_mass_temp
            
            # 2. [NEW] UDT (상한 온도) 체크 - 열 스트레스(Heat Stress)
            is_overheated = False
            if actual_temp >= udt:
                effective_heat = 0 # 너무 더워서 성장 정지
                is_overheated = True
            elif actual_temp <= ldt:
                effective_heat = 0 # 너무 추워서 성장 정지
            else:
                effective_heat = (actual_temp - ldt) * correction
            
            accumulated_adh += effective_heat
            
            adh_history.append({
                "Time": time_val,
                "Base_Temp": base_temp,
                "Actual_Temp_Used": actual_temp,
                "Accumulated_ADH_Reverse": accumulated_adh,
                "Target_ADH": target_adh,
                "Overheat_Status": is_overheated # 그래프 표시용
            })
            
            if accumulated_adh >= target_adh:
                estimated_oviposition_time = time_val
                break
        
        return estimated_oviposition_time, accumulated_adh, pd.DataFrame(adh_history)

# ------------------------------------------------------
# 2. 사이드바 (설정)
# ------------------------------------------------------
st.sidebar.title("🧬 수사 변수 설정 (V6.0)")
st.sidebar.markdown("---")

# 2-1. 생물학적 증거
st.sidebar.subheader("1. 곤충 정보")
calculator = MasterPMICalculatorV6()
species_list = list(calculator.insect_db.keys())

selected_species = st.sidebar.selectbox("채집된 파리 종", species_list)
stage_list = list(calculator.insect_db[selected_species]['stages'].keys())
selected_stage = st.sidebar.selectbox("성장 단계", stage_list, index=3)

# DB 정보 표시
sp_info = calculator.insect_db[selected_species]
st.sidebar.info(f"생육범위: {sp_info['LDT']}°C ~ {sp_info['UDT']}°C")

st.sidebar.markdown("---")

# 2-2. 신체 상태
st.sidebar.subheader("2. 신체 및 병리학")
body_condition = st.sidebar.multiselect(
    "상태 선택", ["당뇨병/고혈당", "개방성 상처/출혈", "영양실조", "약물(각성제)"]
)
bio_correction = 1.0
if "당뇨병/고혈당" in body_condition: bio_correction *= 1.1
if "개방성 상처/출혈" in body_condition: bio_correction *= 1.05
if "약물(각성제)" in body_condition: bio_correction *= 1.2
if "영양실조" in body_condition: bio_correction *= 0.95
st.sidebar.caption(f"성장 속도 보정: {bio_correction*100:.0f}%")

# 2-3. 환경 변수 (대폭 강화됨)
st.sidebar.subheader("3. 현장 환경 분석")

# A. 일사량 (Solar Radiation) [NEW]
st.sidebar.markdown("**☀️ 일사량 노출 (Sun Exposure)**")
sun_option = st.sidebar.radio("발견 위치", ["직사광선 (양지)", "부분 그늘", "완전 그늘 (음지/실내)"], index=1)
sun_exposure = 0.0
if sun_option == "직사광선 (양지)": sun_exposure = 5.0 # 표면 온도 상승
elif sun_option == "완전 그늘 (음지/실내)": sun_exposure = -2.0 # 기온보다 서늘함

# B. 마곳 매스
maggot_mass_toggle = st.sidebar.checkbox("구더기 덩어리 발열 (Maggot Mass)")
mass_heat = 0.0
if maggot_mass_toggle:
    mass_heat = st.sidebar.slider("중심 온도 상승", 1.0, 20.0, 5.0)

# C. 접근 지연
barrier_type = st.sidebar.selectbox("은폐 상태", ["완전 노출", "옷 입음 (2h)", "이불/가방 (24h)", "매장 (72h)"])
delay_hours = 0
if "옷" in barrier_type: delay_hours = 2
elif "이불" in barrier_type: delay_hours = 24
elif "매장" in barrier_type: delay_hours = 72

# ------------------------------------------------------
# 3. 메인 대시보드
# ------------------------------------------------------
st.title("⚖️ 법곤충학 정밀 분석기 V6.0 (Masterpiece)")
st.markdown("##### Forensic Entomology Simulator: UDT & Confidence Interval Integration")
st.markdown("---")

if 'weather_data' not in st.session_state:
    st.session_state['weather_data'] = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["📂 기상 데이터", "📊 정밀 분석 결과", "📄 법정 보고서"])

# ================= TAB 1 =================
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("데이터 소스")
        data_source = st.radio("입력 방식", ["가상 시뮬레이션", "CSV 파일 업로드"])
        if data_source == "가상 시뮬레이션":
            sim_days = st.number_input("시뮬레이션 기간(일)", 1, 100, 20)
            if st.button("🔄 가상 데이터 생성", use_container_width=True):
                hours = sim_days * 24
                dates = pd.date_range(end=datetime.datetime.now(), periods=hours, freq='H')[::-1]
                # 여름철 폭염 시나리오 (UDT 테스트용)
                temps = [28 + 8 * np.sin(i/12) + np.random.normal(0, 1) for i in range(hours)]
                st.session_state['weather_data'] = pd.DataFrame({'Time': dates, 'Temp': temps})
                st.success("데이터 생성 완료 (고온 시나리오)")
        else:
            uploaded = st.file_uploader("CSV 파일", type=['csv'])
            if uploaded:
                df = pd.read_csv(uploaded)
                df['Time'] = pd.to_datetime(df['Time'])
                df = df.sort_values(by='Time', ascending=False)
                st.session_state['weather_data'] = df
                st.success("로드 완료")

    with col2:
        if not st.session_state['weather_data'].empty:
            st.line_chart(st.session_state['weather_data'].set_index('Time')['Temp'])

# ================= TAB 2 =================
with tab2:
    if st.session_state['weather_data'].empty:
        st.warning("데이터가 필요합니다.")
    else:
        # 계산
        est_oviposition, total_adh, df_history = calculator.calculate(
            selected_species, selected_stage, st.session_state['weather_data'], 
            bio_correction, mass_heat, sun_exposure
        )
        
        if est_oviposition:
            # 최종 사망 시점
            est_death_time = est_oviposition - datetime.timedelta(hours=delay_hours)
            
            # [NEW] 신뢰 구간 (Confidence Interval) 계산
            # 생물학적 변이(표준편차)를 전체 기간의 5%로 가정
            elapsed_hours = (st.session_state['weather_data']['Time'].iloc[0] - est_oviposition).total_seconds() / 3600
            sigma_hours = elapsed_hours * 0.05 # 표준편차
            confidence_interval = 1.96 * sigma_hours # 95% 신뢰구간 (약 ±2*SD)
            
            ci_min_time = est_death_time - datetime.timedelta(hours=confidence_interval)
            ci_max_time = est_death_time + datetime.timedelta(hours=confidence_interval)

            # KPI
            st.markdown("### 🔍 최종 수사 결론 (95% 신뢰수준)")
            
            # 메인 시간 표시 (아주 크게)
            st.markdown(f"""
            <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;">
                <h4 style="color:#555;">추정 사망 시각 (Estimated Time of Death)</h4>
                <h1 style="color:#d63031;">{est_death_time.strftime('%Y-%m-%d %H:%M')}</h1>
                <h4 style="color:#2d3436;">(오차범위: ± {confidence_interval:.1f} 시간)</h4>
                <p style="color:#636e72;">{ci_min_time.strftime('%m-%d %H:%M')} ~ {ci_max_time.strftime('%m-%d %H:%M')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("1. 산란 시점", est_oviposition.strftime('%m-%d %H:%M'), "Fly Arrival")
            c2.metric("2. 접근 지연(PIA)", f"{delay_hours}h", barrier_type)
            c3.metric("3. 일사량 보정", f"{sun_exposure:+.1f}°C", sun_option)
            
            st.divider()
            
            # 그래프
            st.subheader("📈 성장 시뮬레이션 및 UDT 분석")
            
            df_plot = df_history.sort_values(by='Time')
            df_plot['Growth_ADH'] = total_adh - df_plot['Accumulated_ADH_Reverse']
            df_plot['Growth_ADH'] = df_plot['Growth_ADH'].apply(lambda x: max(0, x))

            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 성장 곡선
            ax.plot(df_plot['Time'], df_plot['Growth_ADH'], color='#E63946', linewidth=2, label='성장 곡선')
            ax.fill_between(df_plot['Time'], df_plot['Growth_ADH'], color='#E63946', alpha=0.1)
            ax.axhline(y=df_history['Target_ADH'].iloc[0], color='#457B9D', linestyle='--', label='목표 ADH')
            
            # [NEW] UDT 초과 구간 표시 (성장 정지 구간)
            # Overheat_Status가 True인 구간을 빨간색 배경으로 칠하기
            overheat_times = df_plot[df_plot['Overheat_Status'] == True]['Time']
            if not overheat_times.empty:
                # 구간으로 묶어서 칠하기 (간략화)
                for t in overheat_times:
                    ax.axvspan(t - datetime.timedelta(minutes=30), t + datetime.timedelta(minutes=30), 
                               color='orange', alpha=0.3, lw=0)
                # 범례 추가용 가짜 플롯
                ax.plot([], [], color='orange', alpha=0.3, label='성장 정지 구간 (Heat Stress > UDT)', linewidth=5)

            # 마커
            ax.scatter(est_oviposition, 0, color='black', s=100, zorder=5, label='산란 시점')
            
            title_sp = selected_species.split('(')[0]
            ax.set_title(f"Growth Model: {title_sp} (LDT:{sp_info['LDT']}~UDT:{sp_info['UDT']})", fontsize=12)
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            fig.patch.set_alpha(0)
            st.pyplot(fig)
            
        else:
            st.error("분석 실패. 기간 부족.")

# ================= TAB 3 =================
with tab3:
    st.subheader("📄 법정 제출용 보고서")
    
    if not st.session_state['weather_data'].empty and 'est_death_time' in locals() and est_death_time:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # 요약 시트
            summary = {
                'Parameter': ['분석일시', '파리종', 'LDT', 'UDT', '산란추정', '사망추정(중앙값)', '오차범위(±)', '최소범위', '최대범위', '일사량', '지연시간'],
                'Value': [
                    datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                    selected_species, sp_info['LDT'], sp_info['UDT'],
                    est_oviposition, est_death_time, 
                    f"{confidence_interval:.1f}h", ci_min_time, ci_max_time,
                    sun_option, f"{delay_hours}h"
                ]
            }
            pd.DataFrame(summary).to_excel(writer, sheet_name='Summary', index=False)
            df_plot.to_excel(writer, sheet_name='Data', index=False)
            
        st.download_button("📥 정밀 보고서 다운로드 (XLSX)", buffer, f"Forensic_Report_Master_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.ms-excel", type="primary")
    else:
        st.info("분석 완료 후 생성됩니다.")