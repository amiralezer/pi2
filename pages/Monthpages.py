import streamlit as st
import pandas as pd
import pymysql.cursors
import numpy as np
import plotly.express as px 
import plotly.graph_objs as go
from datetime import time
from datetime import datetime, timedelta

# def seconds_to_hours(seconds):
#     hours = round((seconds / 3600),2)
#     return f"{hours} Horas"

@st.cache_data
def get_start_and_end_of_week(week):
    year, week_number = map(int, week.split('-'))
    monday = datetime.fromisocalendar(year, week_number, 1)
    start_datetime = datetime.combine(monday.date(), time().min)
    end_datetime = datetime.combine((monday + timedelta(days=6)).date(), time().max)

    return start_datetime, end_datetime

@st.cache_data
def get_month_data():
    cursor = conn.cursor()
    cursor.execute("SELECT DATE_FORMAT(moment, '%Y %M') AS Month  FROM " + tableName + " group by year(moment), month(moment),  date_format(moment, '%Y %M') order by year(moment) desc, month(moment) desc")
    month_data = cursor.fetchall()
    month_df = pd.DataFrame(month_data,columns=['Month'])

    return month_df


@st.cache_data
def get_week_data():
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT week_year FROM " + tableName)
    week_data = cursor.fetchall()
    weeks_df = pd.DataFrame(week_data,columns=['week_year'])
    weeks_df['inital_date'], weeks_df['end_date'] = zip(*weeks_df['week_year'].apply(lambda yr_week: get_start_and_end_of_week(yr_week)))
    weeks_df['range'] = weeks_df.apply(lambda row: f"{row['inital_date'].strftime('%Y-%m-%d')} to {row['end_date'].strftime('%Y-%m-%d')}", axis=1)

    return weeks_df

@st.cache_data
def load_data(filter_option,method):
    cursor = conn.cursor()
    cursor.execute("SELECT moment, voltage, current, power_W, energy_WH, power_factor_measured, power_factor_calc, phase_angle_measured, phase_angle_calc, opMode,week_year,active_hours  FROM " + tableName)
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=['moment', 'voltage', 'current', 'power_W', 'energy_WH', 'power_factor_measured', 'power_factor_calc', 'phase_angle_measured', 'phase_angle_calc', 'opMode','week_year','active_hours'])
    
    if (method == 'Weekly'):
        date_obj = datetime.strptime(filter_option.split(' ')[0], '%Y-%m-%d')
        year_week_iso = date_obj.isocalendar()
        year_week_iso_format = f"{year_week_iso[0]}-{year_week_iso[1]:02d}"
        df = df[(df['week_year']==year_week_iso_format)]

    elif (method == 'Monthly'):
        dt_obj = datetime.strptime(filter_option, '%Y %B')
        str_value = dt_obj.strftime('%Y-%m')
        df = df[df['moment'].str.startswith(str_value)]
    
    elif (method == 'Custom'):
        df['moment'] = pd.to_datetime(df['moment'])
        df["week"] = df["moment"].apply(lambda x: x.strftime("%Y-%U"))
        df = df[(df['moment']>=filter_option[0]) & (df['moment']<filter_option[1])]

    return df

mapping = {1: 'On', 2: 'StandBy', 0: 'Off'}
mapping_hours = {1: 'Horário Ativo', 0: 'Horário Inativo'}
colors = ["#42f5e9","#f57b42", "#f5ef42"]

measuringTime = 5
tableName = 'compressor_measurements'
#tableName = 'imported'

conn = pymysql.connect(host='utfpr-pi2-compressor-monitor.mysql.database.azure.com',
                       user='pi2root',
                       password='UTFPR@senha',
                       database='pi2')

# conn = pymysql.connect(host='localhost',
#                        user='root',
#                        password='root',
#                        database='node_test')


if 'min' not in st.session_state:
    cursor = conn.cursor()
    cursor.execute("SELECT Min(moment) FROM "+ tableName)
    st.session_state.min = cursor.fetchone()[0]

    cursor.execute("SELECT Max(moment) FROM "+ tableName)
    st.session_state.max= cursor.fetchone()[0]
    
    if isinstance(st.session_state.min, str):
        st.session_state.min = datetime.strptime(st.session_state.min, '%Y-%m-%d %H:%M:%S')
    if isinstance(st.session_state.max, str):
        st.session_state.max = datetime.strptime(st.session_state.max, '%Y-%m-%d %H:%M:%S')


page1 = "Monitoramento Compressor - UTFPR"
st.set_page_config(page_title=page1)
st.markdown("# " + page1)
st.write(
    "Escolha os limites de data que você quer ver o funcionamento do compressor da UTFPR: "
)

filter_type = st.selectbox("Select filter type", ["Monthly", "Weekly","Custom"])

weeks_df = get_week_data()
month_df = get_month_data()

if filter_type == "Custom":
    date_select = st.slider('Select the time range:',
                        value=(st.session_state.min, st.session_state.max),
                        min_value=st.session_state.min,
                        max_value=st.session_state.max,
                        format="DD/MM/YY - hh:mm",
                        key=("slider", st.session_state.min, st.session_state.max))

    df = load_data(date_select,filter_type)

else:
    if filter_type == "Monthly":
        options = month_df['Month']
        filter_option = st.selectbox("Select an option", options)
        df = load_data(filter_option,filter_type)

    elif filter_type == "Weekly":
        options = weeks_df['range']
        filter_option = st.selectbox("Select an option", options)
        df = load_data(filter_option,filter_type)
      
with st.container():
    st.write("Modos de operação")
    stackeddf = df
    if filter_type == "Weekly":
        stackeddf['moment'] = pd.to_datetime(stackeddf['moment']).dt.strftime('%Y-%m-%d')
        dailyValues = stackeddf.groupby(['moment','active_hours','opMode']).size()
        result_df = dailyValues.apply(lambda x: round((x*5)/60),2).reset_index(name='result')
        groupedAgain = result_df.groupby(['moment','active_hours','opMode'])['result'].sum().reset_index()
        groupedAgain['opMode'] = groupedAgain['opMode'].replace(mapping)
        groupedAgain['active_hours'] = groupedAgain['active_hours'].replace(mapping_hours)

        fig = go.Figure()
        fig.update_layout(
            template="simple_white",
            xaxis=dict(title_text="Day"),
            yaxis=dict(title_text="Time"),
            barmode="group",
        )

        for r, c in zip(groupedAgain['opMode'].unique(), colors):
            plot_df = groupedAgain[groupedAgain['opMode'] == r]
            fig.add_trace(
                go.Bar(x=[plot_df['moment'], plot_df['active_hours']], y=plot_df['result'], name=str(r), marker_color=c)
            )

        st.plotly_chart(fig, use_container_width=True)

st.dataframe(df)
st.dataframe(weeks_df)

st.text('Lucas Moletta')
