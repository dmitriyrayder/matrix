import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
import base64
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# ========================
# НАСТРОЙКИ СТРАНИЦЫ
# ========================
st.set_page_config(
    page_title="DDMRP Система управления остатками",
    page_icon="📊",
    layout="wide"
)

# ========================
# СТИЛИЗАЦИЯ
# ========================

def apply_custom_styles():
    """Применение пользовательских CSS стилей"""
    st.markdown("""
    <style>
        /* Общие стили */
        .main {
            background-color: #f8f9fa;
        }

        /* Заголовки */
        h1 {
            color: #1e3a8a;
            font-weight: 700;
            padding-bottom: 10px;
            border-bottom: 3px solid #3b82f6;
        }

        h2 {
            color: #1e40af;
            font-weight: 600;
        }

        h3 {
            color: #2563eb;
            font-weight: 500;
        }

        /* Метрики */
        [data-testid="stMetricValue"] {
            font-size: 28px;
            font-weight: 700;
        }

        [data-testid="stMetricLabel"] {
            font-size: 14px;
            font-weight: 500;
            color: #64748b;
        }

        /* Кнопки */
        .stButton > button {
            background-color: #3b82f6;
            color: white;
            border-radius: 8px;
            padding: 0.5rem 2rem;
            font-weight: 600;
            border: none;
            transition: all 0.3s ease;
        }

        .stButton > button:hover {
            background-color: #2563eb;
            box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
            transform: translateY(-2px);
        }

        /* Боковая панель */
        [data-testid="stSidebar"] {
            background-color: #f1f5f9;
        }

        [data-testid="stSidebar"] h2 {
            color: #1e40af;
        }

        /* Таблицы */
        .dataframe {
            font-size: 13px;
        }

        .dataframe thead tr th {
            background-color: #3b82f6 !important;
            color: white !important;
            font-weight: 600;
            padding: 12px 8px;
        }

        .dataframe tbody tr:nth-child(even) {
            background-color: #f8fafc;
        }

        .dataframe tbody tr:hover {
            background-color: #e0f2fe;
            transition: background-color 0.2s ease;
        }

        /* Вкладки */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #e2e8f0;
            padding: 8px;
            border-radius: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            background-color: white;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 500;
        }

        .stTabs [aria-selected="true"] {
            background-color: #3b82f6;
            color: white;
        }

        /* Информационные блоки */
        .stAlert {
            border-radius: 8px;
            padding: 1rem;
        }

        /* Карточки */
        div[data-testid="metric-container"] {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        div[data-testid="metric-container"]:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        /* Статусы буферов */
        .status-red {
            background-color: #fee2e2;
            color: #991b1b;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
        }

        .status-yellow {
            background-color: #fef3c7;
            color: #92400e;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
        }

        .status-green {
            background-color: #d1fae5;
            color: #065f46;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
        }

        .status-excess {
            background-color: #dbeafe;
            color: #1e40af;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
        }

        /* Загрузчик файлов */
        [data-testid="stFileUploader"] {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            border: 2px dashed #cbd5e1;
        }

        /* Текстовые поля */
        .stTextInput > div > div > input {
            border-radius: 6px;
            border: 2px solid #e2e8f0;
        }

        .stTextInput > div > div > input:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        /* Разделитель */
        hr {
            margin: 2rem 0;
            border: none;
            border-top: 2px solid #e2e8f0;
        }

        /* Графики */
        .js-plotly-plot {
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)


def style_dataframe(df):
    """Применение стилизации к DataFrame с цветовым кодированием статусов"""

    def highlight_status(row):
        """Раскраска строк по статусу буфера"""
        if 'Buffer_Status' not in row.index:
            return [''] * len(row)

        status = row['Buffer_Status']

        if status == 'RED':
            return ['background-color: #fee2e2'] * len(row)
        elif status == 'YELLOW':
            return ['background-color: #fef3c7'] * len(row)
        elif status == 'GREEN':
            return ['background-color: #d1fae5'] * len(row)
        elif status == 'EXCESS':
            return ['background-color: #dbeafe'] * len(row)
        else:
            return [''] * len(row)

    def color_status_cell(val):
        """Раскраска ячеек статуса"""
        if val == 'RED':
            return 'background-color: #ef4444; color: white; font-weight: bold; text-align: center'
        elif val == 'YELLOW':
            return 'background-color: #eab308; color: white; font-weight: bold; text-align: center'
        elif val == 'GREEN':
            return 'background-color: #22c55e; color: white; font-weight: bold; text-align: center'
        elif val == 'EXCESS':
            return 'background-color: #3b82f6; color: white; font-weight: bold; text-align: center'
        return ''

    def color_priority(val):
        """Раскраска приоритета"""
        if val == 1:
            return 'background-color: #dc2626; color: white; font-weight: bold; text-align: center'
        elif val == 2:
            return 'background-color: #f59e0b; color: white; font-weight: bold; text-align: center'
        elif val == 3:
            return 'background-color: #16a34a; color: white; font-weight: bold; text-align: center'
        elif val == 4:
            return 'background-color: #2563eb; color: white; font-weight: bold; text-align: center'
        return ''

    # Применяем стили
    styled_df = df.style

    # Если есть колонка Buffer_Status, раскрашиваем её
    if 'Buffer_Status' in df.columns:
        styled_df = styled_df.applymap(color_status_cell, subset=['Buffer_Status'])

    # Если есть колонка Priority, раскрашиваем её
    if 'Priority' in df.columns:
        styled_df = styled_df.applymap(color_priority, subset=['Priority'])

    # Форматирование числовых колонок
    format_dict = {}

    if 'Current_Stock' in df.columns:
        format_dict['Current_Stock'] = '{:.0f}'

    if 'Order_Qty' in df.columns:
        format_dict['Order_Qty'] = '{:.0f}'

    if 'Stock_Value' in df.columns:
        format_dict['Stock_Value'] = '{:,.2f}₴'

    if 'Buffer_Fill_Percent' in df.columns:
        format_dict['Buffer_Fill_Percent'] = '{:.1f}%'

    if 'Days_Until_Stockout' in df.columns:
        format_dict['Days_Until_Stockout'] = '{:.1f}'

    if format_dict:
        styled_df = styled_df.format(format_dict, na_rep='-')

    return styled_df


# ========================
# ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ
# ========================

def download_google_sheet(sheet_url, max_retries=3):
    """Загрузка торговой матрицы из Google Sheets с улучшенной обработкой ошибок"""

    # Валидация URL
    if not sheet_url or not isinstance(sheet_url, str):
        st.error("❌ Некорректный URL Google Sheets")
        return None

    if 'docs.google.com/spreadsheets' not in sheet_url:
        st.error("❌ URL должен вести на Google Sheets (docs.google.com/spreadsheets)")
        return None

    try:
        # Преобразование URL в формат экспорта CSV
        if '/edit' in sheet_url:
            csv_url = sheet_url.replace('/edit?gid=', '/export?format=csv&gid=')
            csv_url = csv_url.replace('/edit#gid=', '/export?format=csv&gid=')
            csv_url = csv_url.replace('/edit', '/export?format=csv')
            csv_url = csv_url.split('#')[0]
        else:
            csv_url = sheet_url

        # Retry механизм с экспоненциальной задержкой
        for attempt in range(max_retries):
            try:
                # Запрос с таймаутом
                response = requests.get(csv_url, timeout=30)

                # Проверка статуса
                if response.status_code == 200:
                    # Проверка на пустой ответ
                    if not response.content:
                        st.error("❌ Google Sheets вернул пустой файл")
                        return None

                    # Чтение CSV
                    df = pd.read_csv(BytesIO(response.content))

                    # Проверка на пустой DataFrame
                    if df.empty:
                        st.error("❌ Google Sheets не содержит данных")
                        return None

                    # Проверка на минимальное количество строк
                    if len(df) < 1:
                        st.error("❌ Google Sheets содержит недостаточно данных")
                        return None

                    # Очистка названий колонок от пробелов
                    df.columns = df.columns.str.strip()

                    # Вывод информации о найденных колонках для отладки
                    st.info(f"📋 Найденные колонки в Google Sheets: {', '.join(df.columns.tolist())}")

                    # Маппинг альтернативных названий колонок
                    column_mapping = {
                        'article': 'Article',
                        'ARTICLE': 'Article',
                        'Артикул': 'Article',
                        'артикул': 'Article',
                        'describe': 'Describe',
                        'DESCRIBE': 'Describe',
                        'Description': 'Describe',
                        'Описание': 'Describe',
                        'описание': 'Describe',
                        'Store_ID': 'Store_ID',
                        'store_id': 'Store_ID',
                        'STORE_ID': 'Store_ID',
                        'Magazin': 'Store_ID',
                        'magazin': 'Store_ID',
                        'Магазин': 'Store_ID',
                        'магазин': 'Store_ID',
                        'Red_Zone': 'Red_Zone',
                        'red_zone': 'Red_Zone',
                        'RED_ZONE': 'Red_Zone',
                        'RedZone': 'Red_Zone',
                        'Yellow_Zone': 'Yellow_Zone',
                        'yellow_zone': 'Yellow_Zone',
                        'YELLOW_ZONE': 'Yellow_Zone',
                        'YellowZone': 'Yellow_Zone',
                        'Green_Zone': 'Green_Zone',
                        'green_zone': 'Green_Zone',
                        'GREEN_ZONE': 'Green_Zone',
                        'GreenZone': 'Green_Zone',
                        'Brand': 'Brand',
                        'brand': 'Brand',
                        'Бренд': 'Brand',
                        'бренд': 'Brand',
                        'Retail_Price': 'Retail_Price',
                        'retail_price': 'Retail_Price',
                        'Price': 'Retail_Price',
                        'price': 'Retail_Price',
                        'Цена': 'Retail_Price',
                        'цена': 'Retail_Price',
                        'Avg_Daily_Usage': 'Avg_Daily_Usage',
                        'avg_daily_usage': 'Avg_Daily_Usage',
                        'ABC_Class': 'ABC_Class',
                        'abc_class': 'ABC_Class',
                        'ABC': 'ABC_Class',
                        'Model': 'Model',
                        'model': 'Model',
                        'Модель': 'Model',
                        'модель': 'Model'
                    }

                    # Применение маппинга
                    df = df.rename(columns=column_mapping)

                    st.success(f"✅ Загружено {len(df)} строк из Google Sheets")
                    return df

                elif response.status_code == 403:
                    st.error("❌ Доступ запрещен. Проверьте настройки доступа к Google Sheets (должен быть 'Доступен всем, у кого есть ссылка')")
                    return None

                elif response.status_code == 404:
                    st.error("❌ Google Sheets не найден. Проверьте корректность URL")
                    return None

                else:
                    # Для других кодов ошибок пробуем retry
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 секунды
                        st.warning(f"⚠️ Ошибка {response.status_code}. Повторная попытка через {wait_time} сек...")
                        time.sleep(wait_time)
                        continue
                    else:
                        st.error(f"❌ Ошибка загрузки после {max_retries} попыток: HTTP {response.status_code}")
                        return None

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    st.warning(f"⚠️ Превышено время ожидания. Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                    continue
                else:
                    st.error(f"❌ Превышено время ожидания после {max_retries} попыток")
                    return None

            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    st.warning(f"⚠️ Ошибка подключения. Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                    continue
                else:
                    st.error(f"❌ Ошибка подключения после {max_retries} попыток. Проверьте интернет-соединение")
                    return None

    except pd.errors.EmptyDataError:
        st.error("❌ Google Sheets содержит некорректные данные (пустой CSV)")
        return None

    except pd.errors.ParserError as e:
        st.error(f"❌ Ошибка парсинга CSV из Google Sheets: {str(e)}")
        return None

    except Exception as e:
        st.error(f"❌ Непредвиденная ошибка при загрузке Google Sheets: {str(e)}")
        return None


def load_stock_file(uploaded_file):
    """Загрузка файла остатков Excel с улучшенной обработкой ошибок"""

    # Проверка наличия файла
    if uploaded_file is None:
        st.error("❌ Файл не загружен")
        return None

    try:
        # Чтение Excel файла
        try:
            df = pd.read_excel(uploaded_file)
        except ValueError as e:
            st.error(f"❌ Ошибка формата файла. Убедитесь, что файл имеет формат .xlsx или .xls: {str(e)}")
            return None
        except Exception as e:
            st.error(f"❌ Не удалось прочитать Excel файл: {str(e)}")
            return None

        # Проверка на пустой файл
        if df.empty:
            st.error("❌ Excel файл не содержит данных")
            return None

        # Вывод информации о найденных колонках для отладки
        st.info(f"📋 Найденные колонки: {', '.join(df.columns.tolist())}")

        # Маппинг колонок (поддержка различных вариантов названий)
        column_mapping = {
            'Art': 'Article',
            'art': 'Article',
            'Артикул': 'Article',
            'артикул': 'Article',
            'Magazin': 'Store_ID',
            'magazin': 'Store_ID',
            'Магазин': 'Store_ID',
            'магазин': 'Store_ID',
            'Store': 'Store_ID',
            'Describe': 'Describe',
            'describe': 'Describe',
            'Description': 'Describe',
            'Описание': 'Describe',
            'описание': 'Describe',
            'к-во': 'Current_Stock',
            'кво': 'Current_Stock',
            'Количество': 'Current_Stock',
            'количество': 'Current_Stock',
            'Qty': 'Current_Stock',
            'qty': 'Current_Stock',
            'Stock': 'Current_Stock',
            'Model': 'Model',
            'model': 'Model',
            'Модель': 'Model',
            'модель': 'Model'
        }

        # Применение маппинга
        df = df.rename(columns=column_mapping)

        # Проверка обязательных колонок
        required_cols = ['Article', 'Store_ID', 'Describe', 'Current_Stock']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.error(f"❌ Отсутствуют обязательные колонки: {', '.join(missing_cols)}")
            st.info("💡 Убедитесь, что файл содержит колонки: Art, Magazin, Describe, к-во")
            return None

        # Очистка и валидация данных
        try:
            # Очистка Current_Stock
            df['Current_Stock'] = pd.to_numeric(df['Current_Stock'], errors='coerce')

            # Подсчет невалидных значений
            invalid_stock_count = df['Current_Stock'].isna().sum()
            if invalid_stock_count > 0:
                st.warning(f"⚠️ Найдено {invalid_stock_count} невалидных значений в колонке 'к-во'. Заменены на 0")

            df['Current_Stock'] = df['Current_Stock'].fillna(0)

            # Проверка на отрицательные значения
            negative_stock = (df['Current_Stock'] < 0).sum()
            if negative_stock > 0:
                st.warning(f"⚠️ Найдено {negative_stock} отрицательных значений остатков. Заменены на 0")
                df['Current_Stock'] = df['Current_Stock'].clip(lower=0)

            # Очистка Store_ID
            df['Store_ID'] = df['Store_ID'].astype(str).str.strip()
            df['Store_ID'] = df['Store_ID'].replace('nan', '')

            # Удаление строк с пустым Store_ID
            empty_store_count = (df['Store_ID'] == '').sum()
            if empty_store_count > 0:
                st.warning(f"⚠️ Удалено {empty_store_count} строк с пустым номером магазина")
                df = df[df['Store_ID'] != '']

            # Очистка Article
            df['Article'] = df['Article'].astype(str).str.strip()
            df['Article'] = df['Article'].replace('nan', '')

            # Удаление строк с пустым артикулом
            empty_article_count = (df['Article'] == '').sum()
            if empty_article_count > 0:
                st.warning(f"⚠️ Удалено {empty_article_count} строк с пустым артикулом")
                df = df[df['Article'] != '']

            # Очистка Describe
            df['Describe'] = df['Describe'].astype(str).str.strip()
            df['Describe'] = df['Describe'].replace('nan', 'Без описания')

        except Exception as e:
            st.error(f"❌ Ошибка при очистке данных: {str(e)}")
            return None

        # Финальная проверка
        if df.empty:
            st.error("❌ После очистки данных не осталось валидных строк")
            return None

        st.success(f"✅ Загружено {len(df)} строк из Excel файла")
        return df

    except Exception as e:
        st.error(f"❌ Непредвиденная ошибка при загрузке Excel: {str(e)}")
        return None


def validate_matrix(df):
    """Валидация торговой матрицы с улучшенной проверкой данных"""

    # Создаем копию для безопасной обработки
    df = df.copy()

    required_cols = ['Article', 'Describe', 'Store_ID', 'Red_Zone', 'Yellow_Zone', 'Green_Zone']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"❌ В торговой матрице отсутствуют колонки: {', '.join(missing_cols)}")
        st.info(f"💡 Доступные колонки: {', '.join(df.columns.tolist())}")
        return None

    # Проверка типов данных
    df['Red_Zone'] = pd.to_numeric(df['Red_Zone'], errors='coerce')
    df['Yellow_Zone'] = pd.to_numeric(df['Yellow_Zone'], errors='coerce')
    df['Green_Zone'] = pd.to_numeric(df['Green_Zone'], errors='coerce')
    df['Store_ID'] = df['Store_ID'].astype(str).str.strip()
    df['Article'] = df['Article'].astype(str).str.strip()

    # Подсчет невалидных значений в зонах
    red_invalid = df['Red_Zone'].isna().sum()
    yellow_invalid = df['Yellow_Zone'].isna().sum()
    green_invalid = df['Green_Zone'].isna().sum()

    if red_invalid > 0 or yellow_invalid > 0 or green_invalid > 0:
        st.warning(f"⚠️ Найдены невалидные значения: Red_Zone: {red_invalid}, Yellow_Zone: {yellow_invalid}, Green_Zone: {green_invalid}")

    # Замена NaN на 0 для зон
    df['Red_Zone'] = df['Red_Zone'].fillna(0)
    df['Yellow_Zone'] = df['Yellow_Zone'].fillna(0)
    df['Green_Zone'] = df['Green_Zone'].fillna(0)

    # Проверка на отрицательные значения
    negative_red = (df['Red_Zone'] < 0).sum()
    negative_yellow = (df['Yellow_Zone'] < 0).sum()
    negative_green = (df['Green_Zone'] < 0).sum()

    if negative_red > 0:
        st.warning(f"⚠️ Найдено {negative_red} отрицательных значений в Red_Zone. Заменены на 0")
        df['Red_Zone'] = df['Red_Zone'].clip(lower=0)

    if negative_yellow > 0:
        st.warning(f"⚠️ Найдено {negative_yellow} отрицательных значений в Yellow_Zone. Заменены на 0")
        df['Yellow_Zone'] = df['Yellow_Zone'].clip(lower=0)

    if negative_green > 0:
        st.warning(f"⚠️ Найдено {negative_green} отрицательных значений в Green_Zone. Заменены на 0")
        df['Green_Zone'] = df['Green_Zone'].clip(lower=0)

    # Проверка на нулевые буферы (все три зоны равны 0)
    zero_buffers = ((df['Red_Zone'] == 0) & (df['Yellow_Zone'] == 0) & (df['Green_Zone'] == 0)).sum()
    if zero_buffers > 0:
        st.warning(f"⚠️ Найдено {zero_buffers} позиций с нулевыми буферами (все зоны = 0)")

    # Проверка на пустые значения в Article и Store_ID
    empty_articles = df['Article'].isna().sum()
    empty_stores = df['Store_ID'].isna().sum()

    if empty_articles > 0:
        st.warning(f"⚠️ Найдено {empty_articles} пустых артикулов")

    if empty_stores > 0:
        st.warning(f"⚠️ Найдено {empty_stores} пустых номеров магазинов")

    st.success(f"✅ Торговая матрица валидирована: {len(df)} строк")
    return df


# ========================
# DDMRP ЛОГИКА
# ========================

def calculate_ddmrp_status(matrix_df, stock_df):
    """
    Расчет статуса буферов DDMRP для каждого товара в каждом магазине с улучшенной обработкой ошибок
    """
    try:
        # Проверка входных данных
        if matrix_df is None or matrix_df.empty:
            st.error("❌ Матрица пуста")
            return None

        if stock_df is None or stock_df.empty:
            st.error("❌ Данные остатков пусты")
            return None

        # Подготовка данных для объединения
        stock_cols = ['Article', 'Store_ID', 'Current_Stock']
        if 'Model' in stock_df.columns:
            stock_cols.append('Model')

        # Объединяем матрицу и остатки
        merged = matrix_df.merge(
            stock_df[stock_cols],
            on=['Article', 'Store_ID'],
            how='left'
        )

        # Проверка результата объединения
        if merged.empty:
            st.error("❌ После объединения данных не осталось строк. Проверьте соответствие артикулов и магазинов")
            return None

        # Заполняем отсутствующие остатки нулями
        merged['Current_Stock'] = pd.to_numeric(merged['Current_Stock'], errors='coerce').fillna(0)

        # Убедимся, что зоны числовые и неотрицательные
        merged['Red_Zone'] = pd.to_numeric(merged['Red_Zone'], errors='coerce').fillna(0).clip(lower=0)
        merged['Yellow_Zone'] = pd.to_numeric(merged['Yellow_Zone'], errors='coerce').fillna(0).clip(lower=0)
        merged['Green_Zone'] = pd.to_numeric(merged['Green_Zone'], errors='coerce').fillna(0).clip(lower=0)

        # Расчет стоимости остатков (Retail_Price * Current_Stock)
        if 'Retail_Price' in merged.columns:
            merged['Retail_Price'] = pd.to_numeric(merged['Retail_Price'], errors='coerce').fillna(0).clip(lower=0)
            merged['Stock_Value'] = merged['Retail_Price'] * merged['Current_Stock']
        else:
            merged['Stock_Value'] = 0

        # Расчет Top of Green (максимальный уровень запаса)
        # Формула: Top_of_Green = Red_Zone + Yellow_Zone + Green_Zone
        merged['Top_of_Green'] = merged['Red_Zone'] + merged['Yellow_Zone'] + merged['Green_Zone']

        # Расчет границ зон
        merged['Red_Zone_Max'] = merged['Red_Zone']
        merged['Yellow_Zone_Max'] = merged['Red_Zone'] + merged['Yellow_Zone']
        merged['Green_Zone_Max'] = merged['Top_of_Green']

        # Определение статуса буфера
        def get_buffer_status(row):
            stock = row['Current_Stock']
            red_max = row['Red_Zone_Max']
            yellow_max = row['Yellow_Zone_Max']
            green_max = row['Green_Zone_Max']

            # Проверка на нулевой буфер
            if green_max == 0:
                return 'N/A'  # Нет данных о буфере

            # Определение зоны
            if stock <= red_max:
                return 'RED'
            elif stock <= yellow_max:
                return 'YELLOW'
            elif stock <= green_max:
                return 'GREEN'
            else:
                return 'EXCESS'  # Излишек

        merged['Buffer_Status'] = merged.apply(get_buffer_status, axis=1)

        # Расчет процента заполнения буфера (защита от деления на ноль)
        # Формула: Buffer_Fill_Percent = (Current_Stock / Top_of_Green) * 100
        merged['Buffer_Fill_Percent'] = np.where(
            merged['Top_of_Green'] > 0,
            (merged['Current_Stock'] / merged['Top_of_Green'] * 100).round(1),
            0
        )

        # Расчет количества для заказа
        # Формула: Order_Qty = Top_of_Green - Current_Stock (только для RED и YELLOW)
        def calculate_order_qty(row):
            if row['Buffer_Status'] in ['RED', 'YELLOW']:
                # Заказываем до Top of Green
                order_qty = row['Top_of_Green'] - row['Current_Stock']
                return max(0, round(order_qty, 0))
            return 0

        merged['Order_Qty'] = merged.apply(calculate_order_qty, axis=1)

        # Приоритет заказа (RED = 1, YELLOW = 2, GREEN = 3, EXCESS = 4, N/A = 5)
        priority_map = {'RED': 1, 'YELLOW': 2, 'GREEN': 3, 'EXCESS': 4, 'N/A': 5}
        merged['Priority'] = merged['Buffer_Status'].map(priority_map)

        # Расчет дней до исчерпания запаса (если есть Avg_Daily_Usage)
        if 'Avg_Daily_Usage' in merged.columns:
            merged['Avg_Daily_Usage'] = pd.to_numeric(merged['Avg_Daily_Usage'], errors='coerce').fillna(0).clip(lower=0)

            # Защита от деления на ноль
            merged['Days_Until_Stockout'] = np.where(
                merged['Avg_Daily_Usage'] > 0,
                (merged['Current_Stock'] / merged['Avg_Daily_Usage']).round(1),
                np.inf
            )
        else:
            merged['Days_Until_Stockout'] = np.nan

        # Финальная валидация
        if merged.empty:
            st.error("❌ После расчетов не осталось данных")
            return None

        st.success(f"✅ Рассчитано {len(merged)} позиций")
        return merged

    except Exception as e:
        st.error(f"❌ Ошибка при расчете DDMRP: {str(e)}")
        return None


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
        'Current_Stock', 'Stock_Value', 'Top_of_Green', 'Order_Qty', 
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
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Скачать {filename}</a>'
    return href


# ========================
# STREAMLIT ИНТЕРФЕЙС
# ========================

def main():
    # Применение пользовательских стилей
    apply_custom_styles()

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
                # Валидация и обработка торговой матрицы
                matrix_df = validate_matrix(matrix_df)

                if matrix_df is None:
                    return

                # Загрузка остатков
                stock_df = load_stock_file(uploaded_file)

                if stock_df is not None:
                    # Расчет DDMRP
                    with st.spinner("🔄 Расчет буферов DDMRP..."):
                        ddmrp_df = calculate_ddmrp_status(matrix_df, stock_df)

                        if ddmrp_df is None:
                            return

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
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
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
        
        with col6:
            total_stock_value = ddmrp_df['Stock_Value'].sum() if 'Stock_Value' in ddmrp_df.columns else 0
            st.metric("💰 Остатки (₴)", f"{total_stock_value:,.0f}")
        
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
            col1, col2, col3, col4, col5 = st.columns(5)
            
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
            
            with col5:
                store_value = store_data['Stock_Value'].sum() if 'Stock_Value' in store_data.columns else 0
                st.metric("💰 Остатки (₴)", f"{store_value:,.0f}")
            
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
            
            # График стоимости остатков по магазинам
            if 'Stock_Value' in ddmrp_df.columns:
                st.markdown("---")
                st.subheader("💰 Стоимость остатков по магазинам")
                
                store_value_summary = ddmrp_df.groupby('Store_ID')['Stock_Value'].sum().reset_index()
                store_value_summary = store_value_summary.sort_values('Stock_Value', ascending=False)
                
                fig_value = px.bar(
                    store_value_summary,
                    x='Store_ID',
                    y='Stock_Value',
                    title='Стоимость остатков по магазинам (₴)',
                    labels={'Stock_Value': 'Сумма (₴)', 'Store_ID': 'Магазин'},
                    text='Stock_Value'
                )
                
                fig_value.update_traces(texttemplate='%{text:,.0f}₴', textposition='outside')
                fig_value.update_layout(xaxis_title='Магазин', yaxis_title='Стоимость остатков (₴)')
                
                st.plotly_chart(fig_value, use_container_width=True)
                
                # Таблица с детализацией
                col1, col2 = st.columns(2)
                with col1:
                    st.dataframe(
                        store_value_summary.style.format({'Stock_Value': '{:,.0f}₴'}),
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col2:
                    total_value = store_value_summary['Stock_Value'].sum()
                    st.metric("💰 Общая сумма остатков", f"{total_value:,.0f}₴")
                    avg_value = store_value_summary['Stock_Value'].mean()
                    st.metric("📊 Средняя сумма на магазин", f"{avg_value:,.0f}₴")
            
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
