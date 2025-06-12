import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import base64

def download_google_sheet(sheet_url):
    """Загрузка данных из Google Sheets"""
    try:
        # Конвертируем ссылку в формат CSV экспорта
        if '/edit' in sheet_url:
            csv_url = sheet_url.replace('/edit?gid=', '/export?format=csv&gid=')
            csv_url = csv_url.split('#')[0]  # Убираем якорь
        else:
            csv_url = sheet_url
        
        response = requests.get(csv_url)
        if response.status_code == 200:
            return pd.read_csv(BytesIO(response.content))
        else:
            st.error(f"Ошибка загрузки: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Ошибка при загрузке Google Sheets: {str(e)}")
        return None

def process_stock_data(df):
    """Обработка данных остатков магазинов"""
    if df is None or df.empty:
        return None
    
    # Найдем колонки с магазинами (начинаются с "Маг.")
    store_columns = [col for col in df.columns if col.startswith('Маг.')]
    
    # Создаем сводную таблицу по наличию товаров
    result = []
    for _, row in df.iterrows():
        describe = row.get('Describe', '')
        if pd.isna(describe) or describe == '':
            continue
            
        # Считаем в скольких магазинах есть товар
        in_stock_count = 0
        stores_with_stock = []
        
        for store_col in store_columns:
            stock_value = row.get(store_col, '')
            if not pd.isna(stock_value) and str(stock_value).strip() != '' and str(stock_value) != '0':
                in_stock_count += 1
                stores_with_stock.append(store_col)
        
        result.append({
            'Артикул': row.get('Артикул', ''),
            'Describe': describe,
            'Магазинов с товаром': in_stock_count,
            'Всего магазинов': len(store_columns),
            'Список магазинов': ', '.join(stores_with_stock)
        })
    
    return pd.DataFrame(result)

def compare_assortment(should_be_df, actual_df):
    """Сравнение ассортимента"""
    if should_be_df is None or actual_df is None:
        return None, None, None
    
    # Проверяем наличие колонки Describe в обеих таблицах
    should_be_describe_col = None
    actual_describe_col = None
    
    # Ищем колонку Describe (с учетом возможных вариантов названия)
    for col in should_be_df.columns:
        if 'describe' in col.lower() or 'описание' in col.lower():
            should_be_describe_col = col
            break
    
    for col in actual_df.columns:
        if 'describe' in col.lower() or 'описание' in col.lower():
            actual_describe_col = col
            break
    
    if should_be_describe_col is None or actual_describe_col is None:
        st.error(f"Колонка 'Describe' не найдена! Доступные колонки в обязательном ассортименте: {list(should_be_df.columns)}")
        st.error(f"Доступные колонки в остатках: {list(actual_df.columns)}")
        return None, None, None
    
    # Получаем списки товаров по Describe
    should_be_items = set(should_be_df[should_be_describe_col].dropna().astype(str).str.strip())
    actual_items = set(actual_df[actual_describe_col].dropna().astype(str).str.strip())
    
    # Анализ
    missing_items = should_be_items - actual_items  # Должны быть, но нет
    extra_items = actual_items - should_be_items    # Есть, но не должны быть
    matching_items = should_be_items & actual_items # Совпадают
    
    # Создаем детальные отчеты с проверкой существования колонок
    available_cols_should_be = [col for col in ['ART', 'Describe', 'Название_бренда', 'Price:'] if col in should_be_df.columns]
    available_cols_actual = [col for col in ['Артикул', 'Describe', 'Магазинов с товаром'] if col in actual_df.columns]
    
    missing_df = should_be_df[should_be_df[should_be_describe_col].isin(missing_items)][available_cols_should_be]
    
    extra_df = actual_df[actual_df[actual_describe_col].isin(extra_items)][available_cols_actual]
    
    matching_df = should_be_df[should_be_df[should_be_describe_col].isin(matching_items)][available_cols_should_be]
    
    # Объединяем с данными об остатках если возможно
    if 'Магазинов с товаром' in actual_df.columns:
        matching_with_stock = matching_df.merge(
            actual_df[[actual_describe_col, 'Магазинов с товаром']], 
            left_on=should_be_describe_col,
            right_on=actual_describe_col, 
            how='left'
        )
    else:
        matching_with_stock = matching_df
    
    return missing_df, extra_df, matching_with_stock

def create_download_link(df, filename):
    """Создание ссылки для скачивания Excel файла"""
    if df is None or df.empty:
        return ""
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Скачать {filename}</a>'
    return href

# Streamlit интерфейс
st.set_page_config(page_title="Система сравнения товаров", layout="wide")

st.title("🏪 Система сравнения товаров магазинов")
st.markdown("---")

# Боковая панель для загрузки данных
st.sidebar.header("📂 Загрузка данных")

# Google Sheets URL
google_sheet_url = st.sidebar.text_input(
    "Google Sheets URL (обязательный ассортимент):",
    value="https://docs.google.com/spreadsheets/d/1D8hz6ZLo_orDMokYms2lQkO_A3nnYNEFYe-mO1CDcrY/export?format=csv&gid=1286042599"
)

# Загрузка файла остатков
uploaded_file = st.sidebar.file_uploader(
    "Загрузите Excel файл с остатками магазинов",
    type=['xlsx', 'xls']
)

