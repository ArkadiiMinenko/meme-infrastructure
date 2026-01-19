import requests
import random
import concurrent.futures
import time

LOCAL_API_URL = "http://localhost:8000"
EXTERNAL_API_URL = "https://official-joke-api.appspot.com/random_joke"

TOTAL_REQUESTS = 70
CONCURRENT_USERS = 10

COLORS = ["#ffffff", "#ff0000", "#00ff00", "#0000ff", "#ffff00"]

def get_random_content():
    try:
        response = requests.get(EXTERNAL_API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data["setup"], data["punchline"]
        return "Stress Test", "Load Check"
    except:
        return "Network Error", "Retry"

def get_templates():
    try:
        response = requests.get(f"{LOCAL_API_URL}/templates")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

def single_user_action(templates):
    if not templates:
        return "No templates"

    setup_text, punchline_text = get_random_content()
    template = random.choice(templates)

    layers = [
        {
            "text": setup_text,
            "size": random.randint(40, 60),
            "color": random.choice(COLORS),
            "opacity": 100,
            "border_color_hex": "#000000",
            "x_pos": random.randint(10, 50),
            "y_pos": 20
        },
        {
            "text": punchline_text,
            "size": random.randint(45, 70),
            "color": random.choice(COLORS),
            "opacity": 100,
            "border_color_hex": "#000000",
            "x_pos": random.randint(10, 50),
            "y_pos": 350
        }
    ]

    payload = {
        "template_id": template['id'],
        "text_border": True,
        "text_lines": layers
    }

    try:
        start = time.time()
        res = requests.post(f"{LOCAL_API_URL}/memes", json=payload, timeout=10)
        
        if res.status_code == 200:
            task_id = res.json()['task_id']
            return f"Task {task_id} sent (Time: {time.time() - start:.3f}s)"
        else:
            return f"Error: Status {res.status_code}"
    except Exception as e:
        return f"Request Failed: {e}"

def main():
    print(f"Starting STRESS TEST: {TOTAL_REQUESTS} requests, {CONCURRENT_USERS} threads.")
    templates = get_templates()
    
    if not templates:
        print("API not reachable or no templates found.")
        return

    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [executor.submit(single_user_action, templates) for _ in range(TOTAL_REQUESTS)]
        
        for future in concurrent.futures.as_completed(futures):
            print(future.result())

    duration = time.time() - start_time
    print(f"\nTest Finished in {duration:.2f} seconds.")
    print(f"RPS (Requests Per Second): {TOTAL_REQUESTS / duration:.2f}")

if __name__ == "__main__":
    main()