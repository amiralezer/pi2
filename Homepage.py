import streamlit as st
import numpy as np
import plotly.express as px 
from datetime import time,datetime, timedelta
import polars as pl
import connectorx as cx
import lttbc


def seconds_to_hours(seconds):
    hours = round((seconds / 3600),2)
    return f"{hours} Horas"


def load_data(date_select,df,measuringTime):

    sample_size = 35000
    df = df.filter(pl.col("moment").is_between(date_select[0],date_select[1]))
    print(df)
    
    
    ###### calculando tempo de operacoes antes de aplicar downsampling 
    qtyOff = len(df.filter(pl.col("opMode") == 0 ))
    qtyOffSec = qtyOff * measuringTime

    qtyOn = len(df.filter(pl.col("opMode") == 1 ))
    qtyOnSec = qtyOn * measuringTime

    qtyStandby = len(df.filter(pl.col("opMode") == 2 ))
    qtyStandbySec = qtyStandby * measuringTime

    ##calculando stacked bar metrics

    stackeddf = df.select(pl.col("moment").dt.date())
    stackeddf = stackeddf.with_columns(pl.lit(df.get_column('opMode')).alias('opMode'))
    dailyValues = stackeddf.groupby(['moment','opMode'], maintain_order=True).count()
    dailyValues = dailyValues.with_columns(dailyValues.select(pl.col("count")/60))
    dailyValues = dailyValues.with_columns(pl.col("count").round(2))
    dailyValues = dailyValues.with_columns(pl.col("opMode").str.replace("1", "On"))
    dailyValues = dailyValues.with_columns(pl.col("opMode").str.replace("2", "StandBy"))
    dailyValues = dailyValues.with_columns(pl.col("opMode").str.replace("0", "Off"))

    df = df.with_columns(pl.col("moment").apply(lambda x: x.timestamp()))

    moment_downsampled = df['moment'].to_list()
    voltage_downsampled = df['voltage'].to_list()
    current_downsampled = df['current'].to_list()
    power_W_downsampled = df['power_W'].to_list()
    power_factor_measured_downsampled = df['power_factor_measured'].to_list()
    power_factor_calc_downsampled = df['power_factor_calc'].to_list()
    phase_angle_measured_downsampled = df['phase_angle_measured'].to_list()
    phase_angle_calc_downsampled = df['phase_angle_calc'].to_list()
    opMode_downsampled = df['opMode'].to_list()

    n_moment_downsampled , n_voltage_downsampled = lttbc.downsample(moment_downsampled, voltage_downsampled, sample_size)
    n_moment_downsampled , n_current_downsampled = lttbc.downsample(moment_downsampled, current_downsampled, sample_size)
    n_moment_downsampled , n_power_W_downsampled = lttbc.downsample(moment_downsampled, power_W_downsampled, sample_size)
    n_moment_downsampled , n_power_factor_measured_downsampled = lttbc.downsample(moment_downsampled, power_factor_measured_downsampled, sample_size)
    n_moment_downsampled , n_power_factor_calc_downsampled = lttbc.downsample(moment_downsampled,  power_factor_calc_downsampled, sample_size)
    n_moment_downsampled , n_phase_angle_measured_downsampled = lttbc.downsample(moment_downsampled,  phase_angle_measured_downsampled, sample_size)
    n_moment_downsampled , n_phase_angle_calc_downsampled = lttbc.downsample(moment_downsampled,  phase_angle_calc_downsampled, sample_size)
    n_moment_downsampled , n_opMode_downsampled = lttbc.downsample(moment_downsampled,  opMode_downsampled, sample_size)
    data = {"moment": n_moment_downsampled
            , "voltage": n_voltage_downsampled
            , "current": n_current_downsampled
            , "power_W": n_power_W_downsampled
            , "power_factor_measured": n_power_factor_measured_downsampled
            , "power_factor_calc": n_power_factor_calc_downsampled
            , "phase_angle_measured": n_phase_angle_measured_downsampled
            , "phase_angle_calc": n_phase_angle_calc_downsampled
            , "opMode": n_opMode_downsampled
            }
    final_df = pl.DataFrame(data)
    final_df = final_df.with_columns(pl.col("moment").apply(lambda x:datetime.fromtimestamp(x)))
    final_df = final_df.with_columns(pl.col("moment").dt.strftime("%Y-%U").alias('week'))
    return final_df,qtyOffSec,qtyOnSec,qtyStandbySec,dailyValues



charts = {
    'Tensão': lambda df: px.scatter( x = df_final['moment'], y = df_final['voltage'], title='Tensão [V]', labels = {'voltage': 'Tensão', 'moment': 'Horário'}, render_mode='webgl'),
    'Corrente': lambda df_final: px.scatter( x = df_final['moment'], y = df_final['current'], title='Corrente [A]',  labels = {'current': 'Corrente', 'moment': 'Horário'}, render_mode='webgl'),
    'Potência': lambda df_final: px.scatter( x = df_final['moment'], y = df_final['power_W'], title='Potência [W]',  labels = {'power_W': 'Potência', 'moment': 'Horário'}, render_mode='webgl'),
    'Fator de Potência': lambda df: px.scatter( x = df_power_factor['moment'], y = df_power_factor['power_factor'], color = df_power_factor['source'], title='Fator de Potência', labels = {'power_factor_measured': 'Medido', 'power_factor_calc': 'Calculado', 'moment': 'Horário'}, render_mode='webgl'),
    'Ângulo de Fase' : lambda df: px.scatter(x = df_phase_angle['moment'], y = df_phase_angle['phase_angle'],color = df_phase_angle['source'],  title='Ângulo de Fase [Graus]' , labels = {'phase_angle_measured': 'Medido', 'phase_angle_calc': 'Calculado', 'moment': 'Horário'}, render_mode='webgl')
}

