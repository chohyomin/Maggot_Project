# 🕵️‍♂️ Forensic AI Profiler V22.0 (Expert Edition)

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Gemini API](https://img.shields.io/badge/AI-Google%20Gemini%20Pro%2FFlash-4285F4?style=flat&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

<h3>법곤충학(Forensic Entomology) × 생성형 AI × 독성학(Toxicology)</h3>
<p>사건 현장의 단편적인 텍스트 정보와 기상 데이터를 결합하여<br>사망 경과 시간(PMI)을 정밀 추적하는 <b>지능형 법의학 시뮬레이터</b>입니다.</p>

</div>

---

## 📸 실행 화면 (Preview)

| **AI 프로파일링 & 독성학 감지** | **PMI 역추적 결과 그래프** |
| :---: | :---: |
| <img src="https://via.placeholder.com/400x300.png?text=Scenario+Input+&+AI+Analysis" alt="AI Analysis" width="100%"> | <img src="https://via.placeholder.com/400x300.png?text=Temperature+Graph+&+Event" alt="Graph Result" width="100%"> |
| *자연어 시나리오 분석 및 약물 자동 탐지* | *이벤트 구간 및 기온 변화 시각화 (Plotly)* |

---

## ✨ 핵심 기능 (Key Features)

### 1. 🧠 AI 사건 프로파일링 (AI Criminal Profiling)
사용자가 자연어로 상황을 묘사하면, AI 수사관이 다음을 분석합니다.
* **사건 유형 분석:** 타살(Homicide), 자살(Suicide), 사고사(Accident) 확률 추론
* **증거 추출:** 곤충 종류, 성장 단계, 발견 장소의 환경적 특성 자동 파싱
* **추론 근거:** 법의학적 데이터에 기반한 AI의 논리적 판단 제공

### 2. 🧬 법곤충독성학 시뮬레이션 (Entomotoxicology) <span style="color:red; font-size:0.8em;">[NEW]</span>
시신에 잔류한 약물이 구더기의 대사 활동에 미치는 영향을 수식화하여 적용했습니다.

| 약물 종류 (Drug Type) | 영향 (Effect) | 성장 속도 보정 (Rate) | 비고 |
| :--- | :--- | :---: | :--- |
| **Cocaine** (코카인) | 🔥 **가속 (Acceleration)** | **x 1.5** | 발열량 증가로 인한 성장 가속 |
| **Heroin** (헤로인) | ❄️ **지연 (Retardation)** | **x 0.8** | 대사 활동 저하 |
| **Methamphetamine** (필로폰) | ⚡ **가속 (Acceleration)** | **x 1.3** | 중추신경 자극 효과 반영 |
| **Amitriptyline** (항우울제) | 🐢 **지연 (Retardation)** | **x 0.9** | 성장 저해 요인 |

### 3. 🌡️ 정밀 환경 시뮬레이션 (Hyper-local Climate)
* **Meteostat API:** 발견 장소(GPS)의 과거 기상 데이터를 실시간으로 로드
* **Event Handling:** 트렁크 유기, 실내 난방, 매장 등 특정 시간대의 온도 변화 반영
* **Maggot Mass Effect:** 수천 마리의 구더기가 뭉쳐있을 때 발생하는 **군집 발열(최대 +20℃)** 알고리즘 적용

### 4. ⚙️ 유연한 AI 모델 스위칭 (Model Switcher)
* API 할당량(Quota) 문제 발생 시, 중단 없이 **Flash ↔ Pro ↔ Exp** 모델을 즉시 교체 가능

---

## 🔬 과학적 알고리즘 (Scientific Logic)

본 시뮬레이터는 **ADH (Accumulated Degree Hours, 유효 적산 온도)** 모델을 기반으로 작동합니다.

$$ADH = \sum_{t=0}^{n} (T_{\text{ambient}} - T_{\text{base}}) \times \Delta t \times \alpha_{\text{drug}}$$

* **$T_{\text{ambient}}$**: 환경 온도 (기상청 데이터 + 마곳 발열 + 이벤트 보정)
* **$T_{\text{base}}$**: 해당 곤충의 발육 최저 임계 온도 (LDT)
* **$\alpha_{\text{drug}}$**: 약물에 따른 성장 가속/지연 계수 (Entomotoxicology Factor)

---

## 🛠️ 기술 스택 (Tech Stack)

* **Language:** Python 3.9+
* **Framework:** Streamlit
* **AI Engine:** Google Gemini API (1.5 Flash / Pro / 2.0 Experimental)
* **Data Analysis:** Pandas, NumPy
* **Visualization:** Plotly, Meteostat
* **Export:** XlsxWriter (Excel 리포트 생성)

---

## 🚀 설치 및 실행 (How to Run)

### 1. 환경 설정
```bash
# 저장소 복제
git clone [https://github.com/username/forensic-ai-profiler.git](https://github.com/username/forensic-ai-profiler.git)

# 필수 라이브러리 설치
pip install streamlit pandas plotly meteostat google-generativeai xlsxwriter openpyxl