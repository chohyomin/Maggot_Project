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
from PIL import Image

# ------------------------------------------------------
# 0. 시스템 설정 (UX 개선: 넓은 레이아웃 & 아이콘)
# ------------------------------------------------------
st.set_page_config(
    page_title="Forensic AI V24.0 (UX Edition)", 
    layout="wide", 
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------
# 1. AI 두뇌 (멀티모달)
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
        self.model = genai.GenerativeModel(model_name=self.model_name, safety_settings=self.safety_settings)
        
    def parse_command(self, user_text, user_image=None):
        system_prompt = """
        You are a Forensic AI Assistant. 
        Your goal is to help investigators estimate PMI (Post-Mortem Interval).
        
        Task:
        1. Analyze text & image to identify insect species and stage.
        2. Detect drugs (Entomotoxicology).
        3. Identify environmental events (e.g., 'trunk', 'buried').
        
        Output JSON Only:
        {
            "simulation": {
                "species": "String (Latin name)",
                "stage": "String (e.g., 'instar_3_feed')",
                "maggot_heat": "Float (0~5.0)",
                "drug_type": "String (None/Cocaine/Heroin/Methamphetamine/Amitriptyline)",
                "event": { "active": true/false, "temp_increase": Float, "duration": Int, "end_hours_ago": Int }
            },
            "profiling": {
                "summary": "String (One sentence summary for the report)",
                "homicide_prob": Int, "suicide_prob": Int, "accident_prob": Int,
                "reasoning": "String (Korean explanation)"
            }
        }
        """
        try:
            inputs = [system_prompt, "\nScenario: " + user_text]
            if user_image: inputs.append(user_image)
            
            response = self.model.generate_content(inputs)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            return None

# ------------------------------------------------------
# 2. 계산 엔진
# ------------------------------------------------------
class MasterPMICalculatorV24:
    def __init__(self):
        self.insect_db = {
            "Lucilia sericata (Korea - Busan)": {"Type": "한국형", "LDT": 4.5, "UDT": 35.0, "stages": {"egg": 35, "instar_1": 150, "instar_2": 350, "instar_3_feed": 550, "instar_3_wander": 702, "pupa": 4901}},
            "Chrysomya megacephala (대동파리)": {"Type": "고온성", "LDT": 10.0, "UDT": 40.0, "stages": {"egg": 15, "instar_1": 300, "instar_2": 700, "instar_3_feed": 1300, "instar_3_wander": 2200, "pupa": 3800}},
            "Lucilia sericata (Global/Avg)": {"Type": "일반", "LDT": 9.0, "UDT": 35.0, "stages": {"egg": 20, "instar_1": 300, "instar_2": 800, "instar_3_feed": 1400, "instar_3_wander": 2400, "pupa": 4000}}
        }
        self.drug_effects = {
            "None": {"rate": 1.0, "desc": "특이사항 없음"},
            "Cocaine": {"rate": 1.5, "desc": "성장 가속 (발열↑)"},
            "Heroin": {"rate": 0.8, "desc": "성장 지연"},
            "Methamphetamine": {"rate": 1.3, "desc": "성장 가속"},
            "Amitriptyline": {"rate": 0.9, "desc": "성장 지연"}
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
            adh_history.append({"Time": row['Time'], "Base_Temp": base_temp, "Final_Temp": current_temp, "Event": is_event})
            
            if accumulated_adh >= target_adh: return row['Time'], pd.DataFrame(adh_history)
        return None, pd.DataFrame(adh_history)

# ------------------------------------------------------
# 3. UI 및 제어 (User-Centric)
# ------------------------------------------------------
st.title("🕵️‍♂️ Forensic AI Profiler V24.0")
st.caption("AI Assisted Entomological Evidence Analysis System")

# 세션 초기화 (안전하게)
defaults = {'sp_idx': 0, 'st_idx': 3, 'max_heat': 5.0, 'use_event': False, 'ev_temp': 15.0, 'ev_dur': 2, 'ev_end': 6, 'drug_idx': 0, 'ai_result': None, 'scenario_text': ""}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- [Step 1] 사이드바: 입력 및 AI 분석 ---
with st.sidebar:
    st.header("Step 1. 증거 입력")
    
    # 1. AI 모델 선택 (숨김 기능으로 깔끔하게 처리 가능하나 직관성을 위해 유지)
    with st.expander("⚙️ AI 모델 설정", expanded=False):
        model_opts = ["models/gemini-flash-latest", "models/gemini-pro-latest", "models/gemini-2.0-flash-exp"]
        selected_model = st.selectbox("AI Model", model_opts)

    # 2. 빠른 템플릿 (User-Centric: 타이핑 귀찮은 사람을 위해)
    st.markdown("**📝 빠른 시나리오 입력 (Templates)**")
    col_t1, col_t2 = st.columns(2)
    if col_t1.button("🚗 차량 트렁크"):
        st.session_state['scenario_text'] = "대동파리 3령 발견. 시신은 차량 트렁크에 이불로 덮여 있었음. 여름철이라 트렁크 내부 온도가 매우 높았을 것으로 추정됨."
    if col_t2.button("⛰️ 야산 매장"):
        st.session_state['scenario_text'] = "금파리 번데기 발견. 야산 비탈길 낙엽 더미 아래에 얕게 매장되어 있었음. 약물 반응은 없으나 부패가 심함."
        
    # 3. 입력창
    api_key = st.secrets.get("GOOGLE_API_KEY")
    img_file = st.file_uploader("📸 증거 사진 (선택)", type=["jpg", "png"])
    if img_file: st.image(img_file, caption="Evidence Image", use_container_width=True)
    
    user_input = st.text_area("상황 묘사", value=st.session_state['scenario_text'], height=120)
    
    # 4. 분석 버튼
    if st.button("🔍 AI 분석 실행 (Analyze)", type="primary", disabled=not api_key):
        if user_input:
            agent = AICommanderGemini(api_key, selected_model)
            img = Image.open(img_file) if img_file else None
            with st.spinner("증거물 분석 및 프로파일링 중..."):
                res = agent.parse_command(user_input, img)
                if res:
                    st.session_state['ai_result'] = res # 결과 저장
                    
                    # AI가 찾은 값 세션에 반영 (Human-in-the-loop 준비)
                    sim = res['simulation']
                    # 종 자동 매칭
                    if sim.get("species"):
                        for i, key in enumerate(MasterPMICalculatorV24().insect_db.keys()):
                            if sim["species"].split()[0] in key:
                                st.session_state['sp_idx'] = i; break
                    # 단계 자동 매칭
                    if sim.get("stage"):
                        stages = ["egg", "instar_1", "instar_2", "instar_3_feed", "instar_3_wander", "pupa"]
                        if sim["stage"] in stages: st.session_state['st_idx'] = stages.index(sim["stage"])
                    # 이벤트 자동 매칭
                    if sim.get("event") and sim["event"]["active"]:
                        st.session_state['use_event'] = True
                        st.session_state['ev_temp'] = sim["event"]["temp_increase"]
                        st.session_state['ev_dur'] = sim["event"]["duration"]
                        st.session_state['ev_end'] = sim["event"]["end_hours_ago"]
                    # 약물 자동 매칭
                    if sim.get("drug_type"):
                        d_keys = list(MasterPMICalculatorV24().drug_effects.keys())
                        if sim["drug_type"] in d_keys: st.session_state['drug_idx'] = d_keys.index(sim["drug_type"])
                    
                    st.rerun()

# --- [Step 2] 메인 화면: 검토 및 결과 리포트 ---

# AI 분석 결과가 있을 때만 상단에 요약 표시
if st.session_state['ai_result']:
    res = st.session_state['ai_result']
    prof = res.get('profiling', {})
    
    with st.container():
        st.info(f"🤖 **AI 분석 요약:** {prof.get('summary', '분석 완료')}")
        
        # 3단 컬럼으로 확률 표시
        c1, c2, c3 = st.columns(3)
        c1.metric("살인(Homicide)", f"{prof.get('homicide_prob')}%")
        c2.metric("자살(Suicide)", f"{prof.get('suicide_prob')}%")
        c3.metric("사고사(Accident)", f"{prof.get('accident_prob')}%")
        
        with st.expander("💡 AI 추론 근거 보기 (Reasoning)"):
            st.write(prof.get('reasoning'))

st.divider()

st.header("Step 2. 시뮬레이션 설정 확인 (Human Check)")
st.caption("AI가 설정한 값을 확인하고, 필요시 수정하세요. (AI도 틀릴 수 있습니다!)")

cal = MasterPMICalculatorV24()
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. 생물학적 정보")
    sp = st.selectbox("파리 종 (Species)", list(cal.insect_db.keys()), index=st.session_state['sp_idx'])
    stg = st.selectbox("성장 단계 (Stage)", list(cal.insect_db[sp]['stages'].keys()), index=st.session_state['st_idx'])
    max_h = st.slider("마곳 매스 발열 (°C)", 0.0, 20.0, st.session_state['max_heat'], help="구더기 덩어리가 스스로 내는 열")

with col2:
    st.subheader("2. 환경 변수 (Event)")
    use_ev = st.checkbox("특수 환경(트렁크/매장) 적용", value=st.session_state['use_event'])
    e_temp = st.number_input("온도 보정 (°C)", value=st.session_state['ev_temp'], disabled=not use_ev)
    e_dur = st.number_input("지속 시간 (Hours)", value=st.session_state['ev_dur'], disabled=not use_ev)
    e_end = st.number_input("발견 전 (Hours ago)", value=st.session_state['ev_end'], disabled=not use_ev)

with col3:
    st.subheader("3. 독성학 (Toxicology)")
    d_opts = list(cal.drug_effects.keys())
    sel_drug = st.selectbox("발견 약물", d_opts, index=st.session_state['drug_idx'])
    eff = cal.drug_effects[sel_drug]
    st.markdown(f"**효과:** {eff['desc']}")
    st.metric("성장 계수", f"x{eff['rate']}")

st.divider()

# --- [Step 3] 최종 계산 및 리포트 ---
st.header("Step 3. 결과 산출 (Report)")

if st.button("🚀 사망 시간 역추적 시작 (Calculate)", type="primary", use_container_width=True):
    # 날씨 데이터 로드 (부산 좌표 고정)
    pt = Point(35.1796, 129.0756)
    w_data = Hourly(pt, datetime.datetime.now()-datetime.timedelta(days=30), datetime.datetime.now()).fetch()
    
    if not w_data.empty:
        w_df = w_data.reset_index().rename(columns={'time':'Time','temp':'Temp'}).sort_values('Time', ascending=False).interpolate()
        
        # 계산
        est, log = cal.calculate(sp, stg, w_df, max_maggot_heat=max_h,
                                 event_params={"active": use_ev, "temp_increase": e_temp, "duration": e_dur, "end_hours_ago": e_end},
                                 drug_type=sel_drug)
        
        if est:
            # 1. 메인 결과 (크게 보여주기)
            st.success(f"🏁 추정 사망 시각 (PMI): {est.strftime('%Y년 %m월 %d일 %H시 %M분')}")
            st.caption(f"발견 시점으로부터 약 {int((datetime.datetime.now() - est).total_seconds()/3600)}시간 전")
            
            # 2. 그래프
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=log['Time'], y=log['Final_Temp'], name='보정 온도(Ambient)', line=dict(color='#FF4B4B', width=2)))
            fig.add_trace(go.Scatter(x=log['Time'], y=log['Base_Temp'], name='기상청 온도(Base)', line=dict(color='gray', dash='dot')))
            if use_ev:
                e_rows = log[log['Event']==True]
                if not e_rows.empty:
                    fig.add_vrect(x0=e_rows['Time'].min(), x1=e_rows['Time'].max(), fillcolor="blue", opacity=0.1, annotation_text="Event Zone")
            
            fig.update_layout(title="시간 역추적 온도 그래프 (Time-Temperature Profile)", xaxis_title="시간", yaxis_title="온도(°C)", height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. 자동 생성 리포트 (Text Report)
            st.subheader("📄 자동 생성 사건 보고서")
            report_text = f"""
            [법곤충학적 증거 분석 보고서]
            
            1. 사건 개요
            - 분석 일시: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            - 추정 사인: {prof.get('reasoning') if st.session_state.get('ai_result') else '분석 없음'}
            
            2. 증거물 분석
            - 곤충 종: {sp} ({stg})
            - 독성학 소견: {sel_drug} ({eff['desc']})
            
            3. 환경 요인
            - 마곳 매스 발열: +{max_h}°C 적용
            - 특이 환경 보정: {'적용됨' if use_ev else '없음'}
            
            4. 결론
            위 데이터를 종합하여 ADH 모델로 역산한 결과, 
            대상자의 사망 추정 시각은 {est.strftime('%Y-%m-%d %H:%M')} 경으로 판단됨.
            """
            st.text_area("Report Preview", report_text, height=250)
            
            # 4. 엑셀 다운로드
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as writer:
                log.to_excel(writer, index=False)
            st.download_button("💾 데이터 엑셀 다운로드", buf, "Forensic_Data.xlsx")
            
        else:
            st.error("❌ 계산 실패: 현재 환경 조건으로는 곤충이 해당 단계까지 성장할 수 없습니다. (온도가 너무 낮거나 기간 부족)")
    else:
        st.error("⚠️ 기상청 데이터 연결 실패")