---
name: mailbird-attachment-tool
description: Build a searchable, sortable index of every email attachment in a Mailbird account (filter by sender, domain, date, type), published as a private page that can open the email or save the file.
---

# Mailbird Attachment Tool

Rebuilds the old Mailbird "all attachments" view on top of the Mailbird MCP tools. The output is a private Artifact page: a table of every attachment with search, domain and date filters, grouping by sender or domain, file-type chips, and two buttons per row (Open email in Mailbird in a new window, Save file).

Files in this skill:
- `assets/index.html` is the page template. It ships empty and loads `attachments.json` from the same published folder.
- `scripts/merge.py` turns the collected JSONL part files into `attachments.json`.

## Prerequisites

- Mailbird running, with its AI / MCP connection turned on, and its tools available in this session (search_conversations, get_conversation, list_attachments, list_accounts, list_folders).
- The page's buttons work only when it is opened in the Claude desktop app with Mailbird running. The first click asks the viewer for permission. Elsewhere the page still works as a searchable index and shows a hint instead of buttons.
- Use read-only Mailbird calls only. Never call anything that sends, moves, deletes or archives.

## Step 1: Scope with the user

Ask (one short question if not already said): which account, and how far back (default one year). Ask whether to leave out calendar replies and .ics files (default yes to both). Call list_accounts for the accountId and list_folders to build `folders.json`, a map of folder id to folder name such as `{"38": "Inbox", "56": "Sent"}`.

## Step 2: Collect

Work in a private scratch folder and keep one JSONL file per window in `parts/`.

1. Search by half-month windows: `search_conversations` with `accountId`, `limit: 100`, query `has:attachment after:YYYY/MM/DD before:YYYY/MM/DD`. Dates must use slashes (dashes cause an internal error). Widen each window by one day on both sides. If a search returns exactly 100 results it was cut off: split that window in half and repeat. Dedupe conversationIds across windows.
2. Drop conversations whose subject starts with `Accepted:`, `Declined:`, `Tentative:` or `Tentatively Accepted:` (if the user wants calendar replies skipped).
3. Call `get_conversation` once per conversation, in parallel groups of at most 6. Each message has id, from.displayName, from.email, subject, receivedAtUtc, attachmentCount. The conversation has a folderId.
4. For every message with attachmentCount > 0 whose receivedAtUtc is inside the OVERALL requested range, call `list_attachments(messageId)` and record every entry, including entries Mailbird marks inline (merge.py classifies signature logos). Judge the date against the overall range, not the search window. Search reports a conversation by its last message date, so a thread that spans two windows is returned once; if each window keeps only its own messages, the older messages are lost (this dropped about 140 emails in the first build).
5. Append one line per attachment to the part file, with exactly these keys, values copied as returned, never invented or tidied:
   `{"f": fileName, "m": mimeType, "s": size, "d": receivedAtUtc, "n": from.displayName, "e": from.email, "sub": subject, "fo": folderId, "mid": messageId, "aid": attachmentId, "cid": conversationId}`
   Append in batches of 10 to 15 conversations so partial work survives.
6. If a conversation errors every time, note its subject and tell the user at the end. Put it in the page banner.
7. If Mailbird stops answering ("No result received", not connected), stop, keep what exists, and tell the user. Do not retry in a loop.

For a large mailbox, split the date range across parallel subagents. Give each its own output file and its own private work folder (helpers that share one scratch folder overwrite each other's scripts), the steps above verbatim, and the rule to validate that every line parses and has all 11 keys.

## Step 3: Verify completeness

Before publishing, do an independent recount. For each window, repeat the searches and get_conversation calls without looking at the part files, list every message with attachmentCount > 0 in range (messageId, count, date, conversationId), and diff against the collected message ids. Fetch whatever is missing. Messages that carry only inline signature images may legitimately be absent.

## Step 4: Merge

```
python3 ${CLAUDE_SKILL_DIR}/scripts/merge.py --parts parts --out attachments.json \
  --account <the mailbox address> --start <YYYY-MM-DD> --folders folders.json \
  --note "<known gaps, optional>"
```

Add `--keep-calendar` if the user wants calendar files kept. If `${CLAUDE_SKILL_DIR}` is not set, use the path to `scripts/merge.py` inside this skill's folder. The script drops duplicates on (messageId, attachmentId), drops anything before `--start`, hides signature-style small images behind a toggle on the page, and prints the record count, calendar files left out, and any bad lines.

## Step 5: Publish the page

Load the artifact-design and artifact-capabilities skills first if they are available, then publish `assets/index.html` with the Artifact tool:

- `files`: `{"attachments.json": "<path to attachments.json>"}`, icon `attachment`.
- `capabilities`: `{"mcp": {"servers": [{"server": "host:mailbird", "tools": ["select_conversation", "get_attachment_content"]}]}, "downloads": true}`.
- `host:mailbird` is the name of the local Mailbird server on the viewer's device. If the buttons say Mailbird is not reachable even with Mailbird open in the desktop app, check how the local server is named in the app, then change it both in the manifest and in the `mb.server` value in the script near the bottom of `index.html`.
- The page is private to its owner until they share it. It lists real sender names, subjects and file names, so do not share it with anyone who should not see the mailbox.

On a refresh, rebuild `attachments.json` for the new range and republish with `files` set to the new file. Do not combine `edits` with `files` in one publish call.

## Step 6: Tell the user

Say in a line what the page is. State the coverage dates, the counts (shown by default, hidden signature images, calendar files left out) and every known gap. Mention that the buttons work only in the Claude desktop app with Mailbird running, and that the first click asks permission.

## Known limits (state these plainly)

- Search returns at most 100 conversations per query and its date syntax is undocumented, so windows are split until each returns fewer than 100. A thread that never appears in any search could still be missed; the recount in Step 3 is the safeguard.
- A conversation Mailbird cannot read errors every time. List it in the banner.
- The signature-logo filter is a heuristic on file name and size (auto-named image under 150 KB). Real small images with such names are hidden behind the toggle, not deleted.
- The index is a snapshot, not live. Rerun Steps 2 to 5 to refresh.
- Save is limited to the downloads allowlist (gif png jpg jpeg webp mp4 webm mov txt json md docx pptx epub csv ttf html svg pdf xlsx zip fig) and to attachments of 10 MB or less. For other types use Open email in Mailbird.
- Sizes shown are the server's encoded transfer size scaled by 0.75, so they are estimates.
- `attachments.json` holds real mail metadata (senders, subjects, file names). Never put it in a shared repo, a shared page, or anywhere the user did not choose.
