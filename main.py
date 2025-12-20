import datetime
from datetime import timedelta

class BasicPMICalculator:
    """
    기본적인 법곤충학 사망 시간 추정 계산기 (ADH: 적산온도 모델 기반)
    """
    def __init__(self):
        # 1. 곤충 데이터베이스
        # 실제로는 방대한 연구 데이터를 기반으로 해야 합니다.
        # LDT: 발육 영점 온도 (이 온도 이하에서는 성장 멈춤)
        self.insect_db = {
            "lucilia_sericata": {
                "name": "구리금파리",
                "LDT": 9.0, 
                "stages": {
                    "egg": 23,        # 알 부화까지 (단위: ADH)
                    "instar_1": 400,  # 1령
                    "instar_2": 900,  # 2령
                    "instar_3": 2000, # 3령 (섭식 종료)
                    "pupa": 4500      # 번데기
                }
            },
            "chrysomya_megacephala": {
                "name": "대동파리",
                "LDT": 10.0,
                "stages": {
                    "egg": 18,
                    "instar_1": 350,
                    "instar_2": 800,
                    "instar_3": 1800,
                    "pupa": 4000
                }
            }
        }

    def calculate_pmi(self, species_key, current_stage, weather_data, correction_factor=1.0):
        """
        PMI(사후 경과 시간) 역계산 함수
        
        :param species_key: 파리 종류 키 (예: 'lucilia_sericata')
        :param current_stage: 현재 발견된 성장 단계 (예: 'instar_3')
        :param weather_data: 시간별 온도 데이터 리스트 (최신순 정렬)
        :param correction_factor: 약물/환경 등에 의한 성장 속도 보정 계수 (기본 1.0)
        """
        
        # 1. 입력값 검증 (종 및 단계 확인)
        if species_key not in self.insect_db:
            return {"status": "error", "msg": "알 수 없는 파리 종류입니다."}
        
        species_info = self.insect_db[species_key]
        ldt = species_info['LDT']
        
        if current_stage not in species_info['stages']:
            return {"status": "error", "msg": "알 수 없는 성장 단계입니다."}
            
        target_adh = species_info['stages'][current_stage]
        
        print(f"--- 분석 시작: {species_info['name']} ({current_stage}) ---")
        print(f"목표 누적 ADH: {target_adh}, 발육 영점(LDT): {ldt}°C")
        if correction_factor != 1.0:
            print(f"특이 사항: 성장 보정 계수 {correction_factor} 적용됨")

        # 2. 역계산 로직 (Back-calculation)
        accumulated_heat = 0.0
        estimated_time = None
        
        # 시간 데이터를 최신(발견 시점)에서 과거로 순회
        for record in weather_data:
            current_temp = record['temp']
            current_time = record['time']
            
            # 유효 온도 계산 (현재 온도 - 발육 영점)
            effective_temp = current_temp - ldt
            
            # 온도가 LDT보다 낮으면 곤충은 성장하지 않음 (0 처리)
            if effective_temp > 0:
                # 보정 계수 적용 (약물 등으로 성장이 빨라졌으면, 시간당 더 많은 열량을 얻은 것으로 계산)
                hourly_heat = effective_temp * correction_factor
                accumulated_heat += hourly_heat
            
            # 목표치에 도달했는지 확인
            if accumulated_heat >= target_adh:
                estimated_time = current_time
                break
        
        # 3. 결과 반환
        if estimated_time:
            # 발견 시점과 추정 사망 시점 사이의 시간 차이 계산
            hours_elapsed = (weather_data[0]['time'] - estimated_time).total_seconds() / 3600
            return {
                "status": "success",
                "species": species_info['name'],
                "estimated_death_time": estimated_time,
                "total_adh_accumulated": accumulated_heat,
                "hours_ago": hours_elapsed
            }
        else:
            return {
                "status": "fail", 
                "msg": "데이터 기간 내에서 사망 시점을 특정할 수 없습니다. (데이터 부족)"
            }

# ==========================================
# 실행 및 테스트 섹션
# ==========================================

def generate_weather_history(hours_back=500, base_temp=24.0):
    """
    테스트를 위해 가상의 과거 날씨 데이터를 생성하는 함수입니다.
    현재 시간부터 과거로 가며 데이터를 만듭니다.
    """
    history = []
    now = datetime.datetime.now()
    
    for i in range(hours_back):
        timestamp = now - timedelta(hours=i)
        
        # 간단한 하루 온도 변화 시뮬레이션 (낮에는 덥고 밤에는 춥게)
        hour_val = timestamp.hour
        # 오후 2시(14시) 기준 온도 변동폭 설정
        temp_fluctuation = 5 * ((12 - abs(hour_val - 14)) / 12) 
        
        final_temp = base_temp + temp_fluctuation
        
        history.append({
            'time': timestamp,
            'temp': round(final_temp, 1)
        })
    return history

if __name__ == "__main__":
    # 1. 계산기 인스턴스 생성
    calculator = BasicPMICalculator()
    
    # 2. 상황 설정 (시나리오)
    # 구리금파리 3령 유충이 발견됨
    target_species = "lucilia_sericata"
    target_stage = "instar_3"
    
    # 시신에서 약물(코카인) 반응이 있어 성장이 1.2배 빨랐을 것으로 가정
    drug_correction = 1.2 
    
    # 3. 가상 데이터 생성 (500시간 전까지, 평균 22도)
    print("가상의 기상 데이터를 생성 중입니다...")
    weather_history = generate_weather_history(hours_back=500, base_temp=22)
    
    # 4. 계산 수행
    result = calculator.calculate_pmi(
        target_species, 
        target_stage, 
        weather_history, 
        correction_factor=drug_correction
    )
    
    # 5. 결과 출력
    print("\n" + "=" * 50)
    if result['status'] == 'success':
        death_time_str = result['estimated_death_time'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"▶ 분석 결과: {result['species']} 산란 시점 추적 완료")
        print(f"▶ 추정 사망 시각: {death_time_str}")
        print(f"▶ 발견 시점으로부터: 약 {result['hours_ago']:.1f}시간 전")
        print(f"▶ 역추적된 총 ADH: {result['total_adh_accumulated']:.2f}")
    else:
        print(f"▶ 분석 실패: {result['msg']}")
    print("=" * 50)