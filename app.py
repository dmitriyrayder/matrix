import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
import base64
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ========================
# НАСТРОЙКИ СТРАНИЦЫ
# ========================
st.set_page_config(
    page_title="DDMRP Система управления остатками",
    page_icon="📊",
    layout="wide"
)

# ========================
# ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ
# ========================

def download_google_sheet(sheet_url):
    """Загрузка торговой матрицы из Google Sheets"""
    try:
        if '/edit' in sheet_url:
            csv_url = sheet_url.replace('/edit?gid=', '/export?format=csv&gid=')
            csv_url = csv_url.split('#')[0]
        else:
            csv_url = sheet_url
        
        response = requests.get(csv_url)
        if response.status_code == 200:
            df = pd.read_csv(BytesIO(response.content))
            return df
        else:
            st.error(f"❌ Ошибка загрузки: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"❌ Ошибка при загрузке Google Sheets: {str(e)}")
        return None


def load_stock_file(uploaded_file):
    """Загрузка файла остатков Excel"""
    try:
        df = pd.read_excel(uploaded_file)
        
        # Маппинг колонок
        column_mapping = {
            'Art': 'Article',
            'Magazin': 'Store_ID',
            'Describe': 'Describe',
            'к-во': 'Current_Stock',
            'Model': 'Model'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Проверка обязательных колонок
        required_cols = ['Article', 'Store_ID', 'Describe', 'Current_Stock']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"❌ Отсутствуют обязательные колонки: {missing_cols}")
            return None
        
        # Очистка данных
        df['Current_Stock'] = pd.to_numeric(df['Current_Stock'], errors='coerce').fillna(0)
        df['Store_ID'] = df['Store_ID'].astype(str).str.strip()
        df['Article'] = df['Article'].astype(str).str.strip()
        
        return df
    
    except Exception as e:
        st.error(f"❌ Ошибка при загрузке Excel: {str(e)}")
        return None


def validate_matrix(df):
    """Валидация торговой матрицы"""
    required_cols = ['Article', 'Describe', 'Store_ID', 'Red_Zone', 'Yellow_Zone', 'Green_Zone']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ В торговой матрице отсутствуют колонки: {missing_cols}")
        return False
    
    # Проверка типов данных
    df['Red_Zone'] = pd.to_numeric(df['Red_Zone'], errors='coerce')
    df['Yellow_Zone'] = pd.to_numeric(df['Yellow_Zone'], errors='coerce')
    df['Green_Zone'] = pd.to_numeric(df['Green_Zone'], errors='coerce')
    df['Store_ID'] = df['Store_ID'].astype(str).str.strip()
    df['Article'] = df['Article'].astype(str).str.strip()
    
    # Проверка на пустые значения
    if df[required_cols].isnull().any().any():
        st.warning("⚠️ В торговой матрице есть пустые значения в обязательных полях")
    
    return True


# ========================
# DDMRP ЛОГИКА
# ========================

def calculate_ddmrp_status(matrix_df, stock_df):
    """
    Расчет статуса буферов DDMRP для каждого товара в каждом магазине
    """
    # Объединяем матрицу и остатки
    merged = matrix_df.merge(
        stock_df[['Article', 'Store_ID', 'Current_Stock', 'Model']],
        on=['Article', 'Store_ID'],
        how='left'
    )
    
    # Заполняем отсутствующие остатки нулями
    merged['Current_Stock'] = merged['Current_Stock'].fillna(0)
    
    # Расчет Top of Green (максимальный уровень запаса)
    merged['Top_of_Green'] = merged['Red_Zone'] + merged['Yellow_Zone'] + merged['Green_Zone']
    
    # Расчет границ зон
    merged['Red_Zone_Max'] = merged['Red_Zone']
    merged['Yellow_Zone_Max'] = merged['Red_Zone'] + merged['Yellow_Zone']
    merged['Green_Zone_Max'] = merged['Top_of_Green']
    
    # Определение статуса буфера
    def get_buffer_status(row):
        stock = row['Current_Stock']
        if stock <= row['Red_Zone_Max']:
            return 'RED'
        elif stock <= row['Yellow_Zone_Max']:
            return 'YELLOW'
        elif stock <= row['Green_Zone_Max']:
            return 'GREEN'
        else:
            return 'EXCESS'  # Излишек
    
    merged['Buffer_Status'] = merged.apply(get_buffer_status, axis=1)
    
    # Расчет процента заполнения буфера
    merged['Buffer_Fill_Percent'] = (merged['Current_Stock'] / merged['Top_of_Green'] * 100).round(1)
    
    # Расчет количества для заказа
    def calculate_order_qty(row):
        if row['Buffer_Status'] in ['RED', 'YELLOW']:
            # Заказываем до Top of Green
            order_qty = row['Top_of_Green'] - row['Current_Stock']
            return max(0, order_qty)
        return 0
    
    merged['Order_Qty'] = merged.apply(calculate_order_qty, axis=1)
    
    # Приоритет заказа (RED = 1, YELLOW = 2, GREEN = 3, EXCESS = 4)
    priority_map = {'RED': 1, 'YELLOW': 2, 'GREEN': 3, 'EXCESS': 4}
    merged['Priority'] = merged['Buffer_Status'].map(priority_map)
    
    # Расчет дней до исчерпания запаса (если есть Avg_Daily_Usage)
    if 'Avg_Daily_Usage' in merged.columns:
        merged['Avg_Daily_Usage'] = pd.to_numeric(merged['Avg_Daily_Usage'], errors='coerce').fillna(0)
        merged['Days_Until_Stockout'] = np.where(
            merged['Avg_Daily_Usage'] > 0,
            (merged['Current_Stock'] / merged['Avg_Daily_Usage']).round(1),
            np.inf
        )
    else:
        merged['Days_Until_Stockout'] = np.nan
    
    return merged


def generate_order_report(ddmrp_df):
    """Генерация отчета по заказам"""
    # Фильтруем только товары, требующие заказа
    orders = ddmrp_df[ddmrp_df['Order_Qty'] > 0].copy()
    
    if orders.empty:
        return pd.DataFrame()
    
    # Сортировка по приоритету и магазину
    orders = orders.sort_values(['Priority', 'Store_ID', 'Article'])
    
    # Выбираем нужные колонки для отчета
    report_columns = [
        'Store_ID', 'Article', 'Describe', 'Brand', 'Model',
        'Current_Stock', 'Top_of_Green', 'Order_Qty', 
        'Buffer_Status', 'Priority', 'Days_Until_Stockout'
    ]
    
    # Проверяем наличие колонок
    available_columns = [col for col in report_columns if col in orders.columns]
    
    return orders[available_columns].reset_index(drop=True)


# ========================
# ВИЗУАЛИЗАЦИЯ
# ========================

def create_buffer_status_chart(ddmrp_df):
    """График распределения статусов буферов"""
    status_counts = ddmrp_df['Buffer_Status'].value_counts()
    
    colors = {
        'RED': '#FF4444',
        'YELLOW': '#FFD700',
        'GREEN': '#44FF44',
        'EXCESS': '#4444FF'
    }
    
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title='Распределение статусов буферов',
        color=status_counts.index,
        color_discrete_map=colors
    )
    
    return fig


