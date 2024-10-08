import os
import pandas as pd
from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
# from pendulum import timezone
import pendulum
###############################################
# Parameters
###############################################
sheet_id = "1UD4YnyMcyFjlG-UpVfzpE4QhSlzeZPGqCY5a130i218"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"

# Path for the CSV file
csv_file_path = "/usr/local/spark/assets/data/sheet.csv"  # เปลี่ยนเป็น path ที่คุณต้องการบันทึก

###############################################
# Function to fetch Google Sheets data and save it as CSV
###############################################
def fetch_and_save_sheet():
    # ดึงข้อมูลจาก Google Sheets
    data = pd.read_csv(url)
    
    # บันทึก DataFrame เป็น CSV
    data.to_csv(csv_file_path, index=False)

###############################################
# Function to read the CSV file, remove first 3 rows, rename columns, and process the data
###############################################
def read_and_process_csv():
    # อ่านข้อมูลจาก CSV
    data = pd.read_csv(csv_file_path)
    
    # # ลบ 3 แถวแรก
    # data = data.iloc[3:]  # ใช้ iloc เพื่อลบแถวจาก DataFrame
    
    # เปลี่ยนชื่อคอลัมน์เป็นภาษาอังกฤษที่ดูง่าย
    data.columns = [
        'Timestamp',
        'Full Name',
        'Gender',
        'Date',
        'Cleanser Product',
        'Photo Instructions',
        'Front View',
        'Left Side View',
        'Right Side View'
    ]  # เปลี่ยนตามชื่อคอลัมน์ที่คุณต้องการ

    # ลบคอลัมน์ Photo Instructions
    data = data.drop(columns=['Photo Instructions'])  # ลบคอลัมน์ที่ไม่ต้องการ
    data[['First Name', 'Last Name']] = data['Full Name'].str.extract(r'(\w+)\s*(\w*)')
    data = data.drop(columns=['Full Name'])  # ลบคอลัมน์ที่ไม่ต้องการ
    

    # บันทึก DataFrame ที่ปรับปรุงแล้วกลับไปที่ CSV
    data.to_csv(csv_file_path, index=False)
    
    # แสดงข้อมูลหลังจากลบแถวและเปลี่ยนชื่อคอลัมน์
    print("Data after removing the first 3 rows, dropping 'Photo Instructions', and renaming columns:")
    print(data.head())  # แสดงข้อมูล 5 แถวแรกหลังจากลบและเปลี่ยนชื่อ

###############################################
# DAG Definition
###############################################

local_tz = pendulum.timezone("Asia/Bangkok")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    'start_date': local_tz.convert(datetime(2024, 10, 5,)),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    "dag-test",
    default_args=default_args,
    schedule_interval='*/1 * * * *',  # รันทุกวันเวลา 0:54
    catchup=False,  # ไม่ทำการ catchup
) as dag:
    start = DummyOperator(task_id='start')

    fetch_data = PythonOperator(
        task_id='fetch_sheets_data',
        python_callable=fetch_and_save_sheet
    )

    process_data = PythonOperator(
        task_id='read_and_process_csv',
        python_callable=read_and_process_csv
    )

    end = DummyOperator(task_id='end')

    start >> fetch_data >> process_data >> end
