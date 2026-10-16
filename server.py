"""File-transfer server with TCP control setup, state, and cleanup."""

import os
import socket
import sys
import tempfile
import threading


class FileTransferServer:
    FILE_LENGTH_BYTES = 8
    TRANSFER_CHUNK_SIZE = 65536

    def __init__(self, control_port):
        self.control_port = control_port
        self.control_socket = None
        self.running = False

        self.sessions = {}
        self.users = {}
        self._sessions_lock = threading.RLock()

    def start(self):
        print("Starting server…")
        print("Creating server socket")
        self.create_control_socket()
        self.running = True
        print("Awaiting connections…")

        try:
            self.accept_connections()
        except KeyboardInterrupt:
            self.shutdown()
        except OSError:
            self.shutdown()
            raise

    def create_control_socket(self):
        if self.control_socket is not None:
            raise RuntimeError("The control listener is already open.")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("", int(self.control_port)))
            listener.listen()
        except (OSError, ValueError, TypeError, OverflowError):
            listener.close()
            raise

        self.control_socket = listener
        self.control_port = listener.getsockname()[1]

    def accept_connections(self):
        if self.control_socket is None:
            raise RuntimeError("Create the control listener before accepting clients.")

        while self.running:
            try:
                control_socket, client_address = self.control_socket.accept()
            except OSError:
                if not self.running:
                    break
                raise

            session = {
                "control_socket": control_socket,
                "client_address": client_address,
                "data_listener": None,
                "data_socket": None,
                "username": None,
                "data_lock": threading.Lock(),
            }
            with self._sessions_lock:
                self.sessions[control_socket] = session
            print("Connection requested. Creating data socket")
            try:
                threading.Thread(
                    target=self.handle_client,
                    args=(control_socket, client_address),
                    daemon=True,
                ).start()
            except RuntimeError:
                self.close_session(session)
                raise

    def handle_client(self, control_socket, client_address):
        with self._sessions_lock:
            session = self.sessions.get(control_socket)
        if session is None:
            return

        try:
            first_command = self.receive_command(session)
            if first_command is None:
                return

            parts = first_command.split()
            if (
                len(parts) != 3
                or parts[0].lower() != "connect"
                or not parts[1]
            ):
                self.send_response(control_socket, 500)
                return
            try:
                requested_port = int(parts[2])
            except ValueError:
                self.send_response(control_socket, 500)
                return
            if not 1 <= requested_port <= 65535:
                self.send_response(control_socket, 500)
                return

            self.create_data_connection(session)
            while self.running:
                command = self.receive_command(session)
                if command is None or self.dispatch_command(session, command):
                    break
        except (EOFError, OSError, UnicodeDecodeError, ValueError) as error:
            if self.running:
                print(f"Error handling client {client_address}: {error}")
        finally:
            self.close_session(session)

    def create_data_connection(self, session):
        control_socket = session.get("control_socket")
        if control_socket is None:
            raise RuntimeError("The session has no control connection.")
        if session.get("data_socket") is not None:
            raise RuntimeError("The session already has a data connection.")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("", 0))
            listener.listen(1)
        except OSError:
            listener.close()
            try:
                self.send_response(control_socket, 500)
            except OSError as response_error:
                print(f"Error reporting data socket failure: {response_error}")
            raise

        session["data_listener"] = listener
        try:
            self.send_response(
                control_socket, 200, str(listener.getsockname()[1])
            )
            data_socket, _ = listener.accept()
            session["data_socket"] = data_socket
        finally:
            listener.close()
            if session.get("data_listener") is listener:
                session["data_listener"] = None

    def receive_command(self, session):
        """Read one UTF-8 command line, or return None for a clean disconnect."""
        connection = session.get("control_socket")
        if connection is None:
            raise RuntimeError("The session has no control connection.")

        message = bytearray()
        while True:
            byte = connection.recv(1)
            if not byte:
                if message:
                    raise EOFError("Connection closed in the middle of a command.")
                return None
            if byte == b"\n":
                break
            message.extend(byte)
            if len(message) > 65536:
                raise ValueError("Command exceeds the 64 KiB limit.")

        command = bytes(message).removesuffix(b"\r").decode("utf-8")
        if not command.strip() or "\r" in command:
            raise ValueError("Expected a nonempty command without embedded line breaks.")
        return command

    def dispatch_command(self, session, command):
        parts = command.split(None, 1)
        name = parts[0].lower()
        argument = parts[1].strip() if len(parts) == 2 else ""

        if name == "login":
            self.handle_login(session, argument)
            return False

        if session.get("username") is None:
            self._send_data_response(session, 500)
            return False

        if name == "quit":
            if argument:
                self._send_data_response(session, 500)
                return False
            self.handle_quit(session)
            return True
        if name == "list":
            if argument:
                self._send_data_response(session, 500)
            else:
                self.handle_list(session)
            return False
        if name in ("stor", "retr", "dele"):
            if not argument:
                self._send_data_response(session, 500)
            elif name == "stor":
                self.handle_stor(session, argument)
            elif name == "retr":
                self.handle_retr(session, argument)
            else:
                self.handle_dele(session, argument)
            return False
        if name in ("who", "broadcast", "private"):
            self.handle_chat_command(session, command)
            return False

        self._send_data_response(session, 500)
        return False

    def handle_login(self, session, username):
        data_socket = session.get("data_socket")
        if data_socket is None:
            raise RuntimeError("The session has no data connection.")

        print(f"Login requested by: {username}")
        if (
            not username
            or any(character.isspace() for character in username)
            or session.get("username") is not None
        ):
            self._send_data_response(session, 500)
            return

        with self._sessions_lock:
            if username in self.users:
                self._send_data_response(session, 500)
                return
            session["username"] = username
            self.users[username] = session

        self._send_data_response(session, 200)
        self.broadcast_to_data(
            self._build_response(200, "join", username), exclude=username
        )

    def handle_chat_command(self, session, command):
        parts = command.split(None, 1)
        name = parts[0].lower()
        argument = parts[1] if len(parts) == 2 else ""
        username = session["username"]

        if name == "who":
            if argument:
                self._send_data_response(session, 500)
                return
            with self._sessions_lock:
                names = ", ".join(self.users)
            print("Who requested. Sending users.")
            self._send_data_response(session, 200, names)
            return

        if name == "broadcast":
            if not argument:
                self._send_data_response(session, 500)
                return
            print(f"Broadcast requested by {username}")
            print(f"Message: {argument}")
            self.broadcast_to_data(
                self._build_response(200, "Broadcast", username, argument)
            )
            return

        if name == "private":
            private_parts = argument.split(None, 1)
            if len(private_parts) != 2:
                self._send_data_response(session, 500)
                return
            recipient, message = private_parts
            with self._sessions_lock:
                recipient_session = self.users.get(recipient)
            if recipient_session is None:
                self._send_data_response(session, 500)
                return

            try:
                self._send_data_bytes(
                    recipient_session,
                    self._build_response(200, "Private", username, message),
                )
            except OSError as error:
                print(f"Error sending private message to {recipient}: {error}")
                self._send_data_response(session, 500)
                return

            print(f"Private message from {username} to {recipient}")
            self._send_data_response(session, 200)

    def handle_stor(self, session, filename):
        username = session["username"]
        print(f"Stor {filename} requested by {username}")
        temporary_path = None
        transfer_complete = False
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".upload-", dir=os.getcwd(), delete=False
            ) as temporary_file:
                temporary_path = temporary_file.name

            self.receive_file(session["data_socket"], temporary_path)
            transfer_complete = True
            destination = self._resolve_filename(filename)
            os.replace(temporary_path, destination)
            temporary_path = None
        except (OSError, EOFError, ValueError) as error:
            if temporary_path is not None:
                try:
                    os.remove(temporary_path)
                except FileNotFoundError:
                    pass
                except OSError as cleanup_error:
                    print(f"Error removing incomplete upload: {cleanup_error}")
            self._send_data_response(session, 500)
            print(f"STOR failed for {filename}: {error}")
            if not transfer_complete:
                raise
            return

        self._send_data_response(session, 200)
        print("STOR complete")

    def handle_retr(self, session, filename):
        username = session["username"]
        started = False
        try:
            source_path = self._resolve_filename(filename)
            if not os.path.isfile(source_path):
                raise FileNotFoundError(filename)
            source = open(source_path, "rb")
        except (OSError, ValueError) as error:
            self._send_data_response(session, 500)
            print(f"RETR failed for {filename}: {error}")
            return

        print(f"Retr requested by {username}. Sending file: {filename}")
        try:
            with source:
                with self._data_lock(session):
                    self.send_response(session["data_socket"], 200)
                    started = True
                    self.send_file(session["data_socket"], source)
        except (OSError, EOFError, ValueError) as error:
            if not started:
                self._send_data_response(session, 500)
            print(f"RETR failed for {filename}: {error}")
            if started:
                raise
            return

        print("File sent.")

    def handle_list(self, session):
        username = session["username"]
        print(f"List requested by {username}. Sending files.")
        try:
            filenames = []
            with os.scandir(".") as entries:
                for entry in entries:
                    if entry.is_file():
                        try:
                            self._resolve_filename(entry.name)
                        except ValueError:
                            continue
                        filenames.append(entry.name)
            payload = ", ".join(sorted(filenames)).encode("utf-8")
        except (OSError, UnicodeEncodeError) as error:
            self._send_data_response(session, 500)
            print(f"LIST failed: {error}")
            return

        self._send_data_response(session, 200, payload.decode("utf-8"))

    def handle_dele(self, session, filename):
        username = session["username"]
        print(f"Dele requested by {username}. Deleting file: {filename}")
        try:
            path = self._resolve_filename(filename)
            if not os.path.isfile(path):
                raise FileNotFoundError(filename)
            os.remove(path)
        except (OSError, ValueError) as error:
            self._send_data_response(session, 500)
            print(f"DELE failed for {filename}: {error}")
            return

        self._send_data_response(session, 200)
        print("Delete complete")

    def handle_quit(self, session):
        username = session.get("username")
        self._send_data_response(session, 200)
        if username is not None:
            print(f"Quit requested by {username}")
            with self._sessions_lock:
                if self.users.get(username) is session:
                    del self.users[username]
            self.broadcast_to_data(
                self._build_response(200, "logout", username), exclude=username
            )
            session["username"] = None

    def send_response(self, connection, status_code, data=None):
        """Send a status line, blank line, and optional UTF-8 text or raw bytes."""
        if connection is None:
            raise RuntimeError("A response requires an open connection.")
        if type(status_code) is not int or status_code not in (200, 500):
            raise ValueError("Status must be 200 (success) or 500 (failure).")

        if data is None:
            payload = b""
        elif isinstance(data, str):
            payload = data.encode("utf-8")
            if not payload.endswith(b"\n"):
                payload += b"\n"
        elif isinstance(data, bytes):
            payload = data
        else:
            raise TypeError("Response data must be text or bytes.")
        if status_code == 500 and payload:
            raise ValueError("Failure responses must contain only a status header.")

        connection.sendall(f"{status_code}\n\n".encode("ascii") + payload)

    def receive_file(self, data_socket, destination):
        if data_socket is None:
            raise RuntimeError("A file transfer requires an open data connection.")

        length = int.from_bytes(
            self._receive_exact(data_socket, self.FILE_LENGTH_BYTES), "big"
        )
        remaining = length
        with open(destination, "wb") as output_file:
            while remaining:
                chunk = data_socket.recv(min(self.TRANSFER_CHUNK_SIZE, remaining))
                if not chunk:
                    raise EOFError("Connection closed before the file completed.")
                output_file.write(chunk)
                remaining -= len(chunk)
        return length

    def send_file(self, data_socket, source):
        if data_socket is None:
            raise RuntimeError("A file transfer requires an open data connection.")

        file_length = os.fstat(source.fileno()).st_size
        data_socket.sendall(file_length.to_bytes(self.FILE_LENGTH_BYTES, "big"))
        remaining = file_length
        while remaining:
            chunk = source.read(min(self.TRANSFER_CHUNK_SIZE, remaining))
            if not chunk:
                raise EOFError("The source file changed before the transfer completed.")
            data_socket.sendall(chunk)
            remaining -= len(chunk)

    @staticmethod
    def _receive_exact(connection, byte_count):
        received = bytearray()
        while len(received) < byte_count:
            chunk = connection.recv(byte_count - len(received))
            if not chunk:
                raise EOFError("Connection closed before the transfer length arrived.")
            received.extend(chunk)
        return bytes(received)

    @staticmethod
    def _build_response(status_code, *lines):
        payload = "".join(f"{line}\n" for line in lines if line is not None)
        return f"{status_code}\n\n{payload}".encode("utf-8")

    def _send_data_response(self, session, status_code, data=None):
        connection = session.get("data_socket")
        if connection is None:
            raise RuntimeError("The session has no data connection.")
        with self._data_lock(session):
            self.send_response(connection, status_code, data)

    def _send_data_bytes(self, session, payload):
        connection = session.get("data_socket")
        if connection is None:
            raise RuntimeError("The session has no data connection.")
        with self._data_lock(session):
            connection.sendall(payload)

    def _data_lock(self, session):
        with self._sessions_lock:
            if "data_lock" not in session:
                session["data_lock"] = threading.Lock()
            return session["data_lock"]

    def broadcast_to_data(self, message, exclude=None):
        payload = message.encode("utf-8") if isinstance(message, str) else message
        with self._sessions_lock:
            recipients = [
                (username, session)
                for username, session in self.users.items()
                if username != exclude
            ]

        for username, session in recipients:
            try:
                self._send_data_bytes(session, payload)
            except OSError as error:
                print(f"Error sending message to {username}: {error}")

    @staticmethod
    def _resolve_filename(filename):
        if (
            not filename
            or filename in (".", "..")
            or any(character in filename for character in ("/", "\\", ":", "\0"))
        ):
            raise ValueError("Expected a filename in the server's current directory.")

        current_directory = os.path.realpath(os.getcwd())
        path = os.path.abspath(filename)
        resolved_path = os.path.realpath(path)
        if os.path.dirname(path) != os.path.abspath(current_directory):
            raise ValueError("Files must be in the server's current directory.")
        if os.path.commonpath((current_directory, resolved_path)) != current_directory:
            raise ValueError("Files must be in the server's current directory.")
        return path

    def close_session(self, session):
        control_socket = session.get("control_socket")
        username = session.get("username")
        with self._sessions_lock:
            self.sessions.pop(control_socket, None)
            if username is not None and self.users.get(username) is session:
                del self.users[username]

        for key in ("data_socket", "data_listener", "control_socket"):
            connection = session.get(key)
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    # A close failure must not prevent cleanup of other sockets.
                    pass

    def shutdown(self):
        self.running = False

        if self.control_socket is not None:
            try:
                self.control_socket.close()
            except OSError:
                pass
            finally:
                self.control_socket = None

        with self._sessions_lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            self.close_session(session)
        with self._sessions_lock:
            self.sessions.clear()
            self.users.clear()


def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py <port>")
        return 1

    try:
        control_port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a valid integer")
        return 1
    if not 1 <= control_port <= 65535:
        print("Error: Port must be between 1 and 65535")
        return 1

    server = FileTransferServer(control_port)
    try:
        server.start()
    except OSError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
