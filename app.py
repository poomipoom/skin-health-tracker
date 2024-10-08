import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import sqlite3
import base64
import io
from PIL import Image
from model import infer_image_with_sdk, infer_image_with_transformers, infer_image_with_facedetect
from datetime import datetime  # เพิ่มการนำเข้าจาก datetime
import requests
from io import BytesIO
import plotly.graph_objects as go
from flask import Flask, Response
from PIL import Image, ExifTags
import cv2  # For camera handling# ตัวแปรเพื่อเก็บภาพที่ถ่าย
import threading
captured_images = [None, None, None] 
from plotly.subplots import make_subplots



cap = cv2.VideoCapture(-1)

def correct_image_orientation(image):
    try:
        # ดึงข้อมูล EXIF ของภาพ
        exif = image._getexif()
        
        # ตรวจสอบว่า EXIF มีข้อมูล Orientation หรือไม่
        if exif:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break

            # หมุนภาพตามค่า Orientation
            if exif[orientation] == 3:
                image = image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image = image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image = image.rotate(90, expand=True)

    except (AttributeError, KeyError, IndexError):
        # หากไม่มีข้อมูล EXIF หรือไม่มีข้อมูล Orientation ให้ข้ามไป
        pass

    return image

def capture_image_from_camera():
    ret, frame = cap.read()  # ใช้ cap ที่เปิดอยู่แล้ว
    if not ret:
        return None, "Failed to capture image."

    # แปลงภาพเป็น base64
    _, buffer = cv2.imencode('.jpg', frame)
    image_base64 = base64.b64encode(buffer).decode('utf-8')
    image_src = f'data:image/jpeg;base64,{image_base64}'
    # ตรวจสอบว่าจับภาพครบ 3 รูปหรือยัง
    if all(img is not None for img in captured_images):
        cap.release()  # ปิดกล้องเมื่อจับภาพครบ
        return image_src, "Captured all images."  # คืนค่าภาพที่จับได้

    return image_src, None  # คืนค่า image_src

def capture_images_in_thread(index):
    global captured_images

    # ตรวจสอบให้แน่ใจว่าดัชนีไม่เกินขอบเขต
    if index < 0 or index >= len(captured_images):
        print(f"Invalid index: {index}")
        return  # หยุดการทำงานของเธรดถ้าดัชนีไม่ถูกต้อง

    # ถ่ายภาพ
    image_src, error_message = capture_image_from_camera()

    if image_src is not None:
        captured_images[index] = image_src  # เก็บภาพที่จับในตำแหน่งที่ถูกต้อง
    else:
        print(error_message)  # แสดงข้อความข้อผิดพลาด

    

server = Flask(__name__)
# Initializing the Dash app with Bootstrap
app = dash.Dash(__name__, server=server,external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
# สร้างแอป Dash

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: #f3f6fd; /* สีพื้นหลังของหน้าเว็บ */
                font-family: 'Verdana', sans-serif;
            }
            .content-box {
                background-color: #ffffff; /* สีพื้นหลังของกล่อง */
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                margin: 15px 0;
            }
            label, h1, h3, button {
                font-family: 'Verdana', sans-serif';
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Function to connect to SQLite database
def fetch_data():
    conn = sqlite3.connect('user_data.db')
    df = pd.read_sql_query("SELECT * FROM userdata", conn)
    conn.close()
    
    return df

# Function to insert data into SQLite database
def insert_data(first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    try:
        # ใช้ datetime.now() เพื่อให้ได้ค่า timestamp ปัจจุบัน
        custom_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT INTO userdata (first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type, custom_timestamp))
        conn.commit()
    except Exception as e:
        print(f"Error inserting data: {e}")
    finally:
        conn.close()

def get_first_names():
    df = fetch_data()  # ดึงข้อมูลจากฐานข้อมูล
    return list(df['first_name'].unique())  # ดึงชื่อที่ไม่ซ้ำกัน

def get_last_names():
    df = fetch_data()  # ดึงข้อมูลจากฐานข้อมูล
    return list(df['last_name'].unique())  # ดึงนามสกุลที่ไม่ซ้ำกัน

def get_products():
    df = fetch_data()
    df['product'] = df['product'].replace('-', 'Not using cleanser')
      # ดึงข้อมูลจากฐานข้อมูล
    return list(df['product'].unique())  # ดึงชื่อผลิตภัณฑ์ที่ไม่ซ้ำกัน



app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    
    dcc.Store(id='front-image-store'),  # สำหรับเก็บภาพหน้าตรง
    dcc.Store(id='left-image-store'),   # สำหรับเก็บภาพด้านซ้าย
    dcc.Store(id='right-image-store'),  # สำหรับเก็บภาพด้านขวา

    html.Div(id='page-content')
])

