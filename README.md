# CNT4713 File Transfer Project

The server now implements the Chat control/data handshake, login, `who`, `broadcast`,
`private`, and `quit` commands, plus the file-transfer commands in the handout. File
transfers use an eight-byte unsigned big-endian length prefix; listings are
newline-terminated text. The client is still a skeleton and must use the same file
framing when its transfer methods are implemented. The method breakdown is a
suggested organization, not instructor-required naming.

The client's `connect()` now completes the merged server's handshake: it sends
`connect <address> <port>`, reads the status and newline-terminated data port,
and opens the data socket. Setup uses a ten-second socket timeout, then restores
blocking mode. Rejection, malformed replies, and connection failures close both
sockets and reset connection state. Login and the interactive client remain TODOs.
`receive_text_line()` reads one LF/CRLF-terminated UTF-8 line without consuming
the next response.

## Command and response helper contract

The command helpers use UTF-8, LF-terminated command lines; the server also accepts
CRLF. The original Chat Project uses newline-terminated control commands.
`send_command(command, argument)` sends one line and rejects embedded line breaks.
`receive_command(session)` returns the complete line without its terminator, or
`None` on a clean disconnect. A truncated line raises `EOFError`.

`send_response(connection, status_code, data)` sends `200\n\n` or `500\n\n`,
followed by optional success data (UTF-8 text or bytes). Failure replies have no
payload. The caller selects the socket required for that stage of the protocol.
`receive_response(connection, data_length=0)` returns `(status_code, data_bytes)`.
By default it reads only the header; when a successful payload's length is known,
the caller can request exactly that many bytes. Failure replies skip payload reads.
The file-transfer handout does not specify how a receiver detects the end of an
arbitrary TCP file payload, so this project uses an unsigned eight-byte, big-endian
length prefix after a successful `retr` response. For `stor`, the client must prefix
its upload with the same eight-byte length; the server returns the status after
receiving it. The `list` response is a comma-separated UTF-8 line terminated by LF.
This file framing rule is project-selected, not specified by the handout, and the
client implementation must match it.

Oversized command lines raise `ValueError`, invalid UTF-8 raises
`UnicodeDecodeError`, and truncated messages raise `EOFError`. The server closes a
client connection after malformed or partially consumed control lines. Invalid
command arguments receive a 500 status; the client must not try to resume parsing
a partially consumed response.

## Files

- `server.py`: server startup, client sessions, login, command handlers, transfers,
  responses, and cleanup.
- `client.py`: interactive commands, control/data connections, login, transfers,
  responses, and cleanup.
- `readme.txt`: submission placeholder for group member names and student IDs.

## Assignment requirements

The supplied File Transfer Project handout requires Python TCP socket programming,
separate client/server processes, and exactly `server.py` and `client.py` as the
program filenames. FTP libraries and external messaging frameworks are prohibited.
The final programs must retain all commands and behavior from the earlier Chat
Project. Intended invocation is `python server.py <port>` and `python client.py`.

| Command | Responsibility |
| --- | --- |
| `connect <address> <port>` | Establish control and advertised data connections. |
| `login <username>` | Preserve the original Chat login flow. |
| `list` | Return a comma-separated file listing over the data connection. |
| `stor <filename>` | Upload file contents over the data connection. |
| `retr <filename>` | Download file contents over the data connection. |
| `dele <filename>` | Delete a server file and return status. |
| `quit` | Acknowledge and end the client session. |

Commands use the control connection. The handout specifies responses on the data
port after login, with 200 for success and 500 for failure. Its response layout is
a status line, an empty line, and a data section when required. Preserve the exact
console output shown on pages 3-5 of the handout, including capitalization.
Addresses, ports, usernames, messages, and filenames must remain variable because
the grader pairs each submitted program with its own client or server.

## Remaining implementation details

- The client is unfinished and must implement the matching eight-byte length
  prefix for file transfers and LF-terminated listing reads.
- The handout mentions creating and navigating directories but defines no directory
  commands. No extra directory commands are assumed here.

Chapter 2 supplies TCP client/server socket background. Chapter 4 supplies IP and
network-layer background; it does not define additional application commands.

## Final submission checklist (future work)

- Implement and verify both programs, including required original Chat behavior.
- Fill in group member names and IDs in `readme.txt`.
- Submit source `.py` files directly, without ZIPs or IDE project files.
- Create `AI_Usage.pdf` with the AI system, each prompt/output, what was correct,
  shortcomings, testing, and the team's subsequent fixes, under the course policy.
  This skeleton was generated with OpenAI Codex; retain this chat and generated
  files for that record. The report is a future deliverable, not completed here.
- Record a narrated demonstration of every graded command and AI usage. Show
  and explain the message formats in Wireshark. Any shared video link must be
  accessible by the deadline and remain active for the rest of the semester.

The supplied LMS export (`Project 2.pdf`) lists 130 points: 70 for client/server
functionality, 30 for the video, and 30 for AI usage. It takes precedence over the
older grading table in the project handout.

## Chat event framing

The client implements `who`, `broadcast`, and `private`, plus join/logout and
incoming-message notifications. To distinguish asynchronous notifications from
ordinary command replies on the same data stream, this branch prefixes each
notification with `EVENT\n`, followed by `200\n\n`, its kind (`join`, `logout`,
`Broadcast`, or `Private`), username, and (for messages) message text as LF-ended
lines. Broadcast also returns an ordinary status acknowledgement to its sender.
The client skips and displays event frames while awaiting a command response, and
uses `select` to display notifications while waiting for terminal input.

This EVENT marker is a project-specific protocol extension, not a requirement
verified from the missing original Chat specification. It requires the updated
client and server together. The instructor's reference-client/server compatibility
must be checked before submission, including the existing eight-byte file prefix.
