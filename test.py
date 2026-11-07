"""Verify the packaged Mailpit service in a dedicated, empty Linux Docker VM."""
import base64
import hashlib
import json
import os
from email.message import EmailMessage
from pathlib import Path
import secrets
import smtplib
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(value, label):
    if not value:
        raise RuntimeError(label)
    print("PASS", label, flush=True)


def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def http(path, password=None):
    request = Request("http://127.0.0.1:18025" + path)
    if password is not None:
        basic = base64.b64encode(("tester:" + password).encode()).decode()
        request.add_header("Authorization", "Basic " + basic)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, b""


def wait_for(condition, label):
    for _ in range(90):
        try:
            if condition():
                check(True, label)
                return
        except (ConnectionError, URLError):
            pass
        time.sleep(1)
    raise RuntimeError(label)


def run(package):
    check(sys.platform == "linux" and os.geteuid() == 0 and not output("docker", "ps", "-aq"),
          "dedicated empty Linux Docker engine")
    print("Archive SHA256", hashlib.sha256(package.read_bytes()).hexdigest(), flush=True)
    with tempfile.TemporaryDirectory(prefix="mailpit-acceptance-") as tmp:
        root = Path(tmp)
        with tarfile.open(package) as archive:
            (root / "docker-compose.yml").write_bytes(archive.extractfile("docker-compose.yml").read())
        for name in ("config", "data"):
            (root / name).mkdir(mode=0o700)
            os.chown(root / name, 1000, 1000)

        def compose(*args):
            return output("docker", "compose", "-p", "tosmailpittest", *args, cwd=root)

        def state():
            identifier = compose("ps", "-aq")
            return json.loads(output("docker", "inspect", identifier))[0]

        password_file = root / "config/auth.htpasswd"

        def write_password_file(content):
            password_file.write_text(content)
            password_file.chmod(0o600)
            os.chown(password_file, 1000, 1000)

        def failed_closed():
            info = state()
            try:
                if http("/api/v1/messages")[0] != 401:
                    raise RuntimeError("unconfigured API exposed")
            except (ConnectionError, URLError):
                pass
            return info["State"]["ExitCode"] != 0 and info["State"]["Status"] in ("exited", "restarting")

        password = secrets.token_urlsafe(32)
        try:
            for label in ("missing", "whitespace-only"):
                if label == "whitespace-only":
                    write_password_file("  \n")
                compose("up", "-d")
                wait_for(failed_closed, label + " credential file prevents startup")
                compose("down")

            digest = subprocess.check_output(["openssl", "passwd", "-6", "-stdin"],
                                             input=password + "\n", text=True).strip()
            write_password_file("tester:" + digest + "\n")
            compose("up", "-d")
            api = "/api/v1/messages"
            wait_for(lambda: http(api, password)[0] == 200, "configured API starts with unique credentials")
            for route in ("/", api):
                check(http(route)[0] == 401 and http(route, "incorrect")[0] == 401,
                      "anonymous and invalid credentials rejected on " + route)
            code, page = http("/", password)
            check(code == 200 and b"<script" in page and b"mailpit" in page.lower(), "authenticated Mailpit UI")
            info = state()
            image = json.loads(output("docker", "image", "inspect", info["Image"]))[0]
            check((image["Os"], image["Architecture"]) == ("linux", "amd64"), "running Linux amd64 image")
            print("Running image", info["Config"]["Image"], flush=True)
            status = Path(f'/proc/{info["State"]["Pid"]}/status').read_text().splitlines()
            for field in ("Uid", "Gid"):
                check(next(s.split()[1:] for s in status if s.startswith(field + ":")) == ["1000"] * 4,
                      "running " + field + " 1000")
            check("NoNewPrivs:\t1" in status and
                  int(next(s.split()[1] for s in status if s.startswith("CapEff:")), 16) == 0 and
                  info["HostConfig"]["ReadonlyRootfs"] and not info["HostConfig"]["Privileged"],
                  "read-only root, unprivileged, no capabilities or privilege escalation")
            mounts = {m["Destination"]: m for m in info["Mounts"]}
            check(not mounts["/config"]["RW"] and mounts["/data"]["RW"], "read-only configuration, writable data")
            check(info["NetworkSettings"]["Ports"]["1025/tcp"] == [{"HostIp": "127.0.0.1", "HostPort": "11025"}],
                  "SMTP published only on guest loopback")
            check(not any(item.startswith(("MP_SMTP_RELAY_", "MP_SMTP_FORWARD_")) for item in info["Config"]["Env"])
                  and not any("relay" in arg or "forward" in arg for arg in (info["Config"]["Cmd"] or [])),
                  "no SMTP relay or forwarding configured")

            message = EmailMessage()
            message["From"], message["To"] = "sender@example.invalid", "sink@example.invalid"
            message["Subject"] = "Mailpit acceptance " + secrets.token_hex(8)
            message.set_content("Synthetic local test body.")
            with smtplib.SMTP("127.0.0.1", 11025, timeout=8) as client:
                check(not client.send_message(message), "loopback SMTP accepted synthetic message without login")

            def messages():
                return json.loads(http(api, password)[1])["messages"]

            wait_for(lambda: any(m["Subject"] == message["Subject"] for m in messages()), "message visible in API")
            message_id = next(m["ID"] for m in messages() if m["Subject"] == message["Subject"])

            def same_message():
                code, body = http("/api/v1/message/" + message_id, password)
                if code != 200:
                    return False
                result = json.loads(body)
                return result["Subject"] == message["Subject"] and "Synthetic local test body." in result["Text"]

            check(same_message(), "stored subject and body match")
            compose("stop")
            compose("start")
            wait_for(same_message, "same message survives stop and start")
            compose("down")
            database = Path(mounts["/data"]["Source"])
            check(any(f.is_file() and f.stat().st_size > 0 for f in database.iterdir()), "files persist on data bind")
            compose("up", "-d")
            wait_for(same_message, "same message and credentials survive container recreation")
        finally:
            compose("down")
    check(not root.exists() and not output("docker", "ps", "-aq"), "test data, credentials and containers cleaned")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
