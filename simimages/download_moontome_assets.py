
import requests
import os
import json

API_URL = "https://csmxbeemtuykowxymjze.supabase.co/rest/v1/MoonstoneModel?select=*%2cAbility(id%2cname%2cenergyCost%2crange%2cpulse%2concePerGame%2concePerTurn%2cdescription%2cmodelId%2cArcaneOutcome(id%2ccardColourRequirement%2ccardValueRequirement%2ccatastropheOutcome%2coutcomeText%2cabilityId))%2cSignatureMove(id%2cname%2cupgradeFor%2chighGuardDamage%2cfallingSwingDamage%2cthrustDamage%2csweepingCutDamage%2crisingAttackDamage%2clowGuardDamage%2cextraText%2cendStepEffect%2cdamageType%2cparryType)%2cModelRelations(id%2cparentModel%2cchildModel%2crelationType%2crelatedName)"
IMG_BASE = "https://moontome.b-cdn.net/"

HEADERS = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzbXhiZWVtdHV5a293eHltanplIiwicm9sZSI6ImFub24iLCJpYXQiOjE2OTQ3OTI1NTYsImV4cCI6MjAxMDM2ODU1Nn0.8Dq_9StXf4cBjQ5fgd57qGqSuSJ_ARw5dWDpKgelxy0",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzbXhiZWVtdHV5a293eHltanplIiwicm9sZSI6ImFub24iLCJpYXQiOjE2OTQ3OTI1NTYsImV4cCI6MjAxMDM2ODU1Nn0.8Dq_9StXf4cBjQ5fgd57qGqSuSJ_ARw5dWDpKgelxy0"
}

session = requests.Session()
session.headers.update(HEADERS)

# Output directories
os.makedirs("characters", exist_ok=True)
os.makedirs("SignatureMoves", exist_ok=True)

def download_file(url, out_path):
    if os.path.exists(out_path):
        return
    r = session.get(url)
    if r.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"Downloaded {url} -> {out_path}")
    else:
        print(f"Failed to download {url} ({r.status_code})")

resp = session.get(API_URL)
data = resp.json()

downloaded_signatures = set()


for char in data:
    name = char.get("name")
    head = char.get("headFileName")
    stat = char.get("statCardFileName")
    sig = char.get("signatureFileName")

    # Make a folder for each character
    if name:
        safe_name = name.replace("/", "_").replace("\\", "_")
        char_dir = os.path.join("characters", safe_name)
        os.makedirs(char_dir, exist_ok=True)
    else:
        char_dir = "characters"

    # Handle head/stat file name collision
    head_path = None
    stat_path = None
    if head and stat and head == stat:
        head_path = os.path.join(char_dir, f"head-{head}")
        stat_path = os.path.join(char_dir, f"stat-{stat}")
        download_file(f"{IMG_BASE}CharacterHeads/{head}", head_path)
        download_file(f"{IMG_BASE}StatCardsHd/{stat}", stat_path)
        # Update the json blob for these new file names
        char["headFileName"] = f"head-{head}"
        char["statCardFileName"] = f"stat-{stat}"
    else:
        if head:
            head_path = os.path.join(char_dir, head)
            download_file(f"{IMG_BASE}CharacterHeads/{head}", head_path)
            char["headFileName"] = head if head_path.endswith(head) else os.path.basename(head_path)
        if stat:
            stat_path = os.path.join(char_dir, stat)
            download_file(f"{IMG_BASE}StatCardsHd/{stat}", stat_path)
            char["statCardFileName"] = stat if stat_path.endswith(stat) else os.path.basename(stat_path)

    if sig and sig not in downloaded_signatures:
        download_file(f"{IMG_BASE}StatCardsHd/{sig}", f"SignatureMoves/{sig}")
        downloaded_signatures.add(sig)

# Save the big JSON object (with updated file names)
with open("moontome_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)