def create_store_summary_chart(ddmrp_df):
    """График сводки по магазинам"""
    store_summary = ddmrp_df.groupby(['Store_ID', 'Buffer_Status']).size().reset_index(name='Count')
    
    fig = px.bar(
        store_summary,
        x='Store_ID',
        y='Count',
        color='Buffer_Status',
        title='Статусы буферов по магазинам',
        color_discrete_map={
            'RED': '#FF4444',
            'YELLOW': '#FFD700',
            'GREEN': '#44FF44',
            'EXCESS': '#4444FF'
        },
        barmode='stack'
    )
    
    fig.update_layout(xaxis_title='Магазин', yaxis_title='Количество товаров')
    
    return fig


def create_top_orders_chart(orders_df, top_n=20):
    """График топ товаров для заказа"""
    if orders_df.empty:
        return None
    
    top_orders = orders_df.nlargest(top_n, 'Order_Qty')
    
    fig = px.bar(
        top_orders,
        x='Order_Qty',
        y='Describe',
        color='Buffer_Status',
        title=f'Топ-{top_n} товаров для заказа',
        orientation='h',
        color_discrete_map={
            'RED': '#FF4444',
            'YELLOW': '#FFD700'
        }
    )
    
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    
    return fig


# ========================
# ЭКСПОРТ ДАННЫХ
# ========================

