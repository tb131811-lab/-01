import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------------------------------------------------
# 1. 페이지 설정 및 데이터 로드
# -------------------------------------------------------------------
st.set_page_config(page_title="무역 분석 대시보드", layout="wide")

@st.cache_data
def load_data():
    # 1. 데이터 로드
    baci_df = pd.read_csv('baci_85_sample.csv')
    country_df = pd.read_csv('country_codes_sample.csv')
    
    # 원본 결측치 계산을 위해 복사본 유지
    raw_baci_df = baci_df.copy()
    
    # 2. BACI 원본 컬럼명 변경 (v -> Value, t -> Year)
    if 'v' in baci_df.columns:
        baci_df.rename(columns={'v': 'Value', 't': 'Year'}, inplace=True)
        
    # 3. 국가 코드 컬럼 자동 감지 및 병합 (KeyError 방지)
    # country_df에서 국가 코드로 쓰일 확률이 높은 컬럼명 탐색
    possible_code_cols = ['country_code', 'code', 'id', 'country_id', 'i', 'Code']
    merge_col = None
    
    for col in possible_code_cols:
        if col in country_df.columns:
            merge_col = col
            break
            
    # 예상되는 이름이 없다면 가장 첫 번째 컬럼을 국가 코드로 간주
    if merge_col is None:
        merge_col = country_df.columns[0]
        
    # 데이터 병합 실행
    df = pd.merge(baci_df, country_df, left_on='i', right_on=merge_col, how='left')
    
    # 4. 병합된 데이터에서 국가 이름 컬럼을 'Country'로 통일
    possible_name_cols = ['country_name', 'country_name_english', 'country_name_kr', 'name', 'Country Name', 'Name']
    name_col_found = False
    
    for col in possible_name_cols:
        if col in df.columns:
            df.rename(columns={col: 'Country'}, inplace=True)
            name_col_found = True
            break
            
    if not name_col_found:
        # 이름을 찾지 못하면 임시로 병합했던 코드값을 국가명으로 사용
        df.rename(columns={'i': 'Country'}, inplace=True) 
        
    # 5. 무역액 등급(대, 중, 소) 파생 변수 생성
    if 'Value' in df.columns:
        df['무역액등급'] = pd.qcut(df['Value'], q=3, labels=['소', '중', '대'], duplicates='drop')
        
    return df, raw_baci_df

# 데이터 로딩 실행
try:
    df, raw_baci_df = load_data()
except Exception as e:
    st.error(f"데이터를 로드하는 중 오류가 발생했습니다: {e}")
    st.stop()

# -------------------------------------------------------------------
# 2. 사이드바 (필터)
# -------------------------------------------------------------------
st.sidebar.header("🔍 대시보드 필터")

# 국가 선택 필터 (결측치 제외 후 고유값)
all_countries = sorted(df['Country'].dropna().astype(str).unique().tolist())
selected_countries = st.sidebar.multiselect(
    "국가 선택", 
    options=all_countries, 
    default=all_countries[:10] if len(all_countries) > 10 else all_countries
)

# 무역액 등급 선택 필터
all_grades = ['대', '중', '소']
selected_grades = st.sidebar.multiselect(
    "무역액 등급 선택", 
    options=all_grades, 
    default=all_grades
)

# 필터 적용
filtered_df = df[
    (df['Country'].astype(str).isin(selected_countries)) & 
    (df['무역액등급'].isin(selected_grades))
]

# -------------------------------------------------------------------
# 3. 메인 화면 (오른쪽 화면)
# -------------------------------------------------------------------
# 1. 타이틀
st.title("📈 무역 분석 대시보드")
st.markdown("---")

# 2. baci_85_sample.csv 파일의 결측치
st.subheader("1. 원본 데이터(`baci_85_sample.csv`) 결측치 현황")
missing_data = raw_baci_df.isnull().sum()
missing_df = pd.DataFrame({'컬럼명': missing_data.index, '결측치 수': missing_data.values})
st.dataframe(missing_df.T, use_container_width=True)

st.markdown("---")

# 3. 총 거래건수 & 총 수출액(달러)
col1, col2 = st.columns(2)
with col1:
    total_count = len(filtered_df)
    st.metric(label="총 거래건수 (건)", value=f"{total_count:,}")
with col2:
    total_value = filtered_df['Value'].sum() if 'Value' in filtered_df.columns else 0
    st.metric(label="총 수출액 (달러)", value=f"${total_value:,.2f}")

st.markdown("---")

# 4. 차트 영역: 국가*연도 수출액 히트맵 & 무역액 등급분포
col3, col4 = st.columns(2)

with col3:
    st.subheader("상위 8개국 연도별 수출액 히트맵")
    if not filtered_df.empty and 'Year' in filtered_df.columns:
        # 상위 8개국 추출
        top8_countries = filtered_df.groupby('Country')['Value'].sum().nlargest(8).index
        heatmap_data = filtered_df[filtered_df['Country'].isin(top8_countries)]
        heatmap_pivot = heatmap_data.pivot_table(index='Country', columns='Year', values='Value', aggfunc='sum').fillna(0)
        
        # Plotly 히트맵
        fig_heat = px.imshow(
            heatmap_pivot,
            labels=dict(x="연도", y="국가", color="수출액"),
            aspect="auto",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("선택된 데이터가 없거나 연도(Year) 정보가 없습니다.")

with col4:
    st.subheader("무역액 등급 분포")
    if not filtered_df.empty:
        grade_dist = filtered_df['무역액등급'].value_counts().reset_index()
        grade_dist.columns = ['무역액등급', '건수']
        
        fig_pie = px.pie(
            grade_dist, 
            names='무역액등급', 
            values='건수', 
            hole=0.4,
            color='무역액등급',
            color_discrete_map={'대':'#1f77b4', '중':'#ff7f0e', '소':'#2ca02c'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("선택된 데이터가 없습니다.")

st.markdown("---")

# 5. 상위 5개국 * 무역액 등급 교차표
st.subheader("상위 5개국 무역액 등급 교차표")
if not filtered_df.empty:
    # 상위 5개국 추출
    top5_countries = filtered_df.groupby('Country')['Value'].sum().nlargest(5).index
    cross_data = filtered_df[filtered_df['Country'].isin(top5_countries)]

    col5, col6 = st.columns(2)

    with col5:
        st.markdown("**[원본 건수]**")
        crosstab_raw = pd.crosstab(cross_data['Country'], cross_data['무역액등급'])
        # 컬럼 순서 정렬
        for col in ['대', '중', '소']:
            if col not in crosstab_raw.columns:
                crosstab_raw[col] = 0
        crosstab_raw = crosstab_raw[['대', '중', '소']]
        st.dataframe(crosstab_raw, use_container_width=True)

    with col6:
        st.markdown("**[정규화 비율 (행 기준)]**")
        crosstab_norm = pd.crosstab(cross_data['Country'], cross_data['무역액등급'], normalize='index') * 100
        for col in ['대', '중', '소']:
            if col not in crosstab_norm.columns:
                crosstab_norm[col] = 0.0
        crosstab_norm = crosstab_norm[['대', '중', '소']].round(2).astype(str) + '%'
        st.dataframe(crosstab_norm, use_container_width=True)
else:
    st.info("선택된 데이터가 없습니다.")
    