connectionstring = "mysql://python:python@utfpr-pi2-compressor-monitor.mysql.database.azure.com:3306/pi2"
column_names = ['moment', 'voltage', 'current', 'power_W', 'energy_WH', 'power_factor_measured', 'power_factor_calc', 'phase_angle_measured', 'phase_angle_calc', 'opMode']
mapping = {1: 'On', 2: 'StandBy', 0: 'Off'}

measuringTime = 1
tableName = 'compressor_measurements'


if 'min' not in st.session_state:
    query = "SELECT moment , voltage, current, power_W, power_factor_measured, power_factor_calc, phase_angle_measured, phase_angle_calc, opMode FROM " + tableName + ";"
    st.session_state.df = cx.read_sql(connectionstring, query, return_type = "polars")
    st.session_state.min = st.session_state.df['moment'].min()
    st.session_state.min_selected = st.session_state.df['moment'][-65000]
    st.session_state.max_selected = st.session_state.df['moment'].max()
    st.session_state.max= st.session_state.df['moment'].max()
    
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

date_select = st.slider('Select the time range:',
                        value=( st.session_state.min_selected, st.session_state.max_selected),
                        min_value=st.session_state.min,
                        max_value=st.session_state.max,
                        format="DD/MM/YY - hh:mm",
                        step=timedelta(hours=8),
                        key=("slider"))

st.sidebar.header("Data das informações: \n" + str(date_select[0]) + " até \n" + str(date_select[1]))
charts_selected = st.multiselect('Selecione os gráficos que deseja ver:', list(charts.keys()), default=list(charts.keys()))



##### Massageando df

df_final,qtyOffSec,qtyOnSec,qtyStandbySec,dailyValues = load_data(date_select,st.session_state.df,measuringTime)

## DF for fator de potencia
df_power_factor1 = df_final.select(pl.col("power_factor_measured").alias('power_factor'))
df_power_factor1 = df_power_factor1.with_columns(pl.lit('power_factor_measured').alias('source'))
df_power_factor1 = df_power_factor1.with_columns(pl.lit(df_final.get_column('moment')).alias('moment'))


df_power_factor2 = df_final.select(pl.col("power_factor_calc").alias('power_factor'))
df_power_factor2 = df_power_factor2.with_columns(pl.lit('power_factor_calc').alias('source'))
df_power_factor2 = df_power_factor2.with_columns(pl.lit(df_final.get_column('moment')).alias('moment'))


df_power_factor = pl.concat([df_power_factor1,df_power_factor2], rechunk=True)

## DF for angulo de fase
df_phase_angle1 = df_final.select(pl.col("phase_angle_measured").alias('phase_angle'))
df_phase_angle1 = df_phase_angle1.with_columns(pl.lit('phase_angle_measured').alias('source'))
df_phase_angle1 = df_phase_angle1.with_columns(pl.lit(df_final.get_column('moment')).alias('moment'))


df_phase_angle2 = df_final.select(pl.col("phase_angle_calc").alias('phase_angle'))
df_phase_angle2 = df_phase_angle2.with_columns(pl.lit('phase_angle_calc').alias('source'))
df_phase_angle2 = df_phase_angle2.with_columns(pl.lit(df_final.get_column('moment')).alias('moment'))


df_phase_angle = pl.concat([df_phase_angle1,df_phase_angle2], rechunk=True)

for chart_name in charts_selected:
    chart_function = charts[chart_name]
    with st.container():
        fig = chart_function(df_final)
        st.plotly_chart(fig, use_container_width=True)



with st.container():
    st.write("Modos de operação")
    fig = px.bar(dailyValues,  x=dailyValues['moment'],  y=dailyValues['count'], color=dailyValues['opMode'], labels = {'result': 'Tempo de operação (m)', 'moment': 'Horário','opMode':'Modo de Operação' })
    st.plotly_chart(fig, use_container_width=True)



#Para as métricas de modo de operação, quantas vezes ficou ligado, quantas vezes desligado, o outro modo de operação lá e por fim a qtd de Ah do período
with st.sidebar:
    if (len(df_final['current']) != 0):
        currentAvg = df_final['current'].mean()
        powerFacAvg = df_final['power_factor_calc'].mean()
        st.metric("Corrente Média no período",  str(round(currentAvg, 3)) + " A")
        st.metric("Fator de Potência calculado no período", round(powerFacAvg, 3))
        st.metric("Tempo desligado durante o período", seconds_to_hours(qtyOffSec))
        st.metric("Tempo ligado durante o período", seconds_to_hours(qtyOnSec))
        st.metric("Tempo em standby durante o período", seconds_to_hours(qtyStandbySec))

st.text('Lucas Moletta')
