#!/usr/bin/env python3
"""Grant accessibility permission to the APP via TCC database"""
import sqlite3
import os
import subprocess
import time

APP_PATH = "/Applications/昨日重现.app"
BUNDLE_ID = "com.zrcr.app"

# Get the code signature of the APP
result = subprocess.run(
    ["codesign", "-dvvv", APP_PATH],
    capture_output=True, text=True
)
cdhash = None
for line in result.stderr.split("\n"):
    if "CDHash=" in line:
        cdhash = line.split("CDHash=")[1].strip()
        break

print(f"Bundle ID: {BUNDLE_ID}")
print(f"CDHash: {cdhash}")

# Try user TCC database first
tcc_db = os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db")
print(f"TCC DB: {tcc_db}")

try:
    conn = sqlite3.connect(tcc_db)
    cursor = conn.cursor()
    
    # Check existing schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Tables: {tables}")
    
    if 'access' in tables:
        cursor.execute("PRAGMA table_info(access)")
        cols = cursor.fetchall()
        print(f"Columns: {[c[1] for c in cols]}")
        
        # Check existing entries
        cursor.execute("SELECT * FROM access WHERE service='kTCCServiceAccessibility'")
        rows = cursor.fetchall()
        print(f"Existing accessibility entries: {len(rows)}")
        for r in rows:
            print(f"  {r}")
        
        # Insert or update
        # auth_value: 2 = allowed, auth_reason: 4 = user set
        # csreq is the code requirement blob
        cursor.execute("DELETE FROM access WHERE service='kTCCServiceAccessibility' AND client=?", (BUNDLE_ID,))
        cursor.execute(
            "INSERT INTO access (service, client, client_type, auth_value, auth_reason, auth_version, flags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('kTCCServiceAccessibility', BUNDLE_ID, 0, 2, 4, 1, 0)
        )
        conn.commit()
        print("Inserted accessibility permission!")
        
        # Verify
        cursor.execute("SELECT * FROM access WHERE service='kTCCServiceAccessibility' AND client=?", (BUNDLE_ID,))
        print(f"Verify: {cursor.fetchall()}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    print("Trying system TCC database...")
    try:
        sys_db = "/Library/Application Support/com.apple.TCC/TCC.db"
        conn = sqlite3.connect(sys_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print(f"System tables: {[r[0] for r in cursor.fetchall()]}")
        conn.close()
    except Exception as e2:
        print(f"System DB error: {e2}")