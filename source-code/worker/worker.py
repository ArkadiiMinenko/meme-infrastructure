import pika
import json
import os
import time
import boto3
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
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

def ensure_bucket_policy():
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    except Exception as e:
        print(f"Bucket creation warning: {e}")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{BUCKET_NAME}/*"]
            }
        ]
    }
    
    try:
        s3.put_bucket_policy(Bucket=BUCKET_NAME, Policy=json.dumps(policy))
    except Exception as e:
        print(f"Error setting policy: {e}")

def get_best_font(size):
    if os.path.exists("Impact.ttf"):
        return ImageFont.truetype("Impact.ttf", size)
    linux_fonts = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    for font_path in linux_fonts:
        if os.path.exists(font_path):
            try: return ImageFont.truetype(font_path, size)
            except: continue
    return ImageFont.load_default()

def wrap_text(text, font, max_width):
    lines = []
    if max_width <= 0:
        return text
        
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        words = paragraph.split()
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
            
    return '\n'.join(lines)

def hex_to_rgba(hex_color, opacity=100):
    if not hex_color: hex_color = "#ffffff"
    try:
        rgb = ImageColor.getrgb(hex_color)
        alpha = int((opacity / 100) * 255)
        return rgb + (alpha,)
    except:
        return (255, 255, 255, 255)

def draw_text(img, text, font, x_pos, y_pos, color, opacity, border_hex, border_enabled):
    draw = ImageDraw.Draw(img)
    img_width = img.width
    max_text_width = img_width - x_pos - 20
    
    if max_text_width < 100:
        max_text_width = img_width - 40
        x_pos = 20

    final_text = wrap_text(text, font, max_text_width)

    if border_enabled:
        border_rgba = hex_to_rgba(border_hex, opacity)
        for adj_x in range(-2, 3):
            for adj_y in range(-2, 3):
                draw.multiline_text((x_pos+adj_x, y_pos+adj_y), final_text, font=font, fill=border_rgba, align="center")
    
    fill_color = hex_to_rgba(color, opacity)
    draw.multiline_text((x_pos, y_pos), final_text, font=font, fill=fill_color, align="center")

def process_image(task_id, template_url, text_lines, border_enabled):
    print(f"Processing: {task_id}")
    try:
        response = requests.get(template_url, timeout=10)
        response.raise_for_status()
        original_img = Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception as e:
        print(f"Error downloading template: {e}")
        return None

    for line in text_lines:
        font = get_best_font(line.get('size', 50))
        
        draw_text(
            original_img, 
            line.get('text', '').upper(),
            font, 
            line.get('x_pos', 0), 
            line.get('y_pos', 10), 
            line.get('color', '#fff'), 
            line.get('opacity', 100), 
            line.get('border_color_hex', '#000'), 
            border_enabled
        )
    
    bg = Image.new("RGB", original_img.size, (255, 255, 255))
    bg.paste(original_img, (0, 0), original_img)
    
    img_byte_arr = BytesIO()
    bg.save(img_byte_arr, format='JPEG', quality=95, subsampling=0)
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
        update_db(task_id, "Processing")
        url = process_image(task_id, data.get('template_url'), data.get('text_lines', []), data.get('text_border', True))
        if url:
            update_db(task_id, "Done", url)
            print(f"DONE: {task_id}")
        else:
            update_db(task_id, "Failed")
            print(f"FAILED: {task_id}")
    except Exception as e:
        print(f"Error processing: {e}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    time.sleep(10)
    
    try:
        ensure_bucket_policy()
    except Exception as e:
        print(f"Init Error: {e}")

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME)
            print("Waiting for tasks...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            channel.start_consuming()
        except Exception as e:
            print(f"Connection lost: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()