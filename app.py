import streamlit as st
import pandas as pd
import datetime
import io
import json
import xlsxwriter
import numpy as np
import plotly.graph_objects as go
from meteostat import Point, Hourly
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ------------------------------------------------------
# 0. 시스템 설정
# ------------------------------------------------------
st.set_page_config(
    page_title="Forensic AI V22.1 (Final Fix)", 
    layout="wide", 
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------
# 1. AI 두뇌
# ------------------------------------------------------
class AICommanderGemini:
    def __init__(self, api_key, model_name):
        genai.configure(api_key=api_key)
        
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=self.model_name, 
            safety_settings=self.safety_settings
        )
        
    def parse_command(self, user_text):
        system_prompt = """
        You are a Forensic AI Profiler. Output ONLY raw JSON.
        
        Task:
        1. Analyze the text for forensic details.
        2. Detect if any drugs/toxins are mentioned (e.g., Cocaine, Heroin, Amitriptyline, Diabetes meds).
        
        JSON Structure:
        {
            "simulation": {
                "species": "String (Latin name or null)",
                "stage": "String (stage key or null)",
                "maggot_heat": "Float (default 0)",
                "drug_type": "String (Select one: 'None', 'Cocaine', 'Heroin', 'Amitriptyline', 'Methamphetamine') - Default 'None' if not sure",
                "event": {
                    "active": "Boolean",
                    "temp_increase": "Float",
                    "duration": "Integer",
                    "end_hours_ago": "Integer"
                }
            },
            "profiling": {
                "homicide_prob": "Integer (0-100)",
                "suicide_prob": "Integer (0-100)",
                "accident_prob": "Integer (0-100)",
                "reasoning": "String (Short explanation in Korean including drug impact if any)"
            }
        }
        """
        try:
            response = self.model.generate_content(f"{system_prompt}\n\nUser Scenario: {user_text}")
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            st.error(f"⚠️ 모델({self.model_name}) 오류: {e}")
            return None

# ------------------------------------------------------
# 2. 계산 엔진
# ------------------------------------------------------
class MasterPMICalculatorV22:
    def __init__(self):
        self.insect_db = {
            "Lucilia sericata (Korea - Busan)": {"Type": "한국형", "LDT": 4.5, "UDT": 35.0, "stages": {"egg": 35, "instar_1": 150, "instar_2": 350, "instar_3_feed": 550, "instar_3_wander": 702, "pupa": 4901}},
            "Chrysomya megacephala (대동파리)": {"Type": "고온성", "LDT": 10.0, "UDT": 40.0, "stages": {"egg": 15, "instar_1": 300, "instar_2": 700, "instar_3_feed": 1300, "instar_3_wander": 2200, "pupa": 3800}},
            "Lucilia sericata (Global/Avg)": {"Type": "일반", "LDT": 9.0, "UDT": 35.0, "stages": {"egg": 20, "instar_1": 300, "instar_2": 800, "instar_3_feed": 1400, "instar_3_wander": 2400, "pupa": 4000}}
        }
        
        self.drug_effects = {
            "None": {"rate": 1.0, "desc": "영향 없음"},
            "Cocaine": {"rate": 1.5, "desc": "성장 대폭 가속 (발열 증가)"},
            "Heroin": {"rate": 0.8, "desc": "성장 지연"},
            "Amitriptyline": {"rate": 0.9, "desc": "성장 약간 지연 (항우울제)"},
            "Methamphetamine": {"rate": 1.3, "desc": "성장 가속 (필로폰)"}
        }

    def calculate(self, species_name, stage, df_weather, correction=1.0, max_maggot_heat=0.0, event_params=None, drug_type="None"):
        data = self.insect_db[species_name]
        ldt, udt, stages = data['LDT'], data['UDT'], data['stages']
        target_adh = stages[stage]
        accumulated_adh, adh_history = 0.0, []
        discovery_time = df_weather['Time'].max()
        
        drug_factor = self.drug_effects.get(drug_type, {"rate": 1.0})["rate"]

        for idx, row in df_weather.iterrows():
            base_temp = row['Temp']
            current_temp = base_temp
            
            if max_maggot_heat > 0 and accumulated_adh > stages['instar_1']: 
                current_temp += max_maggot_heat
            
            is_event = False
            if event_params and event_params['active']:
                h_diff = (discovery_time - row['Time']).total_seconds() / 3600
                if event_params['end_hours_ago'] <= h_diff <= (event_params['end_hours_ago'] + event_params['duration']):
                    current_temp += event_params['temp_increase']
                    is_event = True

            eff_heat = 0
            if ldt < current_temp < udt:
                eff_heat = (current_temp - ldt) * correction
            
            eff_heat = eff_heat * drug_factor

            accumulated_adh += eff_heat
            
            adh_history.append({
                "Time": row['Time'], 
                "Base_Temp": base_temp,
                "Final_Temp": current_temp,
                "Event": is_event,
                "Drug_Factor": drug_factor
            })
            
            if accumulated_adh >= target_adh: return row['Time'], pd.DataFrame(adh_history)
        return None, pd.DataFrame(adh_history)

# ------------------------------------------------------
# 3. UI 및 제어
# ------------------------------------------------------
st.title("🕵️‍♂️ Forensic AI Profiler V22.1")
st.markdown("##### 🧬 법곤충독성학(Entomotoxicology) 시뮬레이터")

# [수정됨] 안전한 초기화 로직 (하나라도 없으면 채워넣음)
default_values = {
    'sp_idx': 0, 'st_idx': 3, 'max_heat': 5.0, 
    'use_event': False, 'ev_temp': 15.0, 'ev_dur': 2, 'ev_end': 6, 
    'drug_idx': 0, 'ai_log': "준비 완료"
}
for key, val in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = val

