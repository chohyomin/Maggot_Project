Forensic AI Profiler V22.0 (Expert Edition)
"법곤충학(Forensic Entomology)과 AI를 결합한 지능형 사망 시간 추정 시뮬레이터"

이 프로젝트는 파리 유충(구더기)의 성장 속도를 역산하여 시신의 **사후 경과 시간(PMI)**을 추정하는 도구입니다. 단순한 온도 계산을 넘어, **생성형 AI(Gemini)**를 활용한 사건 프로파일링과 법곤충독성학(Entomotoxicology) 개념을 적용하여 시신의 약물 복용 여부가 곤충 성장에 미치는 영향까지 시뮬레이션합니다.

✨ 주요 기능 (Key Features)
1. 🧠 AI 사건 프로파일링 (AI Profiling)
자연어 분석: 사용자가 "시신에서 하얀 가루가 발견됨", "트렁크에 유기됨" 등의 상황을 서술하면 AI가 이를 분석합니다.

확률 추론: 타살(Homicide), 자살(Suicide), 사고사(Accident)의 확률을 법의학적 근거를 바탕으로 계산하여 시각화합니다.

자동 파라미터 설정: 시나리오에서 곤충 종류, 성장 단계, 온도 변화 이벤트, 약물 종류를 자동으로 추출하여 시뮬레이터에 적용합니다.

2. 🧬 법곤충독성학 (Entomotoxicology) [New!]
약물 영향 계산: 시신에 남아있는 약물이나 독소가 구더기의 성장 속도를 변화시키는 현상을 구현했습니다.

적용 로직:

Cocaine (코카인): 성장 속도 가속 (x1.5배) → 사망 시간 추정치 보정

Heroin (헤로인): 성장 지연 (x0.8배)

Amitriptyline (항우울제): 성장 지연

Methamphetamine (필로폰): 성장 가속

3. ⚙️ 지능형 모델 교체 시스템 (Model Switcher)
API 유연성: Google Gemini API의 사용량 제한(Quota Exceeded)이나 모델 버전 문제 발생 시, 사용자가 즉시 다른 모델(Flash, Pro, Exp 등)로 교체하여 중단 없이 사용할 수 있습니다.

4. 🌡️ 정밀 환경 시뮬레이션
이벤트 기반 온도 보정: 트렁크 유기, 실내 에어컨 가동, 매장 등 특정 시간 동안의 온도 변화를 그래프에 반영합니다.

마곳 매스(Maggot Mass) 효과: 구더기 군집 자체가 뿜어내는 발열 현상을 온도 적산에 포함합니다.

기상 데이터 연동: meteostat 라이브러리를 통해 실제 발견 장소(좌표 기반)의 과거 날씨 데이터를 실시간으로 불러옵니다.

🛠️ 기술 스택 (Tech Stack)
Language: Python 3.9+

Framework: Streamlit (UI/UX)

AI Core: Google Gemini API (1.5 Flash / Pro / 2.0 Exp)

Data Analysis: Pandas, NumPy

Visualization: Plotly (Interactive Graph)

Weather Data: Meteostat API

🚀 설치 및 실행 방법 (Installation)

1. 필수 라이브러리 설치
pip install streamlit pandas plotly meteostat google-generativeai xlsxwriter openpyxl
2. API 키 설정
프로젝트 폴더 내에 .streamlit/secrets.toml 파일을 생성하고 구글 API 키를 입력합니다.
# .streamlit/secrets.toml
GOOGLE_API_KEY = "여기에_당신의_API_키를_넣으세요"
3. 애플리케이션 실행
streamlit run app.py


📊 시뮬레이션 로직 (Logic)본 프로그램은 ADH (Accumulated Degree Hours, 유효 적산 온도) 모델을 기반으로 작동합니다.$$ADH = \sum (T_{ambient} - T_{base}) \times \text{Hours} \times \text{DrugFactor}$$$T_{ambient}$: 환경 온도 (기상청 데이터 + 마곳 발열 + 이벤트 보정)$T_{base}$: 해당 파리 종의 발육 최저 온도 (LDT)DrugFactor: 약물에 따른 성장 가속/지연 계수 (Entomotoxicology)⚠️ 면책 조항 (Disclaimer)이 프로그램은 포트폴리오 및 학술 연구 목적으로 개발된 시뮬레이터입니다. 실제 범죄 수사나 법적 판단의 근거로 사용될 수 없으며, 제공되는 데이터(성장 속도, 약물 계수 등)는 공개된 논문을 기반으로 단순화된 수치입니다.