def create_excel_download(df, filename):
    """Создание ссылки для скачивания Excel"""
    if df is None or df.empty:
        return ""
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Скачать {filename}</a>'
    return href


# ========================
# STREAMLIT ИНТЕРФЕЙС
# ========================

def main():
    st.title("📊 DDMRP: Система управления остатками")
    st.markdown("**Динамическое управление буферами запасов по методологии DDMRP**")
    st.markdown("---")
    
    # ========================
    # БОКОВАЯ ПАНЕЛЬ
    # ========================
    st.sidebar.header("📂 Загрузка данных")
    
    # Google Sheets URL
    google_sheet_url = st.sidebar.text_input(
        "Google Sheets URL (торговая матрица):",
        value="",
        help="Ссылка на Google Sheets с торговой матрицей"
    )
    
    # Загрузка Excel файла
    uploaded_file = st.sidebar.file_uploader(
        "Загрузите Excel с остатками",
        type=['xlsx', 'xls'],
        help="Файл с фактическими остатками по магазинам"
    )
    
    # Кнопка загрузки
    load_button = st.sidebar.button("🔄 Загрузить и рассчитать", type="primary")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📖 Легенда статусов")
    st.sidebar.markdown("🔴 **RED** - Критический уровень")
    st.sidebar.markdown("🟡 **YELLOW** - Требуется заказ")
    st.sidebar.markdown("🟢 **GREEN** - Норма")
    st.sidebar.markdown("🔵 **EXCESS** - Излишек")
    
    # ========================
    # ЗАГРУЗКА И ОБРАБОТКА
    # ========================
    
    if load_button:
        if not google_sheet_url:
            st.error("❌ Укажите URL Google Sheets")
            return
        
        if uploaded_file is None:
            st.error("❌ Загрузите Excel файл с остатками")
            return
        
        with st.spinner("⏳ Загрузка данных..."):
            # Загрузка торговой матрицы
            matrix_df = download_google_sheet(google_sheet_url)
            
            if matrix_df is not None:
                st.success(f"✅ Торговая матрица загружена: {len(matrix_df)} строк")
                
                # Валидация
                if not validate_matrix(matrix_df):
                    return
                
                # Загрузка остатков
                stock_df = load_stock_file(uploaded_file)
                
                if stock_df is not None:
                    st.success(f"✅ Остатки загружены: {len(stock_df)} строк")
                    
                    # Расчет DDMRP
                    with st.spinner("🔄 Расчет буферов DDMRP..."):
                        ddmrp_df = calculate_ddmrp_status(matrix_df, stock_df)
                        orders_df = generate_order_report(ddmrp_df)
                    
                    # Сохранение в session_state
                    st.session_state['ddmrp_df'] = ddmrp_df
                    st.session_state['orders_df'] = orders_df
                    st.session_state['matrix_df'] = matrix_df
                    st.session_state['stock_df'] = stock_df
                    
                    st.success("✅ Расчеты выполнены успешно!")
    
    # ========================
    # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ
    # ========================
    
    if 'ddmrp_df' in st.session_state:
        ddmrp_df = st.session_state['ddmrp_df']
        orders_df = st.session_state['orders_df']
        
        # ========================
        # КЛЮЧЕВЫЕ МЕТРИКИ
        # ========================
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_items = len(ddmrp_df)
            st.metric("📦 Всего позиций", total_items)
        
        with col2:
            red_count = len(ddmrp_df[ddmrp_df['Buffer_Status'] == 'RED'])
            st.metric("🔴 Критичных", red_count)
        
        with col3:
            yellow_count = len(ddmrp_df[ddmrp_df['Buffer_Status'] == 'YELLOW'])
            st.metric("🟡 Требуют заказа", yellow_count)
        
        with col4:
            green_count = len(ddmrp_df[ddmrp_df['Buffer_Status'] == 'GREEN'])
            st.metric("🟢 В норме", green_count)
        
        with col5:
            total_order_qty = orders_df['Order_Qty'].sum() if not orders_df.empty else 0
            st.metric("📋 К заказу (шт)", f"{int(total_order_qty)}")
        
        st.markdown("---")
        
        # ========================
        # ВКЛАДКИ
        # ========================
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Заказы",
            "📊 Все товары",
            "🏪 По магазинам",
            "📈 Аналитика",
            "⚙️ Детали расчета"
        ])
        
        # ========================
        # TAB 1: ЗАКАЗЫ
        # ========================
        with tab1:
            st.subheader("📋 Список товаров для заказа")
            
            if not orders_df.empty:
                # Фильтры
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_stores = st.multiselect(
                        "Фильтр по магазинам:",
                        options=sorted(orders_df['Store_ID'].unique()),
                        default=sorted(orders_df['Store_ID'].unique())
                    )
                
                with col2:
                    selected_status = st.multiselect(
                        "Фильтр по статусу:",
                        options=['RED', 'YELLOW'],
                        default=['RED', 'YELLOW']
                    )
                
                # Применение фильтров
                filtered_orders = orders_df[
                    (orders_df['Store_ID'].isin(selected_stores)) &
                    (orders_df['Buffer_Status'].isin(selected_status))
                ]
                
                st.dataframe(
                    filtered_orders,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Скачивание
                st.markdown(
                    create_excel_download(filtered_orders, f"orders_{datetime.now().strftime('%Y%m%d')}.xlsx"),
                    unsafe_allow_html=True
                )
                
                # График топ заказов
                st.markdown("---")
                fig = create_top_orders_chart(filtered_orders)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.success("🎉 Все товары в норме! Заказов не требуется.")
        
        # ========================
        # TAB 2: ВСЕ ТОВАРЫ
        # ========================
        with tab2:
            st.subheader("📊 Полный список товаров и статусы буферов")
            
            # Фильтры
            col1, col2, col3 = st.columns(3)
            
            with col1:
                filter_stores = st.multiselect(
                    "Магазины:",
                    options=sorted(ddmrp_df['Store_ID'].unique()),
                    default=sorted(ddmrp_df['Store_ID'].unique()),
                    key='all_stores'
                )
            
            with col2:
                filter_status = st.multiselect(
                    "Статус буфера:",
                    options=['RED', 'YELLOW', 'GREEN', 'EXCESS'],
                    default=['RED', 'YELLOW', 'GREEN', 'EXCESS'],
                    key='all_status'
                )
            
            with col3:
                search_article = st.text_input("Поиск по артикулу/описанию:")
            
            # Применение фильтров
            filtered_all = ddmrp_df[
                (ddmrp_df['Store_ID'].isin(filter_stores)) &
                (ddmrp_df['Buffer_Status'].isin(filter_status))
            ]
            
            if search_article:
                filtered_all = filtered_all[
                    filtered_all['Article'].str.contains(search_article, case=False, na=False) |
                    filtered_all['Describe'].str.contains(search_article, case=False, na=False)
                ]
            
            st.dataframe(
                filtered_all,
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown(
                create_excel_download(filtered_all, f"all_items_{datetime.now().strftime('%Y%m%d')}.xlsx"),
                unsafe_allow_html=True
            )
        
        # ========================
        # TAB 3: ПО МАГАЗИНАМ
        # ========================
        with tab3:
            st.subheader("🏪 Анализ по магазинам")
            
            # Выбор магазина
            selected_store = st.selectbox(
                "Выберите магазин:",
                options=sorted(ddmrp_df['Store_ID'].unique())
            )
            
            store_data = ddmrp_df[ddmrp_df['Store_ID'] == selected_store]
            
            # Метрики магазина
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Всего SKU", len(store_data))
            
            with col2:
                red_store = len(store_data[store_data['Buffer_Status'] == 'RED'])
                st.metric("🔴 Критичных", red_store)
            
            with col3:
                yellow_store = len(store_data[store_data['Buffer_Status'] == 'YELLOW'])
                st.metric("🟡 Требуют заказа", yellow_store)
            
            with col4:
                order_qty_store = store_data['Order_Qty'].sum()
                st.metric("К заказу (шт)", int(order_qty_store))
            
            st.markdown("---")
            
            # Таблица товаров магазина
            st.dataframe(
                store_data,
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown(
                create_excel_download(store_data, f"store_{selected_store}_{datetime.now().strftime('%Y%m%d')}.xlsx"),
                unsafe_allow_html=True
            )
        
        # ========================
        # TAB 4: АНАЛИТИКА
        # ========================
        with tab4:
            st.subheader("📈 Аналитические графики")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # График распределения статусов
                fig1 = create_buffer_status_chart(ddmrp_df)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # График по магазинам
                fig2 = create_store_summary_chart(ddmrp_df)
                st.plotly_chart(fig2, use_container_width=True)
            
            # Дополнительная аналитика
            if 'ABC_Class' in ddmrp_df.columns:
                st.markdown("---")
                st.subheader("ABC-анализ")
                
                abc_status = ddmrp_df.groupby(['ABC_Class', 'Buffer_Status']).size().reset_index(name='Count')
                
                fig3 = px.bar(
                    abc_status,
                    x='ABC_Class',
                    y='Count',
                    color='Buffer_Status',
                    title='Статусы буферов по ABC-классам',
                    color_discrete_map={
                        'RED': '#FF4444',
                        'YELLOW': '#FFD700',
                        'GREEN': '#44FF44',
                        'EXCESS': '#4444FF'
                    },
                    barmode='group'
                )
                
                st.plotly_chart(fig3, use_container_width=True)
        
        # ========================
        # TAB 5: ДЕТАЛИ РАСЧЕТА
        # ========================
        with tab5:
            st.subheader("⚙️ Методология расчета DDMRP")
            
            st.markdown("""
            ### Зоны буфера:
            
            - **🔴 Красная зона (Red Zone)**: Критический минимум запаса
                - Ниже этого уровня - срочный заказ!
                
            - **🟡 Желтая зона (Yellow Zone)**: Зона пополнения
                - Время сделать заказ
                
            - **🟢 Зеленая зона (Green Zone)**: Целевой запас
                - Нормальный уровень запаса
                
            - **🔵 Излишек (Excess)**: Запас выше Top of Green
                - Возможен избыточный запас
            
            ### Расчет Top of Green:
            ```
            Top of Green = Red Zone + Yellow Zone + Green Zone
            ```
            
            ### Расчет количества для заказа:
            ```
            Order Qty = Top of Green - Current Stock
            ```
            (только для RED и YELLOW статусов)
            
            ### Приоритеты:
            1. 🔴 RED - Максимальный приоритет
            2. 🟡 YELLOW - Высокий приоритет
            3. 🟢 GREEN - Норма (заказ не требуется)
            4. 🔵 EXCESS - Излишек (заказ не требуется)
            """)
            
            # Пример расчета
            st.markdown("---")
            st.subheader("📝 Пример расчета")
            
            example_data = {
                'Параметр': ['Red Zone', 'Yellow Zone', 'Green Zone', 'Top of Green', 'Текущий остаток', 'Статус', 'К заказу'],
                'Значение': ['10 шт', '20 шт', '30 шт', '60 шт', '15 шт', '🟡 YELLOW', '45 шт (60 - 15)']
            }
            
            st.table(pd.DataFrame(example_data))
    
    else:
        # ========================
        # НАЧАЛЬНЫЙ ЭКРАН
        # ========================
        st.info("👆 Загрузите данные через боковую панель для начала работы")
        
        with st.expander("📖 Инструкция по использованию"):
            st.markdown("""
            ### Как использовать систему:
            
            1. **Подготовьте торговую матрицу** в Google Sheets со следующими колонками:
               - `Article` - Артикул товара ⚠️
               - `Describe` - Описание товара ⚠️
               - `Store_ID` - Номер магазина (6, 9, 10...) ⚠️
               - `Red_Zone` - Красная зона (шт) ⚠️
               - `Yellow_Zone` - Желтая зона (шт) ⚠️
               - `Green_Zone` - Зеленая зона (шт) ⚠️
               - `Brand` - Бренд (опционально)
               - `Avg_Daily_Usage` - Средний расход/день (опционально)
               - `ABC_Class` - ABC-класс (опционально)
               - и другие...
            
            2. **Подготовьте файл остатков** в Excel с колонками:
               - `Art` → будет переименовано в `Article` ⚠️
               - `Magazin` → будет переименовано в `Store_ID` ⚠️
               - `Describe` - Описание ⚠️
               - `к-во` → будет переименовано в `Current_Stock` ⚠️
               - `Model` - Модель (опционально)
            
            3. **Вставьте URL** Google Sheets в боковую панель
            
            4. **Загрузите Excel** файл с остатками
            
            5. **Нажмите "Загрузить и рассчитать"**
            
            6. **Анализируйте результаты** во вкладках:
               - 📋 Заказы - список товаров для заказа
               - 📊 Все товары - полный список с буферами
               - 🏪 По магазинам - анализ по каждому магазину
               - 📈 Аналитика - графики и визуализация
               - ⚙️ Детали расчета - методология DDMRP
            
            ### Преимущества DDMRP:
            - ✅ Динамическое управление запасами
            - ✅ Снижение дефицита и излишков
            - ✅ Приоритизация заказов
            - ✅ Визуализация статусов
            - ✅ Автоматический расчет количества для заказа
            """)
        
        with st.expander("🎯 Пример структуры данных"):
            st.markdown("#### Торговая матрица (Google Sheets):")
            example_matrix = pd.DataFrame({
                'Article': ['ART001', 'ART002', 'ART003'],
                'Describe': ['Молоко 3.2% 1л', 'Хлеб белый', 'Масло сливочное'],
                'Store_ID': ['6', '6', '9'],
                'Red_Zone': [10, 15, 5],
                'Yellow_Zone': [20, 25, 10],
                'Green_Zone': [30, 35, 15],
                'Brand': ['Простоквашино', 'Хлебный дом', 'Вологодское']
            })
            st.dataframe(example_matrix, use_container_width=True)
            
            st.markdown("#### Остатки (Excel):")
            example_stock = pd.DataFrame({
                'Art': ['ART001', 'ART002', 'ART003'],
                'Magazin': ['6', '6', '9'],
                'Describe': ['Молоко 3.2% 1л', 'Хлеб белый', 'Масло сливочное'],
                'к-во': [8, 45, 12],
                'Model': ['VPL 932', 'RB 4534', 'VOL 123']
            })
            st.dataframe(example_stock, use_container_width=True)


if __name__ == "__main__":
    main()