with st.sidebar:
    st.header("🧠 AI 모델 선택")
    model_options = [
        "models/gemini-flash-latest",    
        "models/gemini-pro-latest",      
        "models/gemini-2.0-flash-exp"
    ]
    selected_model = st.selectbox("사용할 AI 모델:", model_options, index=0)

    st.divider()
    st.header("🎙️ 수사 시나리오")
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        ai_available = True
    else:
        api_key = None
        ai_available = False
        st.error("API Key 없음")

    user_voice = st.text_area("상황 묘사", placeholder="예: 시신에서 코카인 가루가 발견되었고, 대동파리 3령이 채집됨.", height=150)
    
    if st.button("🔍 분석 실행", disabled=not ai_available):
        if user_voice:
            agent = AICommanderGemini(api_key, selected_model)
            with st.spinner(f"AI({selected_model})가 독성학 분석 중입니다..."):
                result = agent.parse_command(user_voice)
            
            if result:
                prof = result.get("profiling", {})
                sim = result.get("simulation", {})
                
                st.divider()
                st.subheader("📊 분석 결과")
                h, s, a = prof.get("homicide_prob", 0), prof.get("suicide_prob", 0), prof.get("accident_prob", 0)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("타살", f"{h}%")
                c2.metric("자살", f"{s}%")
                c3.metric("사고사", f"{a}%")
                st.progress(h)
                st.info(f"💡 **AI 판단:** {prof.get('reasoning')}")

                st.session_state['ai_log'] = "✅ 설정 적용 완료"
                
                if sim.get("species"):
                    for i, k in enumerate(MasterPMICalculatorV22().insect_db.keys()):
                        if sim["species"].split()[0] in k:
                            st.session_state['sp_idx'] = i; break
                if sim.get("stage"):
                    stages = ["egg", "instar_1", "instar_2", "instar_3_feed", "instar_3_wander", "pupa"]
                    if sim["stage"] in stages: st.session_state['st_idx'] = stages.index(sim["stage"])
                if sim.get("event") and sim["event"]["active"]:
                    st.session_state['use_event'] = True
                    st.session_state['ev_temp'] = sim["event"]["temp_increase"]
                    st.session_state['ev_dur'] = sim["event"]["duration"]
                    st.session_state['ev_end'] = sim["event"]["end_hours_ago"]
                
                if sim.get("drug_type"):
                    d_keys = list(MasterPMICalculatorV22().drug_effects.keys())
                    if sim["drug_type"] in d_keys:
                        st.session_state['drug_idx'] = d_keys.index(sim["drug_type"])
                        st.toast(f"💊 약물 감지: {sim['drug_type']} 적용됨!")

                st.rerun()

cal = MasterPMICalculatorV22()
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("1. 곤충 설정")
    sp = st.selectbox("파리 종", list(cal.insect_db.keys()), index=st.session_state['sp_idx'])
    stg = st.selectbox("성장 단계", list(cal.insect_db[sp]['stages'].keys()), index=st.session_state['st_idx'])

with c2:
    st.subheader("2. 이벤트 설정")
    use_ev = st.checkbox("이벤트 적용", value=st.session_state['use_event'])
    e_temp = st.number_input("온도 변화", value=st.session_state['ev_temp'], disabled=not use_ev)
    e_dur = st.number_input("지속 시간", value=st.session_state['ev_dur'], disabled=not use_ev)
    e_end = st.number_input("종료 시점 (발견 전)", value=st.session_state['ev_end'], disabled=not use_ev)

with c3:
    st.subheader("3. 독성학(Drug) 설정")
    d_opts = list(cal.drug_effects.keys())
    # [수정됨] 여기서 에러가 났던 부분을 안전하게 처리했습니다.
    sel_drug = st.selectbox("발견된 약물", d_opts, index=st.session_state.get('drug_idx', 0))
    
    eff_info = cal.drug_effects[sel_drug]
    st.caption(f"📝 효과: {eff_info['desc']}")
    st.metric("성장 속도 배율", f"x{eff_info['rate']}")

st.divider()

if st.button("📡 계산 시작"):
    pt = Point(35.1796, 129.0756)
    w_data = Hourly(pt, datetime.datetime.now()-datetime.timedelta(days=30), datetime.datetime.now()).fetch()
    if not w_data.empty:
        w_df = w_data.reset_index().rename(columns={'time':'Time','temp':'Temp'}).sort_values('Time', ascending=False).interpolate()
        
        est, log = cal.calculate(sp, stg, w_df, max_maggot_heat=5.0, 
                                 event_params={"active": use_ev, "temp_increase": e_temp, "duration": e_dur, "end_hours_ago": e_end},
                                 drug_type=sel_drug)
        
        if est:
            st.success(f"🏁 추정 사망 시각: {est}")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=log['Time'], y=log['Final_Temp'], name='시신 체감 온도', line=dict(color='red')))
            fig.add_trace(go.Scatter(x=log['Time'], y=log['Base_Temp'], name='기상청 기온', line=dict(color='gray', dash='dot')))
            
            if use_ev:
                e_rows = log[log['Event']==True]
                if not e_rows.empty: 
                    fig.add_vrect(x0=e_rows['Time'].min(), x1=e_rows['Time'].max(), fillcolor="blue", opacity=0.1, annotation_text="Event")
            
            st.plotly_chart(fig, use_container_width=True)
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as writer:
                log.to_excel(writer, index=False)
            st.download_button("📥 전체 분석 보고서 다운로드 (Excel)", buf, "Forensic_Full_Report.xlsx")
            
        else: 
            st.error("계산 실패: 성장 가능 환경이 아닙니다.")