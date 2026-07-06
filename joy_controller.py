#!/usr/bin/env python3
"""Joystick controller node for managing launch/stop scripts via gamepad combos.

Safety (防呆): LB+RB must be held simultaneously before any action key triggers.
- LB+RB+A    → start launch.sh
- LB+RB+B    → start stop.sh
- LB+RB+X    → kill launch.sh (autonomous mode)

Listens to both /joy and /joy_input so it works regardless of which pipeline
is active (raw or filtered).  Does NOT manage the joy_node driver itself —
that belongs to the system or stop.sh.  On shutdown it starts a joy_node so
the joystick stays usable.
"""

from __future__ import annotations
import os
import signal
import subprocess

import threading
try:
    import rospy
    from sensor_msgs.msg import Joy, JoyFeedback, JoyFeedbackArray
except ImportError:
    # --daemon 模式和 --exec 模式不需要 ROS
    rospy = None
    Joy = JoyFeedback = JoyFeedbackArray = None

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

COOLDOWN_S = 1.5  # minimum seconds between actions

# ---------------------------------------------------------------------------
# Normalise a raw Joy message into a plain dict of {alias: 0|1}.
# After this we never touch raw indices or axes again.
# ---------------------------------------------------------------------------

# Button index → alias, per joystick button-count
_BTN_MAPS = {
    11: {
        0: "A", 1: "B", 2: "X", 3: "Y",
        4: "LB", 5: "RB",
        6: "Back", 7: "Start",
        8: "Home", 9: "LS", 10: "RS",
    },
    16: {
        0: "A", 1: "B", 3: "X", 4: "Y",
        6: "LB", 7: "RB",
        10: "Back", 11: "Start",
        12: "Home", 13: "LS", 14: "RS",
    },
}

# D-pad is on axes[6] and axes[7]
AXIS_DPAD_X = 6  #  0=center,  1=left, -1=right
AXIS_DPAD_Y = 7  #  0=center,  1=up,   -1=down

# All known button / dpad aliases (for iteration / initialisation)
_BTN_ALIASES = ("A", "B", "X", "Y", "LB", "RB", "Back", "Start", "Home", "LS", "RS")
_DPAD_ALIASES = ("DpadUp", "DpadDown", "DpadLeft", "DpadRight")


def _make_alias_dict():
    """Return a dict with every known alias set to 0."""
    d = {}
    for a in _BTN_ALIASES + _DPAD_ALIASES:
        d[a] = 0
    return d


def _normalise(msg):
    """Convert a raw Joy message into a plain alias dict.

    Returns {alias: 0|1}  — e.g. {"A":1, "LB":1, "DpadUp":0, …}.
    """
    out = _make_alias_dict()

    # -- buttons --
    n = len(msg.buttons)
    btn_map = _BTN_MAPS.get(n, _BTN_MAPS[11])
    for i, v in enumerate(msg.buttons):
        name = btn_map.get(i)
        if name:
            out[name] = v

    # -- dpad --
    if len(msg.axes) > AXIS_DPAD_Y:
        x = msg.axes[AXIS_DPAD_X]
        y = msg.axes[AXIS_DPAD_Y]
        if x == 1.0:
            out["DpadLeft"] = 1
        elif x == -1.0:
            out["DpadRight"] = 1
        if y == 1.0:
            out["DpadUp"] = 1
        elif y == -1.0:
            out["DpadDown"] = 1

    return out


# ---------------------------------------------------------------------------
# Process-group wrapper
# ---------------------------------------------------------------------------
class ProcGroup:
    """A named subprocess started in its own session / process group."""

    def __init__(self, name, popen):
        self.name = name
        self.popen = popen

    @property
    def alive(self):
        return self.popen is not None and self.popen.poll() is None

    @property
    def pid(self):
        return self.popen.pid if self.popen else None

    def kill(self, timeout=5.0):
        """Send SIGINT to the process group, escalating to SIGKILL on timeout."""
        if self.popen is None or self.popen.poll() is not None:
            self.popen = None
            return
        try:
            pgid = os.getpgid(self.popen.pid)
            os.killpg(pgid, signal.SIGINT)
            self.popen.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            rospy.logwarn("%s did not exit after SIGINT, sending SIGKILL", self.name)
            try:
                os.killpg(pgid, signal.SIGKILL)
                self.popen.wait()
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        self.popen = None


