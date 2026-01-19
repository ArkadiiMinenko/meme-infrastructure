import pika
import json
import os
import time
import boto3
from PIL import Image, ImageDraw
from io import BytesIO
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Config
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_NAME = "meme_tasks"
DB_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/memedb")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "memes"

# DB Setup
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class MemeTask(Base):
    __tablename__ = "memes"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    status = Column(String, default="Pending")
    image_url = Column(String, nullable=True)

# MinIO Setup
s3 = boto3.client('s3',
                  endpoint_url=MINIO_ENDPOINT,
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

def process_image(task_id, top, bottom):
    print(f"Processing: {task_id}")
    
    # 1. Create Image (CPU Bound Task)
    img = Image.new('RGB', (800, 600), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.text((50, 50), top, fill=(255, 255, 0))
    d.text((50, 500), bottom, fill=(255, 255, 0))
    
    # Simulate Heavy CPU Load for HPA demo later
    # Calculate something useless just to burn CPU cycles
    val = 0
    for i in range(10000000): 
        val += i

    # 2. Save to Bytes
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    # 3. Upload to MinIO
    file_name = f"{task_id}.jpg"
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=img_byte_arr, ContentType='image/jpeg')
        # In MinIO, default presigned/public URL structure is tricky without setup, 
        # so we just store the path for now.
        return f"{MINIO_ENDPOINT}/{BUCKET_NAME}/{file_name}"
    except Exception as e:
        print(f"MinIO Error: {e}")
        return None

def callback(ch, method, properties, body):
    data = json.loads(body)
    task_id = data['id']
    
    update_db(task_id, "Processing")
    
    url = process_image(task_id, data['top_text'], data['bottom_text'])
    
    if url:
        update_db(task_id, "Done", url)
        print(f"DONE: {task_id}")
    else:
        update_db(task_id, "Failed")
        print(f"FAILED: {task_id}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    time.sleep(15) # Wait for infrastructure

    # Ensure Bucket Exists
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
    except:
        pass

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME)
    
    print("Worker started. Waiting for tasks...")
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    channel.start_consuming()

if __name__ == "__main__":
    main()