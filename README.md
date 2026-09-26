# Coalition-Government-Formation-Simulator<br>연립정부 구성 시뮬레이터
선거제도와 의회/정부 구성을 동시에 품은 시뮬레이터 - Powered by Google Gemini

본 시뮬레이터는 구글 제미나이의 도움과 개발자의 아이디어를 기반으로 형성된, 선거제도를 통한 정당체제 형성과 정부 구성을 동시에 시뮬레이터할 수 있는 도구입니다. 비교정치학적 연구에 사용할 수 있으며, 월드빌딩 취미 중에 의회가 필요할 때마다도 사용하실 수 있습니다.

https://dgtaehyeon.github.io/Coalition-Government-Formation-Simulator/에서 이용 가능합니다.


## 기능구성
 1. 선거제도 선택
  - 단순 비례대표제: 유럽 대부분의 국가에서 적용한 비례대표제 원칙을 그대로 보여줍니다.
  - 병립형 비례대표제: 흔히 혼합형 비례대표제라 불리는 것으로, 2016년 총선 때까지의 우리나라나 대만에서 적용하는 제도입니다.
  - 연동형 비례대표제: 독일 등의 소수 국가에서 적용하는 연동형 비례대표제를 적용한 결과를 그대로 보여줍니다.
  - 단기이양식 선호투표제(STV): 온 지구를 둘러봐도 에이레(=아일랜드)만 할 정도로 난이도가 상당히 높은 선거제도라는 점에서 개발자를 도와 코드를 짜는 제미나이조차 완전한 구현을 포기하는 바람에, 여기서는 간이모델을 통해 어떻게 동작하는지 정도만 구현하고 있습니다.
  - 결선투표제: 프랑스를 중심으로 몇 국가가 국회의원 선거에 사용하는 제도로, 결선투표를 통해 50%+1표 이상 되어야 당선이 가능한 제도라서 절대다수대표제라고 불리기도 합니다. 이 부분도 제미나이가 완전한 구현을 포기하고 간이모델로 동작하도록 했습니다.
  - 소선거구제: 미국을 포함한 다수의 국가가 국회의원 선거의 원칙으로 삼고 있으며, 이를 채택한 대표적 국가는 미국입니다. 준연동형 비례제를 채택한 현재의 우리나라에서도 소선거구제를 국회의원 선거의 기반으로 삼고 있습니다. 제미나이도 이를 한꺼번에 구현하기에는 힘든 점 때문에 큐브의 법칙에 기반을 둔 간이모델을 채택해 구현하고 있습니다.

 2. 선거 데이터 입력
   - 정당 란: 비교정치학적 연구를 위해서든, 월드빌딩 상의 가공의 국가가 개원한 의회의 구성을 위해서든 정당은 필수입니다. **아직까지 이 시뮬레이터에는 무소속이 지원이 안 되므로, 더더욱 중요합니다.** 존재 갯수에 따라 추가하거나 삭제할 수 있게 했으며, 현존하는 정당이든 가상의 정당이든 이 정당 란에서 각 정당의 이름을 쓰십시오.
   - 득표율 및 지역구 의석 란: 정당이 획득한 득표율이나 지역구 의석을 입력합니다. 다만 지역구 의석 입력은 병립형 및 연동형으로 선거제도를 선택했을 때만 입력하십시오. **이에 따라, 그 외 선거제도를 선택한 후 지역구 의석을 입력해서 나는 트러블은 컴플레인 안 받습니다.**


## 버전업 데이터
* 버전 1.0.0 (ROK 108(2026). 09. 21)
  - 단순 비례대표제, 병립형 비례대표제 (혼합형), 연동형 비례대표제 (MMP), 단기이양식 선호투표제 (STV 간이모델) 4개 모델 적용
  - 선거 결과를 입력해 나오는 의회 데이터 표출 및 연립정부 구성에 대한 최적의 데이터 표출 가능
  
