import json
import uuid
import hashlib
import hmac
import base64
import sys
import os
from datetime import datetime, timedelta

SECRET_KEY = "DsAc2024S3cur3K3y!@#$"

LICENSE_TYPES = {
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
    "lifetime": None
}

LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses.json")

def load_licenses():
    if not os.path.exists(LICENSE_FILE):
        return {}
    with open(LICENSE_FILE, "r") as f:
        return json.load(f)

def save_licenses(licenses):
    with open(LICENSE_FILE, "w") as f:
        json.dump(licenses, f, indent=2)

def generate_key():
    raw = str(uuid.uuid4()).replace("-", "").upper()[:20]
    return "DSAC-" + "-".join([raw[i:i+5] for i in range(0, 20, 5)])

def sign_data(data):
    fields = ["created", "expires", "key", "note", "server_ip", "status", "type"]
    msg = ";".join(f"{f}={data.get(f, '')}" for f in fields)
    return hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()

def generate_license(license_type, note=""):
    if license_type not in LICENSE_TYPES:
        print(f"Error: invalid type. Use: {', '.join(LICENSE_TYPES.keys())}")
        return None

    key = generate_key()
    now = datetime.utcnow()

    license_data = {
        "key": key,
        "type": license_type,
        "created": now.isoformat() + "Z",
        "expires": (now + timedelta(days=LICENSE_TYPES[license_type])).isoformat() + "Z" if LICENSE_TYPES[license_type] else None,
        "status": "active",
        "note": note,
        "server_ip": ""
    }

    license_data["signature"] = sign_data(license_data)

    licenses = load_licenses()
    licenses[key] = license_data
    save_licenses(licenses)

    print(f"\n=== LICENSE GENERATED ===")
    print(f"Key:    {key}")
    print(f"Type:   {license_type}")
    print(f"Expiry: {license_data['expires'] or 'Never (Lifetime)'}")
    print(f"File:   {LICENSE_FILE}")
    print()

    return key

def list_licenses():
    licenses = load_licenses()
    if not licenses:
        print("No licenses found.")
        return

    print(f"\n{'Key':<30} {'Type':<12} {'Status':<10} {'Expires':<22} {'Note'}")
    print("="*90)
    for key, data in sorted(licenses.items()):
        expires = data.get("expires") or "LIFETIME"
        if data["status"] == "active" and data.get("expires"):
            exp_date = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
            if exp_date < datetime.utcnow().replace(tzinfo=exp_date.tzinfo):
                data["status"] = "expired"
                licenses[key] = data
                save_licenses(licenses)
        print(f"{key:<30} {data['type']:<12} {data['status']:<10} {expires:<22} {data.get('note', '')}")
    print()

def revoke_license(key):
    licenses = load_licenses()
    if key in licenses:
        licenses[key]["status"] = "revoked"
        save_licenses(licenses)
        print(f"License {key} revoked.")
    else:
        print(f"License {key} not found.")

def export_license(key, output_file):
    licenses = load_licenses()
    if key not in licenses:
        print(f"License {key} not found.")
        return

    data = licenses[key]
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"License exported to {output_file}")

def verify_license(key):
    licenses = load_licenses()
    if key not in licenses:
        return {"valid": False, "reason": "Key not found"}

    data = dict(licenses[key])

    sig = data.pop("signature", None)
    if not sig:
        return {"valid": False, "reason": "No signature"}

    expected = sign_data(data)
    if sig != expected:
        return {"valid": False, "reason": "Invalid signature (tampered)"}

    if data["status"] != "active":
        return {"valid": False, "reason": f"Status: {data['status']}"}

    if data.get("expires"):
        exp_date = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
        if exp_date < datetime.utcnow().replace(tzinfo=exp_date.tzinfo):
            return {"valid": False, "reason": "Expired"}

    remaining = None
    if data.get("expires"):
        exp_date = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
        remaining = (exp_date - datetime.utcnow().replace(tzinfo=exp_date.tzinfo)).days

    return {"valid": True, "type": data["type"], "remaining_days": remaining, "expires": data.get("expires")}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Generate: python license_generator.py generate <monthly|quarterly|yearly|lifetime> [--note \"text\"]")
        print("  List:     python license_generator.py list")
        print("  Revoke:   python license_generator.py revoke <KEY>")
        print("  Export:   python license_generator.py export <KEY> --output license.json")
        print("  Verify:   python license_generator.py verify <KEY>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate":
        if len(sys.argv) < 3:
            print("Specify type: monthly, quarterly, yearly, or lifetime")
            sys.exit(1)
        ltype = sys.argv[2]
        note = ""
        if "--note" in sys.argv:
            idx = sys.argv.index("--note")
            if idx + 1 < len(sys.argv):
                note = sys.argv[idx + 1]
        generate_license(ltype, note)

    elif command == "list":
        list_licenses()

    elif command == "revoke":
        if len(sys.argv) < 3:
            print("Specify license key to revoke")
            sys.exit(1)
        revoke_license(sys.argv[2])

    elif command == "export":
        if len(sys.argv) < 3:
            print("Specify license key to export")
            sys.exit(1)
        key = sys.argv[2]
        output = "license.json"
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            if idx + 1 < len(sys.argv):
                output = sys.argv[idx + 1]
        export_license(key, output)

    elif command == "verify":
        if len(sys.argv) < 3:
            print("Specify license key to verify")
            sys.exit(1)
        result = verify_license(sys.argv[2])
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