# Кнопка для загрузки данных
if st.sidebar.button("🔄 Загрузить и сравнить данные"):
    with st.spinner("Загрузка данных..."):
        # Загрузка обязательного ассортимента
        should_be_df = download_google_sheet(google_sheet_url)
        
        if should_be_df is not None:
            st.info(f"📋 Загружено из Google Sheets: {len(should_be_df)} строк")
            st.info(f"Колонки: {list(should_be_df.columns)}")
        
        # Загрузка остатков
        actual_df = None
        if uploaded_file is not None:
            try:
                raw_df = pd.read_excel(uploaded_file)
                st.info(f"📊 Загружено из Excel: {len(raw_df)} строк")
                st.info(f"Колонки: {list(raw_df.columns)}")
                actual_df = process_stock_data(raw_df)
            except Exception as e:
                st.error(f"Ошибка при чтении Excel файла: {str(e)}")
        
        if should_be_df is not None and actual_df is not None:
            st.success("✅ Данные успешно загружены!")
            
            # Сохраняем данные в session_state
            st.session_state['should_be_df'] = should_be_df
            st.session_state['actual_df'] = actual_df
            
            # Выполняем сравнение
            missing_df, extra_df, matching_df = compare_assortment(should_be_df, actual_df)
            
            st.session_state['missing_df'] = missing_df
            st.session_state['extra_df'] = extra_df
            st.session_state['matching_df'] = matching_df
        else:
            st.error("❌ Не удалось загрузить данные")

# Отображение результатов
if 'should_be_df' in st.session_state and 'actual_df' in st.session_state:
    should_be_df = st.session_state['should_be_df']
    actual_df = st.session_state['actual_df']
    missing_df = st.session_state.get('missing_df')
    extra_df = st.session_state.get('extra_df')
    matching_df = st.session_state.get('matching_df')
    
    # Основная статистика
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Должно быть товаров", len(should_be_df))
    
    with col2:
        st.metric("🏪 Фактически товаров", len(actual_df))
    
    with col3:
        st.metric("❌ Отсутствует товаров", len(missing_df) if missing_df is not None else 0)
    
    with col4:
        st.metric("➕ Лишних товаров", len(extra_df) if extra_df is not None else 0)
    
    st.markdown("---")
    
    # Вкладки с результатами
    tab1, tab2, tab3, tab4 = st.tabs(["❌ Отсутствующие товары", "➕ Лишние товары", "✅ Совпадающие товары", "📊 Сводка"])
    
    with tab1:
        st.subheader("Товары, которых нет в наличии, но должны быть")
        if missing_df is not None and not missing_df.empty:
            st.dataframe(missing_df, use_container_width=True)
            st.markdown(create_download_link(missing_df, "отсутствующие_товары.xlsx"), unsafe_allow_html=True)
        else:
            st.success("🎉 Все необходимые товары есть в наличии!")
    
    with tab2:
        st.subheader("Лишние товары (есть в наличии, но не в обязательном ассортименте)")
        if extra_df is not None and not extra_df.empty:
            st.dataframe(extra_df, use_container_width=True)
            st.markdown(create_download_link(extra_df, "лишние_товары.xlsx"), unsafe_allow_html=True)
        else:
            st.info("ℹ️ Лишних товаров не найдено")
    
    with tab3:
        st.subheader("Товары, которые совпадают")
        if matching_df is not None and not matching_df.empty:
            st.dataframe(matching_df, use_container_width=True)
            st.markdown(create_download_link(matching_df, "совпадающие_товары.xlsx"), unsafe_allow_html=True)
        else:
            st.warning("⚠️ Совпадающих товаров не найдено")
    
    with tab4:
        st.subheader("📊 Сводная информация")
        
        if missing_df is not None and matching_df is not None:
            total_should_be = len(should_be_df)
            total_missing = len(missing_df)
            total_matching = len(matching_df)
            
            coverage_percent = (total_matching / total_should_be * 100) if total_should_be > 0 else 0
            
            st.metric("📈 Покрытие ассортимента", f"{coverage_percent:.1f}%")
            
            # График покрытия
            import plotly.express as px
            
            coverage_data = pd.DataFrame({
                'Статус': ['Есть в наличии', 'Отсутствует'],
                'Количество': [total_matching, total_missing],
                'Процент': [coverage_percent, 100 - coverage_percent]
            })
            
            fig = px.pie(coverage_data, values='Количество', names='Статус', 
                        title="Покрытие обязательного ассортимента")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👆 Загрузите данные через боковую панель для начала анализа")
    
    # Инструкция
    with st.expander("📖 Инструкция по использованию"):
        st.markdown("""
        ### Как использовать систему:
        
        1. **Google Sheets URL**: Укажите ссылку на таблицу с обязательным ассортиментом
           - Таблица должна содержать колонку 'Describe'
           
        2. **Excel файл**: Загрузите файл с остатками товаров в магазинах
           - Файл должен содержать колонки: 'Артикул', 'Describe' и колонки магазинов
           
        3. **Нажмите "Загрузить и сравнить данные"**
        
        4. **Анализируйте результаты** в соответствующих вкладках
        
        ### Результаты анализа:
        - **Отсутствующие товары**: Товары из обязательного ассортимента, которых нет в магазинах
        - **Лишние товары**: Товары в магазинах, которых нет в обязательном ассортименте  
        - **Совпадающие товары**: Товары, которые есть и в ассортименте, и в магазинах
        - **Сводка**: Общая статистика и визуализация покрытия
        """)