def _kill_node(name):
    """Kill a ROS node by name via subprocess (safe to call before init_node)."""
    try:
        subprocess.run(
            ["rosnode", "kill", name],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Controller FSM
# ---------------------------------------------------------------------------
class JoyController:
    def __init__(self):
        # -- ensure only the latest instance survives --
        _kill_node("/joy_controller")

        rospy.init_node("joy_controller")

        # Start our own joy driver so the joystick is always available
        self._joy_dev = rospy.get_param("~joy_dev", "/dev/input/js0")
        self._joy_driver = self._start_joy_driver()

        # previous alias state for edge detection
        self._prev = None  # dict or None on first message
        self._last_stamp = None  # dedup across /joy + /joy_input

        self._cooldown_until = 0.0
        self._proc = {}  # name → ProcGroup

        # Listen to both raw and filtered joy topics so we always see input
        rospy.Subscriber("/joy", Joy, self._cb, queue_size=1)
        rospy.Subscriber("/joy_input", Joy, self._cb, queue_size=1)

        # Feedback publisher for joystick rumble
        self._rumble_pub = rospy.Publisher(
            "/joy/set_feedback", JoyFeedbackArray, queue_size=1)

        rospy.loginfo("joy_controller ready  topics=/joy, /joy_input")
        self._running = True
        # 启动 ferry 对接管道
        self._create_fifo()

    # ------------------------------------------------------------------
    # Per-key guard / edge helpers (all operate on alias dicts)
    # ------------------------------------------------------------------
    @staticmethod
    def _guard_held(state):
        """Safety: both LB and RB must be held."""
        return state.get("LB") == 1 and state.get("RB") == 1

    @staticmethod
    def _rising_keys(cur, prev):
        """Yield every alias that was 0 last frame and 1 this frame."""
        for name, v in cur.items():
            if v == 1 and prev.get(name) == 0:
                yield name

    @staticmethod
    def _is_guard_key(name):
        return name in ("LB", "RB")

    def _check_cooldown(self, key):
        now = rospy.Time.now().to_sec()
        if now < self._cooldown_until:
            rospy.loginfo_throttle(1, "cooldown active, ignoring %s", key)
            return False
        self._cooldown_until = now + COOLDOWN_S
        return True

    # ------------------------------------------------------------------
    # Subscriber callback
    # ------------------------------------------------------------------
    def _cb(self, msg):
        # dedup: skip if same stamp as last (both /joy and /joy_input may feed us)
        stamp = msg.header.stamp
        if self._last_stamp is not None and stamp == self._last_stamp:
            return
        self._last_stamp = stamp

        cur = _normalise(msg)

        if self._prev is None:
            self._prev = cur
            return

        # -- safety guard: LB+RB required for anything --
        if not self._guard_held(cur):
            self._prev = cur
            return

        # -- every newly-pressed key (excluding the guard keys themselves) --
        for key in self._rising_keys(cur, self._prev):
            if self._is_guard_key(key):
                continue
            if self._check_cooldown(key):
                self._dispatch(key)

        self._prev = cur

    # ------------------------------------------------------------------
    # Action dispatch — works purely on aliases
    # ------------------------------------------------------------------
    def _dispatch(self, key):
        rospy.loginfo("combo  LB+RB+%s", key)

        if key == "A":
            self._kill_script("stop.sh")
            self._launch_script("launch.sh")
        elif key == "B":
            self._kill_script("launch.sh")
            self._launch_script("stop.sh")
        elif key == "X":
            self._kill_launch()
        else:
            rospy.loginfo("key %s is not bound to any action", key)
            return

        self._rumble()

    # ------------------------------------------------------------------
    # Rumble feedback
    # ------------------------------------------------------------------
    def _rumble(self, duration=0.15, intensity=0.7):
        """Brief vibration pulse on both motors as action confirmation."""
        msg = JoyFeedbackArray()
        msg.array = [
            JoyFeedback(type=JoyFeedback.TYPE_RUMBLE, id=0, intensity=intensity),
            JoyFeedback(type=JoyFeedback.TYPE_RUMBLE, id=1, intensity=intensity),
        ]
        self._rumble_pub.publish(msg)
        threading.Timer(duration, lambda: self._rumble_pub.publish(
            JoyFeedbackArray(array=[
                JoyFeedback(type=JoyFeedback.TYPE_RUMBLE, id=0, intensity=0.0),
                JoyFeedback(type=JoyFeedback.TYPE_RUMBLE, id=1, intensity=0.0),
            ]))).start()

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------
    def _launch_script(self, name):
        """Start a script from SCRIPTS_DIR if it isn't already running."""
        existing = self._proc.get(name)
        if existing is not None and existing.alive:
            rospy.logwarn("%s is already running (pid=%d) — skipping", name, existing.pid)
            return

        path = os.path.join(SCRIPTS_DIR, name)
        if not os.path.isfile(path):
            rospy.logerr("script not found: %s", path)
            return

        log = open("/tmp/joy_%s.log" % name, "w")
        rospy.loginfo("starting %s  (log: %s)", path, log.name)
        proc = subprocess.Popen(
            ["bash", path],
            preexec_fn=os.setsid,
            stdout=log, stderr=log,
            env=os.environ.copy(),
        )
        pg = ProcGroup(name, proc)
        self._proc[name] = pg
        rospy.loginfo("%s started  pid=%d  pgid=%d", name, proc.pid, os.getpgid(proc.pid))

    def _kill_script(self, name):
        """Kill a named script if it is running."""
        pg = self._proc.pop(name, None)
        if pg is not None and pg.alive:
            rospy.loginfo("killing %s (pid=%d)", name, pg.pid)
            pg.kill()
            rospy.loginfo("%s killed", name)

    def _kill_launch(self):
        """Kill launch.sh (autonomous mode) only. Leaves teleop untouched."""
        pg = self._proc.get("launch.sh")
        if pg is not None and pg.alive:
            self._kill_script("launch.sh")
        else:
            rospy.loginfo("launch.sh is not running")

    def _start_joy_driver(self):
        """Start joy_node_ctrl so the joystick is always available."""
        try:
            proc = subprocess.Popen(
                ["rosrun", "joy", "joy_node",
                 "__name:=joy_node_ctrl",
                 "_dev:=" + self._joy_dev,
                 "_deadzone:=1e-3",
                 "_autorepeat_rate:=0",
                 "_coalesce_interval:=0.05"],
                preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            pg = ProcGroup("joy_node_ctrl", proc)
            rospy.loginfo("joy_node_ctrl started  pid=%d  device=%s", proc.pid, self._joy_dev)
            return pg
        except Exception as e:
            rospy.logerr("failed to start joy_node_ctrl: %s", e)
            return None

    


    
    # ------------------------------------------------------------------
    # Ferry 对接管道 — 从命名管道接受远程 launch/stop 指令
    # ferryd daemon 写入 /tmp/ferry_joy_cmd, 本线程读取并执行。
    # ------------------------------------------------------------------
    _FERRY_FIFO = "/tmp/ferry_joy_cmd"

    def _create_fifo(self):
        """创建命名管道并启动读取线程"""
        import os as _os
        import stat as _st
        import threading as _th
        import select as _sel

        # 确保 FIFO 存在
        try:
            if not _os.path.exists(self._FERRY_FIFO):
                _os.mkfifo(self._FERRY_FIFO, 0o644)
        except Exception as e:
            rospy.logwarn("无法创建 FIFO %s: %s", self._FERRY_FIFO, e)
            return

        def _reader():
            while self._running:
                try:
                    fd = _os.open(self._FERRY_FIFO, _os.O_RDONLY | _os.O_NONBLOCK)
                    poll = _sel.poll()
                    poll.register(fd, _sel.POLLIN)
                    while self._running:
                        events = poll.poll(1000)  # 1s timeout
                        if not events:
                            continue
                        data = _os.read(fd, 4096).decode("utf-8").strip()
                        if not data:
                            continue
                        action = data.splitlines()[0].strip()
                        rospy.loginfo("FIFO 收到指令: %s", action)
                        if action == "launch":
                            self._kill_script("stop.sh")
                            self._launch_script("launch.sh")
                        elif action == "stop":
                            self._kill_script("launch.sh")
                            self._launch_script("stop.sh")
                        else:
                            rospy.logwarn("FIFO 未知指令: %s", action)
                except Exception as e:
                    if self._running:
                        rospy.logwarn_throttle(10, "FIFO 错误: %s", e)
                    _th.Event().wait(1)
                finally:
                    try:
                        _os.close(fd)
                    except Exception:
                        pass

        t = _th.Thread(target=_reader, daemon=True)
        t.start()
        rospy.loginfo("ferry 对接管道已启动: %s", self._FERRY_FIFO)

    def shutdown(self):
        """Clean up children and driver on exit."""
        rospy.loginfo("shutting down, cleaning up subprocesses…")
        for name, pg in list(self._proc.items()):
            if pg is not None and pg.alive:
                rospy.loginfo("killing %s (pid=%d)", name, pg.pid)
                pg.kill()
        if self._joy_driver is not None and self._joy_driver.alive:
            rospy.loginfo("stopping joy driver (pid=%d)", self._joy_driver.pid)
            self._joy_driver.kill()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------






class FifoDaemon:
    """TCP 守护模式: 监听端口 19878 (launch/stop), 可选 ROS 手柄支持。
    ferryd daemon 通过 TCP JSON 发送指令, 手柄通过 ROS topic 输入。
    """

    def __init__(self):
        import os as _os
        self.SCRIPTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
        self._procs = {}
        self._running = True
        # ROS 手柄状态 (可选)
        self._prev = None
        self._last_stamp = None
        self._cooldown_until = 0.0

    def _launch_script(self, name):
        import os as _os
        import subprocess as _sp
        import signal as _sig

        path = _os.path.join(self.SCRIPTS_DIR, name)
        if not _os.path.isfile(path):
            print("脚本不存在:", path)
            return

        log = open("/tmp/ferry_%s.log" % name, "w")
        proc = _sp.Popen(
            ["bash", path],
            preexec_fn=_os.setsid,
            stdout=log, stderr=log,
            env=_os.environ.copy(),
        )
        self._procs[name] = proc
        print("已启动: %s (pid=%d)" % (name, proc.pid))

    def _kill_script(self, name):
        import os as _os
        import signal as _sig
        proc = self._procs.pop(name, None)
        if proc is not None and proc.poll() is None:
            try:
                pgid = _os.getpgid(proc.pid)
                _os.killpg(pgid, _sig.SIGINT)
                proc.wait(timeout=5)
            except Exception:
                pass
        print("已停止: %s" % name)

    def _run_tcp(self):
        """TCP 服务循环 (daemon 线程运行)."""
        import socket as _sk
        import json as _js
        import threading as _th

        srv = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
        srv.setsockopt(_sk.SOL_SOCKET, _sk.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", 19878))
        except OSError as e:
            print("TCP 端口 19878 绑定失败: %s" % e)
            return
        srv.listen(5)
        srv.settimeout(1.0)
        print("ferry daemon: TCP 监听中 (127.0.0.1:19878)")

        def _handle(conn):
            try:
                data = conn.recv(4096)
                msg = _js.loads(data.decode())
                action = msg.get("action", "")
                print("TCP 指令: %s" % action)
                if action == "launch":
                    self._kill_script("stop.sh")
                    self._launch_script("launch.sh")
                elif action == "stop":
                    self._kill_script("launch.sh")
                    self._launch_script("stop.sh")
                conn.sendall(_js.dumps({"ok": True}).encode())
            except Exception as e:
                try:
                    conn.sendall(_js.dumps({"ok": False, "error": str(e)}).encode())
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        while self._running:
            try:
                conn, addr = srv.accept()
                _th.Thread(target=_handle, args=(conn,), daemon=True).start()
            except _sk.timeout:
                continue
            except Exception as e:
                print("TCP server error:", e)
                continue

    def _joy_cb(self, msg):
        """ROS 手柄回调: LB+RB+A/B/X 等效于 TCP 指令."""
        import rospy

        stamp = msg.header.stamp
        if self._last_stamp is not None and stamp == self._last_stamp:
            return
        self._last_stamp = stamp

        cur = _normalise(msg)

        if self._prev is None:
            self._prev = cur
            return

        if not (cur.get("LB") == 1 and cur.get("RB") == 1):
            self._prev = cur
            return

        now = rospy.Time.now().to_sec()
        for key, v in cur.items():
            if v == 1 and self._prev.get(key) == 0:
                if key in ("LB", "RB"):
                    continue
                if now < self._cooldown_until:
                    continue
                self._cooldown_until = now + COOLDOWN_S
                print("ferry daemon: combo LB+RB+%s" % key)
                if key == "A":
                    self._kill_script("stop.sh")
                    self._launch_script("launch.sh")
                elif key == "B":
                    self._kill_script("launch.sh")
                    self._launch_script("stop.sh")
                elif key == "X":
                    self._kill_script("launch.sh")

        self._prev = cur

    def _try_init_ros(self):
        """尝试启用 ROS 手柄模式 (失败不影响 TCP 模式)."""
        try:
            import rospy
            from sensor_msgs.msg import Joy
        except ImportError:
            print("ferry daemon: rospy 不可用, 仅 TCP 模式")
            return

        try:
            rospy.init_node("joy_controller_daemon", anonymous=True)
            rospy.Subscriber("/joy", Joy, self._joy_cb, queue_size=1)
            rospy.Subscriber("/joy_input", Joy, self._joy_cb, queue_size=1)
            import threading as _th
            _th.Thread(target=rospy.spin, daemon=True).start()
            print("ferry daemon: ROS 手柄模式已启用")
        except Exception as e:
            print("ferry daemon: ROS 初始化失败: %s (仅 TCP 模式)" % e)

    # ── FIFO 对接 ──
    # ferryd 通过写入 /tmp/ferry_joy_cmd 来发送 launch/stop 指令,
    # 和手柄走同一个 self._procs, 确保状态一致。

    _FERRY_FIFO = "/tmp/ferry_joy_cmd"

    def _create_fifo(self):
        import os as _os
        import stat as _st
        import threading as _th

        try:
            if not _os.path.exists(self._FERRY_FIFO):
                _os.mkfifo(self._FERRY_FIFO, 0o644)
        except Exception as e:
            print("无法创建 FIFO %s: %s" % (self._FERRY_FIFO, e))
            return

        def _reader():
            import select as _sel
            while self._running:
                try:
                    fd = _os.open(self._FERRY_FIFO, _os.O_RDONLY | _os.O_NONBLOCK)
                    poll = _sel.poll()
                    poll.register(fd, _sel.POLLIN)
                    while self._running:
                        events = poll.poll(1000)
                        if not events:
                            continue
                        data = _os.read(fd, 4096)
                        if not data:
                            continue
                        action = data.decode("utf-8").strip().splitlines()[0].strip()
                        if not action:
                            continue
                        print("FIFO 指令: %s" % action)
                        if action == "launch":
                            self._kill_script("stop.sh")
                            self._launch_script("launch.sh")
                        elif action == "stop":
                            self._kill_script("launch.sh")
                            self._launch_script("stop.sh")
                        else:
                            print("FIFO 未知指令: %s" % action)
                except Exception as e:
                    if self._running:
                        print("FIFO 错误: %s" % e)
                    _th.Event().wait(1)
                finally:
                    try:
                        _os.close(fd)
                    except Exception:
                        pass

        t = _th.Thread(target=_reader, daemon=True)
        t.start()
        print("ferry daemon: FIFO 已创建 %s" % self._FERRY_FIFO)

    def run(self):
        """主入口: TCP 守护 + FIFO + 可选 ROS 手柄."""
        import threading as _th
        import time as _time

        # 创建 FIFO 并启动读取线程 (ferry 指令)
        self._create_fifo()

        # 启动 TCP 服务器 (daemon 线程, 兼容旧版 ferryd)
        _th.Thread(target=self._run_tcp, daemon=True).start()

        # 尝试启用 ROS 手柄
        self._try_init_ros()

        # 主循环保持进程存活
        while self._running:
            _time.sleep(1)
# ── 入口 ──
 # --daemon: TCP 守护 + 可选 ROS 手柄
import sys as _sys
if len(_sys.argv) > 1 and _sys.argv[1] == "--daemon":
    FifoDaemon().run()
    _sys.exit(0)



# ── CLI: 远程 launch/stop 入口 ────────────────────────────────────
# 用法:
#   python joy_controller.py                     # ROS 手柄节点
#   python joy_controller.py launch [targets..]   # 远程启动机器人
#   python joy_controller.py stop  [targets..]    # 远程停止机器人
# SSH 到目标机器后通过 ferry 对接接口 (TCP 19878) 发送指令。

import sys as _sys

_FERRY_PORT = 19878

def _resolve_targets(targets):
    """解析目标列表 [(name, ip), ...]"""
    cfg_path = os.path.join(os.path.dirname(__file__), "ferry", "config.yaml")
    robots = {}
    if os.path.exists(cfg_path):
        try:
            import yaml
            with open(cfg_path) as f:
                robots = (yaml.safe_load(f) or {}).get("robots", {})
        except Exception:
            pass
    if not targets:
        targets = list(robots.keys())
    resolved = []
    for t in targets:
        if t in robots and robots[t].get("ip"):
            resolved.append((t, robots[t]["ip"]))
        else:
            name = t
            for rn, ri in robots.items():
                if ri.get("ip") == t:
                    name = rn
                    break
            resolved.append((name, t))
    return resolved


def _send_ferry_command(ip: str, action: str) -> tuple[bool, str]:
    """SSH 到目标机器人, 通过 TCP 发送 JSON 指令到本地 joy_controller daemon."""
    import subprocess as _sp
    import json as _js
    try:
        payload = _js.dumps({"action": action})
        # SSH 后用 python 向本地 TCP 19878 发送 JSON
        r = _sp.run(
            ["ssh", "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ConnectTimeout=5",
             "nvidia@" + ip,
             "python3", "-c",
             "import socket,sys;" +
             "s=socket.socket();s.settimeout(10);" +
             "s.connect(('127.0.0.1',19878));" +
             "s.sendall(sys.stdin.buffer.read());" +
             "print(s.recv(4096).decode());s.close()"],
            input=payload, capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and '"ok": true' in r.stdout:
            return True, ""
        return False, (r.stderr.strip() or r.stdout.strip() or "SSH/连接失败")
    except Exception as e:
        return False, str(e)


def main_cli():
    import sys as _sys
    if len(_sys.argv) < 2:
        print("用法: python joy_controller.py {launch|stop} [target IP/名称...]")
        print("      python joy_controller.py                          # ROS 手柄节点")
        return

    command = _sys.argv[1]
    if command not in ("launch", "stop"):
        print(f"未知指令: {command}")
        return

    targets = _resolve_targets(_sys.argv[2:])
    if not targets:
        print("未找到目标机器人")
        return

    print(f"\n  {command} → {len(targets)} 台机器人\n")
    for name, ip in targets:
        ok, err = _send_ferry_command(ip, command)
        mark = "✓" if ok else "✗"
        print(f"  {name} ({ip}) {mark}", end="")
        if not ok and err:
            print(f"  {err}", end="")
        print()


if __name__ == "__main__":
    # 有 CLI 参数时走远程控制
    if len(_sys.argv) > 1 and _sys.argv[1] in ("launch", "stop"):
        main_cli()
        sys.exit(0)
    # 检查 ROS
    if rospy is None:
        print("错误: rospy 不可用。请先 source ROS setup.bash，或使用 --daemon 模式。", file=sys.stderr)
        sys.exit(1)
    # 正常启动 ROS 手柄节点
    ctrl = JoyController()
    rospy.on_shutdown(ctrl.shutdown)
    rospy.spin()
