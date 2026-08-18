import glob
import requests

slipper_files = sorted(glob.glob('storage/Slippers/*.jpeg') + glob.glob('storage/Slippers/*.jpg'))
print(f"Testing {len(slipper_files)} slippers against live server at http://127.0.0.1:8000:")

for idx, p in enumerate(slipper_files, 1):
    with open(p, 'rb') as f:
        r = requests.post('http://127.0.0.1:8000/api/match', files={'file': f})
    data = r.json()
    cat = data.get('detected_category')
    fw = data.get('is_footwear_detected')
    matches = data.get('matches', [])
    top = f"{matches[0]['design_id']} ({matches[0]['confidence_pct']}%)" if matches else f"NO MATCH ({data.get('message')})"
    print(f"[{idx:02d}] {p:33s} -> Cat: {str(cat):8s} | FW: {str(fw):5s} | Matches: {len(matches)} | Top: {top}")
