# CNT4713 File Transfer Project

Python TCP client/server implementation with login, file listing, upload, download,
delete, quit, and Chat commands (`who`, `broadcast`, `private`). No external Python
packages are required. The client and server run as separate processes.

## Run

Use Python 3.9 or newer. Start the server from the directory whose files you want
to share, and the client from a separate directory for local uploads/downloads:

```sh
# Server terminal, with the server storage directory as the working directory:
python /absolute/path/to/project/server.py 8991

# Client terminal, with the local file directory as the working directory:
python /absolute/path/to/project/client.py
```

Then enter commands in the client:

```text
connect 127.0.0.1 8991
login alice
list
stor sample.txt
retr sample.txt
dele sample.txt
who
broadcast Hello everyone
private bob Hello Bob
quit
```

Addresses, ports, usernames, messages, and filenames are supplied at runtime.
Filenames refer to the current directory; spaces are supported without quoting.
Downloads replace an existing local file only after the entire transfer succeeds.
Failed or interrupted downloads remove the temporary file and preserve the original.
EOF or Ctrl+C exits the client and closes its sockets. A connection failure resets
connection state so another `connect` can be attempted. Before login, `quit` closes
locally because the server requires authentication for its quit command.

## Implementation and protocol

- The control socket carries LF-terminated UTF-8 commands. CRLF input is accepted.
- The client sends `connect <address> <port>` after opening TCP. The server returns
  `200\n\n<data-port>\n` on the control socket. The client opens that data port.
  Setup socket operations use a ten-second timeout, then return to blocking mode.
- Login and subsequent command responses use the data socket. Ordinary replies
  start with `200\n\n` for success or `500\n\n` for failure.
- `list` and `who` success data is one LF-terminated, comma-separated text line.
- `stor` sends an unsigned eight-byte big-endian byte count followed by file bytes.
  The server returns its status after receiving the upload.
- `retr` success consists of a status header, the same eight-byte length, and the
  exact file bytes. Failure responses have no payload.
- Successful login, upload, delete, private-message, broadcast, and quit replies
  are status-only. Broadcast also echoes a notification to its sender.
- Chat notifications have an explicit `EVENT\n` prefix, then `200\n\n`, a kind
  (`join`, `logout`, `Broadcast`, `Private`), a username, and a message for the last
  two kinds. Each text field occupies one LF-terminated line. The client displays
  notifications while waiting for input or an ordinary reply; only one reader
  accesses its data stream.

The eight-byte file prefix and EVENT marker are **project-specific conventions**.
The supplied File Transfer handout does not specify the file completion rule, and
we do not have the original Chat Project specification. The EVENT marker resolves
an ambiguity in the merged server's earlier format, where status-only replies and
notifications both began with `200\n\n`. It changes the Chat notification wire
format and requires this branch's client and server together.

Compatibility with the instructor's reference programs remains unverified. Confirm
handshake, file framing, Chat framing, and Chat console output against the original
specification before submission.

## Submission work remaining

- Confirm reference-program protocol compatibility and exact required output.
- Fill in group member names and IDs in `readme.txt`.
- Submit the required source files directly, without ZIPs or IDE project files.
- Prepare `AI_Usage.pdf` under the course policy, recording the AI system, prompts,
  outputs, correctness, shortcomings, and subsequent changes. This branch
  was developed with OpenAI Codex; retain the chat and incremental commits.
- Record a narrated demonstration of every graded feature, explain AI usage, and
  show and explain the actual message formats in Wireshark. Keep any shared video
  link accessible through the rest of the semester.

The supplied LMS export lists 130 points: 70 for functionality, 30 for the video,
and 30 for AI usage. It overrides the older table in the File Transfer handout.
The handout mentions directories but supplies no directory-management commands;
this implementation does not invent additional commands for them.
