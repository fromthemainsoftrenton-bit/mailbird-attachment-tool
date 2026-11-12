"""Merge collected parts/*.jsonl into attachments.json for the Mailbird Attachment Tool page.

Usage:
  python3 merge.py --parts DIR --out attachments.json --account you@example.com \
      --start 2025-11-12 [--folders folders.json] [--keep-calendar] [--note "banner text"]

folders.json maps Mailbird folder ids to names, e.g. {"38": "Inbox", "56": "Sent"}.
"""
import argparse, datetime, glob, json, os, re

SIG = re.compile(r"^(image\d*|Outlook-[\w-]+|~WRD\d+|ATT\d+)\.(png|jpe?g|gif|bmp)$", re.I)
KEYS = ["f", "m", "s", "d", "n", "e", "sub", "fo", "mid", "aid", "cid"]

ap = argparse.ArgumentParser()
ap.add_argument("--parts", required=True, help="folder holding the *.jsonl part files")
ap.add_argument("--out", default="attachments.json")
ap.add_argument("--account", required=True, help="the mailbox's own address (marks mail you sent)")
ap.add_argument("--start", required=True, help="earliest date to keep, YYYY-MM-DD")
ap.add_argument("--folders", help="JSON file mapping folder id -> folder name")
ap.add_argument("--keep-calendar", action="store_true", help="keep .ics/.vcs and calendar mime types")
ap.add_argument("--note", default="", help="banner text shown on the page (known gaps)")
a = ap.parse_args()

folders = {}
if a.folders:
    folders = {str(k): v for k, v in json.load(open(a.folders, encoding="utf-8")).items()}

skipped, seen, out, bad, parts = 0, set(), [], [], []
for path in sorted(glob.glob(os.path.join(a.parts, "*.jsonl"))):
    n = 0
    for ln, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            assert all(k in r for k in KEYS)
        except Exception as ex:
            bad.append((os.path.basename(path), ln, str(ex)))
            continue
        if not a.keep_calendar and (str(r["f"] or "").lower().endswith((".ics", ".vcs")) or "calendar" in str(r["m"] or "").lower()):
            skipped += 1
            continue
        key = (r["mid"], r["aid"])
        if key in seen or str(r["d"])[:10] < a.start:
            continue
        seen.add(key)
        n += 1
        mime = str(r["m"] or "").lower()
        # Mailbird often does not flag signature logos as inline, so treat small auto-named images as inline.
        sig = bool(r.get("inline")) or (mime.startswith("image/") and (r["s"] or 0) < 150000 and bool(SIG.match(str(r["f"] or ""))))
        out.append({"file": r["f"], "mime": mime, "size": r["s"], "inline": sig, "date": r["d"],
                    "fromName": r["n"], "fromEmail": r["e"], "subject": r["sub"], "folder": folders.get(str(r["fo"]), ""),
                    "messageId": r["mid"], "attachmentId": r["aid"], "conversationId": r["cid"]})
    parts.append((os.path.basename(path)[:-6], n))

out.sort(key=lambda x: x["date"], reverse=True)
days = sorted(x["date"][:10] for x in out)
meta = {"account": a.account, "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {"from": days[0], "to": days[-1]} if days else {}, "sample": False}
if a.note:
    meta["note"] = a.note
json.dump({"meta": meta, "attachments": out}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
print("records", len(out), "| calendar files left out", skipped, "| parts", parts, "| bad lines", bad)
