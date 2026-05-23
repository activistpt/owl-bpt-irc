#!/usr/bin/env python3
"""
OWL IRC Bridge for PTnet
Connects to PTnet IRC, receives messages, writes them for the agent to process,
and sends agent responses back to IRC channels.

Communication: uses a simple file-based message queue.
- Incoming IRC messages -> /home/.hermes/irc/incoming.jsonl
- Outgoing agent responses -> /home/.hermes/irc/outgoing.jsonl
"""

import socket
import ssl
import time
import sys
import os
import json
import threading
import queue
import datetime

# === CONFIG ===
IRC_SERVER = "zen.ptnet.org"
IRC_PORT = 6697
IRC_NICK = "OWL"
IRC_REALNAME = "OWL - We are Anonymous"
IRC_CHANNELS = ["#rebeleao", "#deep-web"]
QUEUE_DIR = os.path.expanduser("~/.hermes/irc")
INCOMING_FILE = os.path.join(QUEUE_DIR, "incoming.jsonl")
OUTGOING_FILE = os.path.join(QUEUE_DIR, "outgoing.jsonl")
HEARTBEAT_INTERVAL = 60
# ===============

os.makedirs(QUEUE_DIR, exist_ok=True)

def now():
    return datetime.datetime.now().strftime("%H:%M:%S")

def log(msg):
    print(f"[{now()}] {msg}", flush=True)

