import pika
import json
import os
import time
import boto3
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv('../.env')

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT"))
QUEUE_NAME = "meme_tasks"

PG_USER = os.getenv("POSTGRES_USER")
PG_PASS = os.getenv("POSTGRES_PASSWORD")
PG_HOST = os.getenv("POSTGRES_HOST")
PG_DB = os.getenv("POSTGRES_DB")
DB_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:5432/{PG_DB}"

MINIO_ENDPOINT_INTERNAL = os.getenv("MINIO_INTERNAL_ENDPOINT")
MINIO_ENDPOINT_EXTERNAL = os.getenv("MINIO_EXTERNAL_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
BUCKET_NAME = os.getenv("MINIO_BUCKET")

TEMPLATES = {
    "doge": "https://i.imgflip.com/4t0m5.jpg",
    "disaster": "https://i.imgflip.com/23ls.jpg",
    "drake": "https://i.imgflip.com/30b1gx.jpg",
    "wonka": "https://i.imgflip.com/1bip.jpg"
}

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class MemeTask(Base):
    __tablename__ = "memes"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="Pending")
    image_url = Column(String, nullable=True)
    meta = Column(JSON, nullable=True)

s3 = boto3.client('s3',
                  endpoint_url=MINIO_ENDPOINT_INTERNAL,
                  aws_access_key_id=MINIO_ACCESS_KEY,
                  aws_secret_access_key=MINIO_SECRET_KEY)

def update_db(task_id, status, url=None):
    db = SessionLocal()
    try:
        task = db.query(MemeTask).filter(MemeTask.task_id == task_id).first()
        if task:
            task.status = status
            if url:
                task.image_url = url
            db.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        db.close()

def get_font(size):
    try:
        return ImageFont.truetype("font.ttf", size)
    except IOError:
        print("WARNING: font.ttf not found")
        return ImageFont.load_default()

def draw_text_centered(draw, image_size, text, font, y_pos, color, border):
    img_width, img_height = image_size
    
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = draw.textsize(text, font=font)

    x = (img_width - text_width) / 2
    
    if border:
        outline_range = 2
        for adj_x in range(-outline_range, outline_range+1):
            for adj_y in range(-outline_range, outline_range+1):
                draw.text((x+adj_x, y_pos+adj_y), text, font=font, fill="black")

    draw.text((x, y_pos), text, font=font, fill=color)

def process_image(task_id, template_name, text_lines, border):
    print(f"Processing: {task_id} | Template: {template_name}")
    
    if template_name in TEMPLATES:
        try:
            url = TEMPLATES[template_name]
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            print(f"Error downloading template: {e}")
            img = Image.new('RGB', (600, 600), color=(73, 109, 137))
    else:
        img = Image.new('RGB', (600, 600), color=(73, 109, 137))

    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    for line in text_lines:
        text = line.get('text', '')
        size = line.get('size', 50)
        color = line.get('color', 'white')
        y_pos = line.get('y_pos', 10)
        
        font = get_font(size)
        draw_text_centered(draw, (width, height), text.upper(), font, y_pos, color, border)
    
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    file_name = f"{task_id}.jpg"
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=img_byte_arr, ContentType='image/jpeg')
        return f"{MINIO_ENDPOINT_EXTERNAL}/{BUCKET_NAME}/{file_name}"
    except Exception as e:
        print(f"MinIO Error: {e}")
        return None

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        task_id = data['id']
        template = data.get('template', 'doge')
        text_lines = data.get('text_lines', [])
        text_border = data.get('text_border', True)
        
        update_db(task_id, "Processing")
        
        url = process_image(task_id, template, text_lines, text_border)
        
        if url:
            update_db(task_id, "Done", url)
            print(f"DONE: {task_id}")
        else:
            update_db(task_id, "Failed")
            print(f"FAILED: {task_id}")

    except Exception as e:
        print(f"Error processing message: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    time.sleep(5)
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
            )
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME)
            
            try:
                s3.create_bucket(Bucket=BUCKET_NAME)
            except:
                pass

            print("Waiting for tasks...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            channel.start_consuming()
        except Exception as e:
            print(f"Connection lost: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()