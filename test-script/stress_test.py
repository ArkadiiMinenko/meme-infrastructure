import requests
import random
import concurrent.futures
import time

LOCAL_API_URL = "http://api.192.168.0.220.nip.io"
EXTERNAL_API_URL = "https://official-joke-api.appspot.com/random_joke"

CONCURRENT_USERS = 13
TEST_DURATION = 600

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
    setup_text, punchline_text = get_random_content()
    template = random.choice(templates)

    layers = [
        {"text": setup_text, "size": random.randint(40, 60), "color": random.choice(COLORS), "opacity": 100, "x_pos": random.randint(10, 50), "y_pos": 20},
        {"text": punchline_text, "size": random.randint(45, 70), "color": random.choice(COLORS), "opacity": 100, "x_pos": random.randint(10, 50), "y_pos": 350}
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
            return f"OK ({time.time() - start:.3f}s)"
        return f"Error {res.status_code}"
    except Exception as e:
        return f"Fail: {e}"

def worker_thread(templates, stop_time):
    results = []
    while time.time() < stop_time:
        res = single_user_action(templates)
        results.append(res)
        print(f"[{time.strftime('%H:%M:%S')}] {res}")
    return results

def main():
    print(f"Starting test: {CONCURRENT_USERS} threads for {TEST_DURATION} seconds.")
    templates = get_templates()
    
    if not templates:
        print("API unreachable.")
        return

    stop_time = time.time() + TEST_DURATION
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [executor.submit(worker_thread, templates, stop_time) for _ in range(CONCURRENT_USERS)]
        all_results = []
        for future in concurrent.futures.as_completed(futures):
            all_results.extend(future.result())

    duration = time.time() - start_time
    total_req = len(all_results)
    print(f"\nTotal duration: {duration:.2f}s")
    print(f"Requests: {total_req}")
    print(f"Average RPS: {total_req / duration:.2f}")

if __name__ == "__main__":
    main()