def write_incoming(data):
    """Write incoming IRC message for agent to process"""
    with open(INCOMING_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")

class PTnetIRC:
    def __init__(self):
        self.sock = None
        self.connected = False
        self.joined_channels = set()
        self.running = True
        self.buffer = ""
        self.processed_ids = set()
        self.channel_members = {}  # { "#channel": set(nick1, nick2, ...) }
        self.needs_names = set()  # channels that need NAMES refresh
        # Lock file to prevent multiple instances
        self.lock_file = os.path.join(QUEUE_DIR, ".irc_lock")

    def acquire_lock(self):
        """Prevent multiple IRC instances"""
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file) as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, 0)  # Check if process exists
                log(f"Already running (PID {old_pid})")
                return False
            except (OSError, ValueError):
                pass  # Stale lock
        with open(self.lock_file, "w") as f:
            f.write(str(os.getpid()))
        return True

    def release_lock(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass

    def connect(self):
        log(f"Connecting to {IRC_SERVER}:{IRC_PORT}...")
        
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(30)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=IRC_SERVER)
            self.sock.connect((IRC_SERVER, IRC_PORT))
            self.sock.settimeout(1)
        except Exception as e:
            log(f"Connection failed: {e}")
            return False

        self.send_raw(f"NICK {IRC_NICK}")
        self.send_raw(f"USER {IRC_NICK} 0 * :{IRC_REALNAME}")
        self.connected = True
        log(f"Connected! Nick: {IRC_NICK}")
        return True

    def send_raw(self, msg):
        if self.sock:
            try:
                self.sock.send(f"{msg}\r\n".encode("utf-8", errors="replace"))
            except Exception as e:
                log(f"Send error: {e}")
                self.connected = False

    def send_msg(self, target, msg):
        max_len = 400
        lines = [msg[i:i+max_len] for i in range(0, len(msg), max_len)]
        for line in lines:
            self.send_raw(f"PRIVMSG {target} :{line}")

    def send_notice(self, target, msg):
        max_len = 400
        lines = [msg[i:i+max_len] for i in range(0, len(msg), max_len)]
        for line in lines:
            self.send_raw(f"NOTICE {target} :{line}")

    def join_channel(self, channel):
        self.send_raw(f"JOIN {channel}")

    def request_names(self, channel):
        """Request NAMES list for a channel to refresh member cache"""
        self.needs_names.add(channel)
        self.send_raw(f"NAMES {channel}")
        log(f"NAMES requested for {channel}")

    def handle_ping(self, line):
        if line.startswith("PING"):
            pong_arg = line.split(" ", 1)[1] if " " in line else ""
            self.send_raw(f"PONG {pong_arg}")
            return True
        return False

    def parse_message(self, line):
        if "PRIVMSG" not in line:
            return None
        try:
            parts = line.split("PRIVMSG", 1)
            sender_full = parts[0].lstrip(":")
            sender = sender_full.split("!")[0]
            rest = parts[1].strip()
            target, msg = rest.split(" ", 1)
            msg = msg.lstrip(":")
            
            # Detect if sender is channel operator (@), halfop (+), or voice
            is_op = sender.startswith("@") or "!" in sender_full and "@" in sender_full.split("!")[1] if "!" in sender_full else False
            # Clean @ prefix from sender nick for consistency
            clean_sender = sender.lstrip("@").lstrip("%").lstrip("+").lstrip("~").lstrip("&")
            
            return {
                "sender": clean_sender,
                "sender_full": sender_full,
                "target": target,
                "message": msg,
                "is_channel": target.startswith("#"),
                "is_op": is_op,
                "timestamp": datetime.datetime.now().isoformat()
            }
        except:
            return None

    def handle_line(self, line):
        line = line.strip()
        if not line:
            return

        # PING/PONG
        if self.handle_ping(line):
            return

        parts = line.split()
        
        # Server numeric replies
        if len(parts) >= 2:
            sender_host = parts[0].lstrip(":")
            if sender_host == IRC_SERVER or sender_host.endswith(".ptnet.org"):
                code = parts[1]
                
                if code == "001":
                    log("Registered! Joining channels...")
                    for ch in IRC_CHANNELS:
                        self.join_channel(ch)
                
                elif code == "366":
                    channel = parts[3] if len(parts) > 3 else "?"
                    self.joined_channels.add(channel)
                    log(f"Joined {channel}")
                    # Ensure channel is in members cache
                    if channel not in self.channel_members:
                        self.channel_members[channel] = set()
                    # Add ourselves
                    self.channel_members[channel].add(IRC_NICK)

                elif code == "353":
                    # RPL_NAMREPLY — list of channel members
                    if len(parts) >= 5:
                        channel = parts[4]
                        names = " ".join(parts[5:]).lstrip(":")
                        nicks = set()
                        for n in names.split():
                            # Strip prefixes: @ % + ~ &
                            clean = n.lstrip("@%+~&")
                            if clean:
                                nicks.add(clean)
                        if channel not in self.channel_members:
                            self.channel_members[channel] = set()
                        self.channel_members[channel].update(nicks)
                        log(f"NAMES {channel}: {len(nicks)} nicks")
                        # If we requested NAMES for this channel, also send to main channels
                        if channel in self.needs_names:
                            self.needs_names.discard(channel)

                elif code == "433":
                    IRC_NICK = IRC_NICK.rstrip("_") + "_"
                    self.send_raw(f"NICK {IRC_NICK}")
                    log(f"Nick taken, trying {IRC_NICK}")

                elif code == "451":
                    # Not registered
                    log("Registration error")

        # Handle CTCP
        if "\x01" in line and "PRIVMSG" in line:
            # Strip CTCP
            line = line.replace("\x01", "")
            if "VERSION" in line:
                msg = self.parse_message(line)
                if msg:
                    log(f"CTCP VERSION from {msg['sender']}")
                    self.send_raw(f"NOTICE {msg['sender']} :\x01VERSION OWL Bot - Python IRC\x01")
                return

        # Track JOIN/PART/QUIT/NICK for member cache
        # Parse nick from :nick!user@host format
        try:
            if "!" in line and line.startswith(":"):
                sender_full = line.split(" ")[0]  # :nick!user@host
                sender_nick = sender_full.split("!")[0].lstrip(":")
            else:
                sender_nick = None
        except:
            sender_nick = None

        if sender_nick:
            upper_line = line.upper()
            if " JOIN " in upper_line or line.count("JOIN") >= 1 and "!" in line:
                # :nick!user@host JOIN :#channel
                ch = line.split("JOIN")[1].strip().lstrip(":")
                if ch.startswith("#"):
                    if ch not in self.channel_members:
                        self.channel_members[ch] = set()
                    self.channel_members[ch].add(sender_nick)
                    log(f"JOIN: {sender_nick} -> {ch}")
            elif " PART " in upper_line and "!" in line:
                # :nick!user@host PART #channel :reason
                ch = line.split("PART")[1].split(":")[0].strip()
                if ch in self.channel_members:
                    self.channel_members[ch].discard(sender_nick)
                    log(f"PART: {sender_nick} <- {ch}")
            elif " QUIT " in upper_line and "!" in line:
                for ch in self.channel_members:
                    self.channel_members[ch].discard(sender_nick)
                log(f"QUIT: {sender_nick}")
            elif " KICK " in upper_line and "!" in line:
                parts_q = line.split()
                if len(parts_q) >= 4:
                    ch = parts_q[2]
                    kicked = parts_q[3]
                    if ch in self.channel_members:
                        self.channel_members[ch].discard(kicked)
                        log(f"KICK: {kicked} <- {ch}")
            elif " NICK " in upper_line and "!" in line:
                # :oldnick!user@host NICK :newnick
                new_nick = line.split("NICK")[1].strip().lstrip(":")
                for ch in self.channel_members:
                    if sender_nick in self.channel_members[ch]:
                        self.channel_members[ch].discard(sender_nick)
                        self.channel_members[ch].add(new_nick)
                        log(f"NICK: {sender_nick} -> {new_nick} in {ch}")

        msg = self.parse_message(line)
        if msg and msg["sender"] != IRC_NICK:
            # Ignore messages from ourselves
            log(f"<{msg['sender']}> {msg['message']}")
            
            # Only process messages that mention us or are in channel
            is_direct = msg["message"].upper().startswith(IRC_NICK.upper()) or \
                        msg["message"].upper().startswith("OWL") or \
                        not msg["is_channel"]
            
            # Always process for now, agent can filter
            write_incoming(msg)

    def check_outgoing(self):
        """Check for messages to send back to IRC"""
        if not os.path.exists(OUTGOING_FILE):
            return
        
        try:
            lines = []
            with open(OUTGOING_FILE, "r") as f:
                lines = f.read().strip().split("\n")
            
            # Clear the file
            open(OUTGOING_FILE, "w").close()
            
            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    target = data.get("target", IRC_CHANNELS[0])
                    message = data.get("message", "")
                    msg_type = data.get("type", "privmsg")
                    if message:
                        if msg_type == "notice":
                            self.send_notice(target, message)
                            log(f"NOTICE -> {target}: {message[:50]}...")
                        elif msg_type == "notice_all":
                            # Send NOTICE to all channel members from cache
                            channel = target
                            exclude = set(data.get("exclude", []))
                            exclude.add(IRC_NICK)
                            members = self.channel_members.get(channel, set()).copy()
                            
                            if members:
                                sent = 0
                                for nick in members:
                                    if nick not in exclude:
                                        self.send_notice(nick, message)
                                        sent += 1
                                log(f"NOTICE ALL -> {channel}: {sent} nicks ({message[:30]}...)")
                            else:
                                # Cache empty: request NAMES and retry next tick
                                log(f"NOTICE ALL -> {channel}: cache empty, requesting NAMES")
                                self.request_names(channel)
                                # Re-append to outgoing so it retries after NAMES arrives
                                retry = {"target": channel, "message": message, "type": "notice_all", "exclude": list(exclude)}
                                with open(OUTGOING_FILE, "a") as rf:
                                    rf.write(json.dumps(retry) + "\n")
                        else:
                            self.send_msg(target, message)
                            log(f"-> {target}: {message[:50]}...")
                except json.JSONDecodeError:
                    pass
        except:
            pass

    def receive_loop(self):
        last_outgoing_check = time.time()
        
        while self.running and self.connected:
            try:
                data = self.sock.recv(4096).decode("utf-8", errors="replace")
                if not data:
                    log("Connection closed by server")
                    self.connected = False
                    break
                
                self.buffer += data
                while "\r\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\r\n", 1)
                    self.handle_line(line)
                    
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    log(f"Receive error: {e}")
                    self.connected = False
                break

            # Check outgoing queue periodically
            if time.time() - last_outgoing_check > 2:
                self.check_outgoing()
                last_outgoing_check = time.time()

    def run(self):
        if not self.acquire_lock():
            return

        try:
            if not self.connect():
                return
            self.receive_loop()
        except KeyboardInterrupt:
            log("Shutting down...")
        finally:
            self.running = False
            if self.sock:
                self.send_raw("QUIT :OWL Bot signing off")
                self.sock.close()
            self.release_lock()
            log("Disconnected.")


if __name__ == "__main__":
    bot = PTnetIRC()
    bot.run()
