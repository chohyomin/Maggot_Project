# 🧬 Forensic PMI Analyzer V6.0 (Masterpiece)

**법곤충학 기반 사망 추정 시간(PMI) 정밀 분석 시뮬레이터** **Forensic Entomology PMI Estimation Simulator with Advanced Biological Variables**

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📖 개요 (Overview)
이 프로젝트는 시신에서 발견된 곤충(구더기)의 성장 데이터를 역추적하여 **사망 추정 시각(Estimated Time of Death)**을 산출하는 법의학 시뮬레이션 도구입니다.

단순한 적산온도(ADH) 계산을 넘어, **상한 발육 온도(UDT), 마곳 매스(Maggot Mass), 약물 반응, 일사량, 접근 지연(PIA)** 등 실제 수사 현장에서 고려되는 복합적인 변수를 통제하여 높은 정밀도의 분석 결과를 제공합니다.

## ✨ 주요 기능 (Key Features)

### 1. 과학적 성장 모델링 (Scientific Modeling)
* **적산온도(ADH) 역계산:** LDT(발육영점)와 UDT(상한온도)를 모두 고려한 정밀 알고리즘.
* **열 스트레스(Heat Stress) 구현:** 기온이 UDT를 초과할 경우 성장이 멈추는 생물학적 한계 반영.
* **신뢰 구간(Confidence Interval):** 95% 신뢰 수준의 오차 범위를 계산하여 법정 증거 능력 강화.

### 2. 다양한 환경 변수 시뮬레이션 (Environmental Variables)
* **마곳 매스 (Maggot Mass):** 구더기 덩어리 내부의 대사열(Metabolic Heat)로 인한 온도 상승 보정.
* **접근 지연 (PIA):** 이불, 가방, 매장 등 은폐 상황에 따른 산란 지연 시간 자동 계산.
* **일사량 보정 (Solar Radiation):** 직사광선(양지) 및 그늘(음지) 여부에 따른 체감 온도 보정.
* **법곤충독성학 (Entomotoxicology):** 마약류(가속)나 중금속(지연) 등 체내 약물에 따른 성장 속도 변화 적용.

### 3. 사용자 친화적 인터페이스 (UI/UX)
* **전문가용 대시보드:** 사건 정보 입력, 정밀 분석, 보고서 탭으로 분리된 워크플로우.
* **시각화:** 성장 곡선(Growth Curve) 및 성장 정지 구간 시각화 그래프 제공.
* **자동 보고서 생성:** 분석된 모든 데이터를 엑셀(XLSX) 파일로 다운로드 가능.

---

## 🚀 설치 및 실행 방법 (Installation)

### 1. 환경 설정
이 프로젝트는 Python 환경에서 동작합니다. 아래 명령어로 필수 라이브러리를 설치하세요.

```bash
pip install -r requirements.txt