# หน้าแรก
index_page = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Skin Analysis Dashboard", className="text-center text-primary", style={'font-family': 'Arial, sans-serif'}), width=12)),

    # Form กรอกข้อมูล
    dbc.Row([
        dbc.Col(html.Div([
            html.Label('First Name', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
            dcc.Input(id='first-name', type='text', value='', className='form-control')
        ], className='content-box'), width=6),
        dbc.Col(html.Div([
            html.Label('Last Name', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
            dcc.Input(id='last-name', type='text', value='', className='form-control')
        ], className='content-box'), width=6)
    ]),

    dbc.Row([
        dbc.Col(html.Div([
            html.Label('Gender', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
            dcc.Dropdown(
                id='gender',
                options=[
                    {'label': 'Male', 'value': 'M'},
                    {'label': 'Female', 'value': 'F'}
                ],
                value='',
                className='form-control'
            )
        ], className='content-box'), width=6),
        dbc.Col(html.Div([
            html.Label('Product Name', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
            dcc.Input(id='product-name', type='text', value='', className='form-control')
        ], className='content-box'), width=6)
    ]),

    # Capture images from camera for three views
    dbc.Row(html.Label('Capture Images from Camera', className="text-left text-info", style={'font-family': 'Arial, sans-serif', 'font-size': '32px'})),
    dbc.Row([
        # ปรับขนาดของ img ที่แสดงผล
        dbc.Col(html.Img(id='camera_feed', src="/video_feed", style={'width': '60%', 'height': 'auto', 'border': '2px solid #007bff'}), width=12)
    ]),
    dbc.Row([
        dbc.Col(dbc.Button('Capture 3 Views', id='capture_btn', n_clicks=0, color='primary', className='mt-2', style={'font-family': 'Verdana, sans-serif'}), width=12)
    ]),

    # แถวสำหรับแสดงชื่อหัวข้อ
    dbc.Row([
        dbc.Col(html.H3("Captured Images", className="text-center text-info", style={'font-family': 'Verdana, sans-serif'}), width=12)
    ]),

    # แถวสำหรับแสดงภาพที่จับได้
    dbc.Row([
    dbc.Col(html.Div([
        html.Img(id='front-image', src='', style={'width': '100%', 'height': 'auto', 'border': '2px solid #007bff'}),
        html.P('front', style={'text-align': 'center', 'font-family': 'Verdana, sans-serif'})
    ], className='content-box'), width=4),

    dbc.Col(html.Div([
        html.Img(id='left-image', src='', style={'width': '100%', 'height': 'auto', 'border': '2px solid #007bff'}),
        html.P('left', style={'text-align': 'center', 'font-family': 'Verdana, sans-serif'})
    ], className='content-box'), width=4),

    dbc.Col(html.Div([
        html.Img(id='right-image', src='', style={'width': '100%', 'height': 'auto', 'border': '2px solid #007bff'}),
        html.P('right', style={'text-align': 'center', 'font-family': 'Verdana, sans-serif'})
    ], className='content-box'), width=4)
    ]),

    html.Div(id='save_status', className='mt-2'),
    html.Div(id='image_status', className='mt-2', style={'fontWeight': 'bold'}),
    dcc.Interval(id='interval-component', interval=5000, n_intervals=0),  # รีเฟรชทุก 5000 มิลลิวินาที

    # ปุ่ม Reset Images
    dbc.Row(dbc.Col(html.Div([
        dbc.Button('Reset Images', id='reset-images-btn', n_clicks=0, color='danger', className='mt-2', style={'font-family': 'Verdana, sans-serif'}),
        dbc.Button('Confirm Save Data', id='confirm-save-btn', n_clicks=0, color='success', className='mt-2', style={'font-family': 'Verdana, sans-serif', 'margin-left': '10px'})
    ], className='content-box text-center'), width={"size": 6, "offset": 3})),
        

    # Output Result
    dcc.Loading(
        id="loading",
        type="default",
        children=[
            html.Div(id='output')  # แสดงผลลัพธ์ที่ได้จาก callback
        ]
    ),

    html.Br(),

    dcc.Link(dbc.Button("Go to Graph Page", color="secondary", style={'font-family': 'Verdana, sans-serif'}), href='/graphs')
], fluid=True)

# )
@app.callback(
    Output('camera_feed', 'src'),
    Input('interval-component', 'n_intervals')
)
def update_video_src(n):
    return f'/video_feed?{n}'

@server.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    global cap
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    else:
        print("Camera index 0 is not availableo")
        
    while True:
        # print("oooo")
        ret, frame = cap.read()
        if not ret:
            print("beak")
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()

@app.callback(
    [Output('front-image-store', 'data'),
     Output('left-image-store', 'data'),
     Output('right-image-store', 'data'),
     Output('save_status', 'children'),
     Output('image_status', 'children'),
     Output('interval-component', 'n_intervals'),
     Output('capture_btn', 'n_clicks'),
     Output('reset-images-btn', 'n_clicks'),
     Output('front-image', 'src'),  # เพิ่ม Output สำหรับแสดงภาพหน้าตรง
     Output('left-image', 'src'),   # เพิ่ม Output สำหรับแสดงภาพด้านซ้าย
     Output('right-image', 'src')],
    [Input('reset-images-btn', 'n_clicks'),
     Input('capture_btn', 'n_clicks')],
     State('interval-component', 'n_intervals'),
    prevent_initial_call=True
)
def update_images(reset_clicks, capture_clicks,n_intervals):
    global captured_images, cap
    
    # Reset images if reset button is clicked
    if reset_clicks and reset_clicks > 0:
        captured_images = [None, None, None] # Reset captured images
        if not cap.isOpened():
            # cap = cv2.VideoCapture(0)
            print("Camera is available")
        else:
            print("Camera is not available")  # Re-open the camera
        return None, None, None, "Images have been reset.", "",1,0,0,'','',''

    # Capture images based on button clicks
    if capture_clicks and 1 <= capture_clicks <= 3:
        image_index = capture_clicks - 1
        ret, frame = cap.read()
        
        if not ret:
            return dash.no_update, dash.no_update, dash.no_update, "Failed to capture image.", "",dash.no_update,dash.no_update,dash.no_update,dash.no_update,dash.no_update,dash.no_update
        
        _, buffer = cv2.imencode('.jpg', frame)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        image_src = f'data:image/jpeg;base64,{image_base64}'
        
        # Store the captured image based on the index
        captured_images[image_index] = image_src
        
        # Check if all 3 images have been captured
        if all(captured_images):
            cap.release()  # Close the camera after all images are captured
            # cv2.destroyAllWindows()
            status_message = "All images captured!"
        else:
            status_message = f"Captured Image {capture_clicks}."
        
        # Update the stores with the captured images
        return captured_images[0], captured_images[1], captured_images[2], dash.no_update, status_message,dash.no_update,dash.no_update,dash.no_update,captured_images[0], captured_images[1], captured_images[2]
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update,dash.no_update,dash.no_update,dash.no_update,dash.no_update,dash.no_update,dash.no_update

def handle_image_update(reset_clicks, capture_clicks):
    return update_images(reset_clicks, capture_clicks)


# หน้าแสดงกราฟ
user_selection = dbc.Row([
    dbc.Col(html.Div([
        html.Label('First Name', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
        dcc.Dropdown(
            id='first-name-dropdown',
            options=[{'label': name, 'value': name} for name in get_first_names()],
            placeholder="Select First Name",
            className='form-control'
        )
    ], className='content-box'), width=4),

    dbc.Col(html.Div([
        html.Label('Last Name', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
        dcc.Dropdown(
            id='last-name-dropdown',
            options=[{'label': name, 'value': name} for name in get_last_names()],
            placeholder="Select Last Name",
            className='form-control'
        )
    ], className='content-box'), width=4),

    dbc.Col(html.Div([
        html.Label('Product', style={'font-family': 'Verdana, sans-serif', 'font-size': '16px'}),
        dcc.Dropdown(
            id='product-dropdown',
            options=[{'label': product, 'value': product} for product in get_products()],
            placeholder="Select Product",
            className='form-control'
        )
    ], className='content-box'), width=4)
])




graphs_page = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Skin Health Visualizer", className="text-center text-primary",style={'font-family': 'Arial, sans-serif'}), width=12)),
    
    # เพิ่มช่องเลือกผู้ใช้
    user_selection,

    # กราฟแท่ง
    dbc.Row(dbc.Col(dcc.Graph(id='acne-wrinkle-graph'), width=12)),
    
    # กราฟวงกลม
    dbc.Row(dbc.Col(dcc.Graph(id='acne-pie-graph'), width=12)),
    
    # กราฟแนวโน้ม
    dbc.Row(dbc.Col(dcc.Graph(id='acne-trend-graph'), width=12)),
    
    # กราฟฮิสโตแกรม
    dbc.Row(dbc.Col(dcc.Graph(id='acne-histogram'), width=12)),

    dbc.Row(dbc.Col(dcc.Graph(id='acne-product-graph'), width=12)),

    dbc.Row(dbc.Col(dcc.Graph(id='acne-gender-graph'), width=12)),

    dbc.Row(dbc.Col(dcc.Graph(id='acne-skin-graph'), width=12)),

    
    dcc.Interval(
        id='interval-component',
        interval=60 * 1000,  # อัปเดตทุก 60 วินาที
        n_intervals=0
    ),
    
    html.Br(),
    
    dcc.Link(dbc.Button("Back to Home", color="secondary"), href='/')
], fluid=True)
@app.callback(
    Output('first-name-dropdown', 'options'),
    Output('last-name-dropdown', 'options'),
    Output('product-dropdown', 'options'),
    Input('interval-component', 'n_intervals')
)
def update_dropdowns(n):
    # ดึงข้อมูลใหม่จากฐานข้อมูล
    first_names = [{'label': name, 'value': name} for name in get_first_names()]
    last_names = [{'label': name, 'value': name} for name in get_last_names()]
    products = [{'label': product, 'value': product} for product in get_products()]
    
    return first_names, last_names, products

# Callback to update results
@app.callback(
    Output('output', 'children'),
    Input('confirm-save-btn', 'n_clicks'),
    State('first-name', 'value'),
    State('last-name', 'value'),
    State('gender', 'value'),
    State('product-name', 'value'),
    State('front-image-store', 'data'),  # ดึงข้อมูลภาพหน้าตรง
    State('left-image-store', 'data'),   # ดึงข้อมูลภาพด้านซ้าย
    State('right-image-store', 'data'),  # ดึงข้อมูลภาพด้านขวา
    prevent_initial_call=True
)

def update_output(n_clicks, first_name, last_name, gender, product, front_image_content, left_image_content, right_image_content):
    if n_clicks > 0:

        try:
            # Check for missing fields
            if not all([first_name, last_name, gender, product, front_image_content, left_image_content, right_image_content]):
                return "Please fill out all fields and upload all images."
            with sqlite3.connect('user_data.db') as conn:
                c = conn.cursor()
                c.execute("SELECT skin_type FROM userdata WHERE first_name=? AND last_name=?", (first_name, last_name))
                result = c.fetchone()
            activate = 0
            if result:  # If data exists
                skin_type = result[0]
                activate = 1

            # Process images
            class_counts = {'Acne': 0, 'wrinkles': 0, 'Dark circles': 0, 'blackheads': 0, 'whiteheads': 0}
            
            for image_content in [front_image_content, left_image_content, right_image_content]:
                if image_content is not None:
                    content_type, content_string = image_content.split(',')
                    decoded = base64.b64decode(content_string)
                    img = Image.open(io.BytesIO(decoded))
                
                    # Save image for processing
                    image_path = 'data/uploaded_image.jpg'
                    img.save(image_path)
                    try:
                        left, top, right, bottom = infer_image_with_facedetect(image_path)
                        cropped_image = img.crop((left, top, right, bottom))
                        cropped_image.save(image_path)
                    except:
                        img.save(image_path)
                    
                    # Call model to get counts
                    temp_counts = infer_image_with_sdk(image_path)
                    for key in class_counts:
                        class_counts[key] += temp_counts.get(key, 0)

            # Call model to classify skin type
            if activate == 0:
                skin_type = infer_image_with_transformers(image_path)
            if class_counts['Dark circles'] > 2:
                class_counts['Dark circles'] = 2
            # Generate summary message
            result_message = (f"Data Summary for {first_name} {last_name}:<br>"
                            f"Skin Type: {skin_type}<br>"
                            f"Total Acne Count: {class_counts['Acne']}<br>"
                            f"Total Wrinkle Count: {class_counts['wrinkles']}<br>"
                            f"Total Dark Circle Count: {class_counts['Dark circles']}<br>"
                            f"Total Blackhead Count: {class_counts['blackheads']}<br>"
                            f"Total Whitehead Count: {class_counts['whiteheads']}<br>")

            # Insert data into database
            if gender == 'M':
                gender = 'Male'
            else:
                gender = 'Female'
            insert_data(first_name, last_name, gender, product, 
                        class_counts['Acne'], class_counts['wrinkles'],
                        class_counts['Dark circles'], class_counts['blackheads'],
                        class_counts['whiteheads'], skin_type)
            
            return result_message
        except Exception as e:
            return f"An error occurred: {e}"

    return ''

@app.callback(
    Output('acne-wrinkle-graph', 'figure'),
    Output('acne-pie-graph', 'figure'),
    Output('acne-trend-graph', 'figure'),
    Output('acne-histogram', 'figure'),
    Output('acne-product-graph', 'figure'),
    Output('acne-gender-graph', 'figure'),
    Output('acne-skin-graph', 'figure'),

        # เพิ่ม Output สำหรับกราฟที่ 5
    Input('first-name-dropdown', 'value'),
    Input('last-name-dropdown', 'value'),
    Input('product-dropdown', 'value'),
    Input('interval-component', 'n_intervals')
)
def update_graphs(first_name, last_name, product, n):
    # ดึงข้อมูลใหม่จากฐานข้อมูล
    df = fetch_data()  # ฟังก์ชันนี้จะคืนค่าข้อมูลจากฐานข้อมูล

    # เรียงลำดับข้อมูลตาม timestamp
    df = df.sort_values(by='timestamp', ascending=True)
    df['product'] = df['product'].replace('-', 'Not using cleanser')

    # กรองข้อมูลตามที่เลือกใน Dropdown
    if first_name:
        df = df[df['first_name'] == first_name]
    if last_name:
        df = df[df['last_name'] == last_name]
    if product:
        df = df[df['product'] == product]

    if df.empty:
        return {}, {}, {}, {}, {},{},{}

    # สร้างกราฟแท่งสำหรับเงื่อนไขผิวหนัง
    fig1 = go.Figure()
    colors = ['#264653', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51']  # กำหนดชุดสีที่สวยงาม
    
    # ใช้คอลัมน์ที่มีอยู่ในการสร้างกราฟ
    for i, condition in enumerate(['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']):
        fig1.add_trace(go.Bar(
            x=df['first_name'],  
            y=df[condition],
            name=condition.replace('_', ' ').title(),
            text=df[condition],
            textposition='inside',
            marker=dict(color=colors[i])
        ))

    fig1.update_layout(
        title='Skin Conditions Count by First Name',
        xaxis_title='First Name',
        yaxis_title='Count',
        barmode='group',  # Ensure bars are grouped for each first name
        template='plotly_white',
        font=dict(size=14),  # Adjust font size
        showlegend=True,
        legend=dict(title='Conditions'),
        xaxis_tickangle=-45,  # Rotate x-axis labels
        margin=dict(l=40, r=40, t=40, b=80),  # Add space for x-axis labels
        yaxis=dict(showgrid=True)  # Show grid lines for easier comparison
    )

    # สร้างกราฟวงกลมแสดงสัดส่วนของปัญหาผิว
    total_counts = df[['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']].sum()
    
    fig2 = px.pie(
        values=total_counts, 
        names=total_counts.index, 
        title='Distribution of Skin Conditions',
        color_discrete_sequence=['#264653', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51']  # ตัวอย่างโค้ดสี
        )
    fig2.update_traces(textinfo='percent+label')
    fig2.update_layout(template='plotly_white')

    # สร้างกราฟแนวโน้ม
    fig3 = make_subplots(
        rows=5, cols=1, shared_xaxes=True, 
        subplot_titles=['Acne Count', 'Wrinkle Count', 'Dark Circle Count', 'Blackhead Count', 'Whitehead Count'],
        vertical_spacing=0.05
    )

    
    line_styles = ['dash', 'dot', 'solid', 'dashdot', 'longdash']
    for i, condition in enumerate(['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']):
        fig3.add_trace(go.Scatter(
            x=df['timestamp'],  
            y=df[condition],
            mode='lines+markers',
            name=condition.replace('_', ' ').title(),
            line=dict(dash=line_styles[i], width=2, color=colors[i]),  # เพิ่มสี
            marker=dict(size=7)
        ), row=i+1, col=1)

    fig3.update_layout(
        height=1000,
        title='Trends of Skin Conditions Over Time',
        template='plotly_white'
    )
    fig3.update_xaxes(title_text='Timestamp', row=5, col=1)

    # สร้างกราฟฮิสโตแกรม
    fig4 = px.histogram(
        df, 
        x='acne_count', 
        nbins=20, 
        title='Distribution of Acne Count',
        color_discrete_sequence=['#264653']
    )

    fig4.update_traces(
        opacity=0.75,
        marker=dict(line=dict(width=1, color='DarkSlateGrey'))
    )
    fig4.update_layout(
        xaxis_title='Acne Count',
        yaxis_title='Frequency',
        template='plotly_white'
    )

    # สร้างกราฟแท่งสำหรับการแสดงผลเงื่อนไขผิวหนังตามผลิตภัณฑ์
    fig5 = go.Figure()  
    product_df = df.groupby('product')[['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']].sum().reset_index()
    for i, condition in enumerate(['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']):
        fig5.add_trace(go.Bar(
            x=product_df['product'], 
            y=product_df[condition], 
            name=condition.replace('_', ' ').title(),
            text=product_df[condition],
            textposition='auto',  # Change text position to auto
            marker_color=colors[i]  # Assign a color to each condition
        ))

    fig5.update_traces(width=0.4)  # ลดความกว้างของแท่งกราฟเพื่อให้ดูชัดเจนขึ้น
    fig5.update_layout(
        title='Skin Conditions by Product',
        xaxis_title='Product',
        yaxis_title='Count',
        barmode='stack',
        template='plotly_white',
        font=dict(size=14),  # ปรับขนาดฟอนต์
        showlegend=True,
        legend=dict(title='Skin Conditions'),
        xaxis_tickangle=-45,
        margin=dict(l=40, r=40, t=40, b=80),
        bargap=0.3,  # เพิ่มช่องว่างระหว่างแท่งกราฟ
        yaxis=dict(showgrid=True),
        height=1000
    )

    # สร้างกราฟเปรียบเทียบเงื่อนไขผิวหนังระหว่างเพศ
    fig6 = go.Figure()
    gender_counts = df.groupby('gender')[['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']].sum().reset_index()

    # สร้างชุดสีใหม่เพื่อหลีกเลี่ยง IndexError
    for i, condition in enumerate(['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']):
        fig6.add_trace(go.Bar(
            x=gender_counts['gender'],
            y=gender_counts[condition],
            name=condition.replace('_', ' ').title(),
            text=gender_counts[condition],
            textposition='auto',
            marker_color=colors[i]  # ใช้สีจากชุดสีใหม่
        ))

    # ตั้งค่ากราฟ
    fig6.update_layout(
        title='Comparison of Skin Conditions Between Genders',
        xaxis_title='Gender',
        yaxis_title='Count',
        barmode='group',  # แบบกลุ่มเพื่อเปรียบเทียบ
        template='plotly_white',
        font=dict(size=12),  # ปรับขนาดฟอนต์
        showlegend=True,  # แสดงตำนาน
        legend=dict(title='Skin Conditions'),  # ชื่อตำนาน
        margin=dict(l=40, r=40, t=40, b=40),  # เพิ่มขอบเขตให้กับการจัดวาง
        xaxis=dict(showgrid=True)  # แสดงเส้นกริดเพื่อความอ่านง่าย
    )

    # สร้างกราฟเปรียบเทียบเงื่อนไขผิวหนังตามประเภทผิว
    fig7 = go.Figure()
    skin_counts = df.groupby('skin_type')[['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']].sum().reset_index()
    
    # สร้างชุดสีใหม่เพื่อหลีกเลี่ยง IndexError
    for i, condition in enumerate(['acne_count', 'wrinkle_count', 'darkcircle_count', 'blackhead_count', 'whitehead_count']):
        fig7.add_trace(go.Bar(
            x=skin_counts['skin_type'],
            y=skin_counts[condition],
            name=condition.replace('_', ' ').title(),
            text=skin_counts[condition],
            textposition='auto',
            marker_color=colors[i]  # ใช้สีจากชุดสีใหม่
        ))

    # ตั้งค่ากราฟ
    fig7.update_layout(
        title='Comparison of Skin Conditions by Skin Type',
        xaxis_title='Skin Type',
        yaxis_title='Count',
        barmode='group',  # แบบกลุ่มเพื่อเปรียบเทียบ
        template='plotly_white',
        font=dict(size=12),  # ปรับขนาดฟอนต์
        showlegend=True,  # แสดงตำนาน
        legend=dict(title='Skin Conditions'),  # ชื่อตำนาน
        margin=dict(l=40, r=40, t=40, b=40),  # เพิ่มขอบเขตให้กับการจัดวาง
        xaxis=dict(showgrid=True)  # แสดงเส้นกริดเพื่อความอ่านง่าย
    )

    return fig1, fig2, fig3, fig4, fig5, fig6, fig7

# Routing for pages
@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/graphs':
        return graphs_page
    else:
        return index_page



# ฟังก์ชันอ่านไฟล์ CSV
def load_csv_data(filepath):
    df = pd.read_csv(filepath)
    df.columns = ['Timestamp', 'Gender', 'Date', 'Cleanser Product', 'Front View', 'Left Side View', 'Right Side View', 'First Name', 'Last Name']
    return df


def download_image(image_url):
    try:
        # เปลี่ยนลิงก์จาก Google Drive เป็นลิงก์ดาวน์โหลด
        if "drive.google.com" in image_url:
            # ดึง file_id จากลิงก์
            file_id = image_url.split('=')[1]
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        else:
            print(f"Invalid Google Drive URL format: {image_url}")
            return None

        response = requests.get(download_url)
        print(f"Downloaded content size (bytes): {len(response.content)}")

        img = Image.open(BytesIO(response.content))
        print(f"Image format: {img.format}")
        print(f"Image size: {img.size}")
        print(f"Image mode: {img.mode}")

        img.verify()  # ตรวจสอบว่าเป็นรูปภาพที่ถูกต้อง
        img = Image.open(BytesIO(response.content))  # เปิดภาพใหม่หลังจาก verify สำเร็จ

    
        return img

    except requests.exceptions.RequestException as e:
        print(f"Failed to download image from {image_url}: {e}")
        return None
    except (IOError, SyntaxError) as e:
        print(f"Image file is not valid: {e}")
        return None







# ฟังก์ชันประมวลผลภาพผ่านโมเดล
def process_images(front_url, left_url, right_url,first_name,last_name):
    # ดึงภาพจาก URL
    front_image = download_image(front_url)
    left_image = download_image(left_url)
    right_image = download_image(right_url)

    # ถ้าไม่สามารถดาวน์โหลดภาพได้ จะหยุดการประมวลผล
    if front_image is None or left_image is None or right_image is None:
        print("Image download failed or invalid. Skipping processing.")
        return None, None
    # ตรวจสอบว่าเป็นภาพก่อนทำงาน
    if not all(isinstance(img, Image.Image) for img in [front_image, left_image, right_image]):
        print("Invalid image object detected.")
        return None, None
    class_counts = {'Acne': 0, 'wrinkles': 0, 'Dark circles': 0, 'blackheads': 0, 'whiteheads': 0}
    
    try:
        conn = sqlite3.connect('user_data.db')
        c = conn.cursor()
        c.execute("SELECT skin_type FROM userdata WHERE first_name=? AND last_name=?", (first_name, last_name))
        result = c.fetchone()
        conn.close()
        activate = 0
        if result:  # If data exists
            skin_type = result[0]
            activate = 1
        # ใช้ inferencing SDK กับภาพทั้งสาม
        for img in [front_image, left_image, right_image]:
            # ตรวจสอบว่าภาพเป็น PIL Image
            if isinstance(img, bytes):
                img = Image.open(io.BytesIO(img))  # แปลงเป็น PIL Image หากเป็น bytes
            # Save image for processing
            image_path = 'data/csv_image.jpg'
            img.save(image_path)
            img = correct_image_orientation(img)
            img.save(image_path)
            try:
                left, top, right, bottom = infer_image_with_facedetect(image_path)
                cropped_image = img.crop((left, top, right, bottom))
                cropped_image.save(image_path)
            except:
                img.save(image_path)
            temp_counts = infer_image_with_sdk(image_path)  # ใช้ PIL Image ตรงๆ
            
            if temp_counts is None:
                print("Inference failed for one of the images.")
                return None, None

            for key in class_counts:
                class_counts[key] += temp_counts.get(key, 0)

        # คำนวณชนิดผิว
        # Call model to classify skin type
            if activate == 0:
                skin_type = infer_image_with_transformers(image_path)
        # skin_type = infer_image_with_transformers(image_path)  # ใช้ PIL Image ตรงๆ
        
        if skin_type is None:
            print("Skin type inference failed.")
            return None, None

    except Exception as e:
        print(f"Error in image processing: {e}")
        return None, None

    return class_counts, skin_type

def format_date(date_str,on_date):
    # แปลงวันที่จากรูปแบบ "30/9/2024, 21:02:15" เป็น "2024-09-30 21:02:15"
    try:
        # ใช้ strptime เพื่อแปลงวันที่
        original_date = datetime.strptime(date_str.split(', ')[0], '%d/%m/%Y')  # วันที่
        on_date = datetime.strptime(on_date, '%d/%m/%Y')  # แปลง on_date
        
        # แทนที่วันที่ใน original_date ด้วยวันที่ใน on_date
        new_date = original_date.replace(year=on_date.year, month=on_date.month, day=on_date.day)

        # แยกเวลาออกจาก Timestamp
        time_part = date_str.split(', ')[1]  # เวลา
        hour, minute, second = map(int, time_part.split(':'))  # แยกและแปลงเวลาเป็นจำนวนเต็ม

        # สร้าง datetime ใหม่พร้อมด้วยเวลา
        new_date_time = new_date.replace(hour=hour, minute=minute, second=second)

        # แปลงกลับเป็น string ในรูปแบบที่ต้องการ
        formatted_date = new_date_time.strftime('%Y-%m-%d %H:%M:%S')
        return formatted_date
    except ValueError as e:
        print(f"Date format error: {e}")
        return None  # หรือ return ค่าที่คุณต้องการในกรณีที่เกิดข้อผิดพลาด


# ฟังก์ชันเช็คว่ามีข้อมูลในฐานข้อมูลแล้วหรือไม่
def check_duplicate_in_db(first_name, last_name, date):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''SELECT COUNT(*) FROM userdata WHERE first_name = ? AND last_name = ? AND timestamp = ?''', 
                  (first_name, last_name, date))
        result = c.fetchone()[0]
        conn.close()
        return result > 0  # ถ้ามี record ในฐานข้อมูลอยู่แล้ว จะ return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return True  # ถ้าหากมีข้อผิดพลาด ให้ถือว่ามีข้อมูลอยู่แล้ว

# ฟังก์ชันเพิ่มข้อมูลลงใน SQLite
def insert_data_to_db(first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type, date):
    if not check_duplicate_in_db(first_name, last_name, date):
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO userdata (first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (first_name, last_name, gender, product, acne_count, wrinkle_count, darkcircle_count, blackhead_count, whitehead_count, skin_type,date))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Failed to insert data: {e}")
    else:
        print(f"Data for {first_name} {last_name} on {date} already exists in the database. Skipping...")
# ฟังก์ชันเชื่อมต่อฐานข้อมูลด้วย check_same_thread=False
def get_db_connection():
    return sqlite3.connect('user_data.db', check_same_thread=False)
# ฟังก์ชันประมวลผลและเพิ่มข้อมูล
def process_data(df):
    try:
        # ประมวลผลข้อมูลในแต่ละแถวของ CSV
        for index, row in df.iterrows():
            first_name = row['First Name']
            last_name = row['Last Name']
            gender = row['Gender']
            product = row['Cleanser Product']
            date = row['Timestamp']
            on_date = row['Date']
            date = format_date(date,on_date)  # ใช้คอลัมน์ Date ในการเช็คข้อมูล

            # ตรวจสอบ URL รูปภาพไม่ว่างเปล่า
            if pd.isnull(row['Front View']) or pd.isnull(row['Left Side View']) or pd.isnull(row['Right Side View']):
                print(f"Missing image URLs for {first_name} {last_name}. Skipping...")
                continue

            # เช็คข้อมูลซ้ำในฐานข้อมูลก่อนประมวลผล
            if not check_duplicate_in_db(first_name, last_name, date):
                # ดึงภาพและประมวลผลด้วยโมเดล
                class_counts, skin_type = process_images(row['Front View'], row['Left Side View'], row['Right Side View'],row['First Name'],row['Last Name'])
                if class_counts['Dark circles'] > 2:
                    class_counts['Dark circles'] = 2
                if class_counts and skin_type:
                    # เพิ่มข้อมูลลงฐานข้อมูล
                    insert_data_to_db(first_name, last_name, gender, product, 
                                      class_counts['Acne'], class_counts['wrinkles'], 
                                      class_counts['Dark circles'], class_counts['blackheads'], 
                                      class_counts['whiteheads'], skin_type, date)
                else:
                    print(f"Skipping data for {first_name} {last_name} due to image processing failure.")
            else:
                print(f"Data for {first_name} {last_name} on {date} already exists. Skipping...")

        print("Data processed and saved successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")
# โหลดข้อมูลจาก CSV และประมวลผล
csv_filepath = 'src\\spark\\assets\\data\\sheet.csv'

def run_process_data_in_thread(filepath):
    df = load_csv_data(filepath)
    process_data(df)

process_thread = threading.Thread(target=run_process_data_in_thread, args=(csv_filepath,))

# เริ่มเธรด
process_thread.start()


# Running the server
if __name__ == '__main__':
    app.run_server(debug=True)