* 버전 2.0.0 (ROK 108(2026). 09. 23)
  - 프랑스식 결선투표제(2차 투표), 소선거구제(단순다수제, 큐브의 법칙(Cube Rule) 기반) 추가
  - 결선투표 승리 정당에게 과반 프리미엄 의석(예: 총 의석의 50%를 1위에게 몰아주고 나머지를 비례 배분)을 부여하는 방식을 끄고 킬 수 있게 하면서도 사용자가 10%부터 50%까지 슬라이더로 프리미엄 의석 비율을 조절할 수 있도록 추가
  - 갤러거 지수(Gallagher Index), 라크소-타게페라(Laakso-Taagepera) 지수, 반자프 권력 지수(Banzhaf Power Index), 샤플리-슈빅 지수(Shapley-Shubik Power Index), 갬슨의 법칙(Gamson's Law), ‘의석 가중 평균 이념 좌표(Weighted Average Ideological Position)’ 등 연립정부와 선거 변동성 관련 지표들 표시 추가
  - '🤝 연립정부 시나리오'에서 권력 지수가 가장 높은 당을 '연정 주도당(Formateur)'으로 별도 표기 가능하도록 조정
  - 화면에 출력된 제도별 비교 데이터를 CSV나 엑셀 파일로 바로 다운로드할 수 있는 버튼 추가
  - 대조되는 선거 제도를 한 화면에 표 형식으로 나란히 놓고 비교가 가능하도록 조정 - 단순 비례대표제 vs 단순다수제(소선거구제)로 추가
  - 비교 모드의 표(compare_df) 안에 단순 비례대표제와 단순다수제의 갤러거 인덱스 및 유효 정당 수(ENP) 지표 결과도 요약해서 함께 출력할 수 있도록 조정
  - 연동형 비례대표제(MMP) 선택 시 나타나는 초과의석 허용 여부 체크박스 추가
  - 병립형이나 연동형 비례대표제에서 최대 비례대표 의석수를 최대 지역구 의석수랑 똑같이 제한을 두지 않거나 제한을 동일하게 두도록 조정
 
* 버전 2.1.0 (ROK 108(2026). 09. 25)
  - 병립형이나 연동형 비례대표제 선택 시 병립형/연동형 비례대표제에서 쓸 수 있는 비례대표제의 의석 배분 방식을 추가: 최고평균법(동트, 생-라귀), 최대잔여법
  - 파웰-터커(Powell-Tucker) 지수[정당의 출현(창당), 몰락(소멸), 대등합당 혹은 신설합당 및 분열로 인한 선거 결과 변동을 변동성 A, 기성 정당이나 당명 변경 정당, 혹은 흡수합당을 통해 당체를 소멸시키지 않고 세력을 키운 정당 간의 선거 결과 변동을 변동성 B라고 정의하여 각 변동성에 라크소-타게페라 지수의 계산법을 사용 (둘을 합치면 페데르센 변동성 지수(Pedersen’s Volatility Index)가 됨)] 추가
  - “유효 정당 수(ENP, Effective Number of Parties)”를 정병기(2024)의 정당체제 구분으로 대체
  - 참고문헌 추가
  - ‘선거제도 비교 모드 켜기’ 체크박스 추가 및 기존 PR vs 단순다수제 비교 삭제
  - 단순다수제(큐브의 법칙)와 결선투표제(간이모델)에서 비례대표 배분 로직(pr_method)이 개입하지 않도록 함수 분리
  - 초과의석은 연동형 비례대표제에서만 작동하도록 수정 + 초과의석을 억제할 때 비례대표 파이를 다시 분배하는 연산(득표율 기반 재배분) 로직의 수학적 결함 수정
 
* 버전 2.1.1 (ROK 108(2026). 09. 26)
  - 시뮬레이터 이름을 "의회 및 연정 구성 시뮬레이터"로 고정

 ## 참고문헌 -
  - Banzhaf III, J. F. (1965). "Weighted voting doesn't work: A mathematical analysis." Rutgers Law Review, 19, 317-343.
  - Budge, I., Robertson, D., & Hearl, D. (1987). Ideology, Strategy and Party Change: Spatial Analyses of Post-War Election Programmes in 19 Democracies. Cambridge University Press.
  - Budge, I., et al. (2001). Mapping Policy Preferences: Estimates for Parties, Electors, and Governments 1945–1998. Oxford University Press.
  - Gamson, W. A. (1961). "A theory of coalition formation." American Sociological Review, 26(3), 373-382.
  - Gallagher, M. (1991). "Proportionality, disproportionality and electoral systems." Electoral Studies, 10(1), 33-51.
  - Kendall, M. G., & Stuart, A. (1950). "The Law of the Cubic Proportion in Election Results." The British Journal of Sociology, 1(3), 183-196.
  - Laakso, M., & Taagepera, R. (1979). "Effective" Number of Parties: A Measure with Application to West Europe. Comparative Political Studies, 12(1), 3-27.
  - Powell, E. N., & Tucker, J. A. (2009a) “Applying new approaches to electoral volatility: East vs. West”,Working paper.
  - Powell, E. N., & Tucker, J. A. (2009b) “New approaches to electoral volatility: Evidence from postcommunist countries”. Working paper.
  - Shapley, L. S., & Shubik, M. (1954). "A method for evaluating the distribution of power in a committee system." American Political Science Review, 48(3), 787-792.
  - Smith, J. Parker (1910). "Oral evidence", Royal Commission on Systems of Election, Minutes of Evidence, CD 5352, London: HMSO.
  - Farrell, D., 전용주 옮김 및 옮김 수정 (2017) 『선거제도의 이해』. 파주:한울아카데미.
  - 정병기 (2024). “그리스의 2023년 총선과 정당 구도 변화: 추가의석 효과와 경제 이슈 투표.”, 『선거연구』, (20), 59-80.
  -  [추후 관련 참고문헌 발견 및 새 개념 추가 시마다 추가 예정]
