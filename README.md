# CNT4713 File Transfer Project

Partial implementation: constructors, resource cleanup, the server control listener
and acceptance loop, client TCP connection helpers, and command/response helpers
are implemented.
The Chat handshake, server data-connection setup, file transfers, command loops,
and entry points remain unfinished. Client `connect()` currently opens only the
control socket; it does not yet negotiate or open the data connection automatically.
The acceptance loop handles clients sequentially and closes each session when
`handle_client()` returns; that handler is still a placeholder.
The method breakdown is a suggested organization, not instructor-required naming.

## Command and response helper contract

The helpers currently use provisional UTF-8, LF-terminated command lines. Readers
also accept CRLF. These framing choices need confirmation against the missing
Chat Project specification before grader compatibility can be claimed.
`send_command(command, argument)` sends one line and rejects embedded line breaks.
`receive_command(session)` returns the complete line without its terminator, or
`None` on a clean disconnect. A truncated line raises `EOFError`.

`send_response(connection, status_code, data)` sends `200\n\n` or `500\n\n`,
followed by optional success data (UTF-8 text or bytes). Failure replies have no
payload. The caller selects the socket required for that stage of the protocol.
`receive_response(connection, data_length=0)` returns `(status_code, data_bytes)`.
By default it reads only the header; when a successful payload's length is known,
the caller can request exactly that many bytes. Failure replies skip payload reads.
The helper never guesses payload length from a receive call or a timeout, and it
does not add a length field to the wire format. Unknown-length listings and file
transfers still need the course's completion rule before they can be implemented.

Malformed headers and oversized command lines raise `ValueError`, invalid UTF-8
raises `UnicodeDecodeError`, and truncated messages raise `EOFError`. Future
session/command loops must handle these errors and close the affected connection;
they must not try to resume parsing an invalid or partially consumed message.

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

## Details to resolve before implementation

- The earlier Chat Project specification/code is absent from the supplied files
  and repository. Obtain it to fill in the original commands, handshake, login,
  data-port negotiation, and exact wire format. The generic Chat handler is only
  a placeholder until those actual commands are known.
- Confirm message boundaries, file-transfer completion, byte encoding for text,
  and data-connection reuse against the course protocol. TCP is a byte stream;
  one receive call is not guaranteed to return one entire message or file.
- Confirm status placement and sequencing for each transfer. The examples do
  not fully define the bytes exchanged, especially the connect response and
  successful download. Do not invent a protocol incompatible with the grader.
- The overview mentions creating/navigating directories, but the command table
  defines no directory commands. No extra directory commands are assumed here.

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
