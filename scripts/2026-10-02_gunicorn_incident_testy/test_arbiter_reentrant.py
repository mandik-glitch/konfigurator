"""Zkusebni instance gunicornu (verze z konfigurator venv) na vlastnim socketu, NE zivá služba.
Reprodukce incidentu 2026-10-02 17:37: hlavni vlákno arbitra je v zápisu logu na stderr (journald/rour pomalá -> blokující write),
v tu chvíli skončí worker -> SIGCHLD -> handle_chld loguje ze signal handleru -> RuntimeError reentrant -> 'Unhandled exception in main loop'
-> arbiter se vypne (exit -1), systemd ho po RestartSec=5 spustí znovu = výpadek ~20 s."""
import fcntl, os, signal, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
GUNI = "/opt/konfigurator/api/venv/bin/gunicorn"

def run(mode):
    """mode: none = bez opatreni | auto = api/gunicorn.conf.py v cwd uz pri startu (jako po restartu sluzby) | hup = soubor pridan az za behu a nacte se pri HUP (jako pri planovanem nasazeni)"""
    import shutil, tempfile
    wd = tempfile.mkdtemp(prefix="guni_", dir=HERE)
    shutil.copy(os.path.join(HERE, "wsgi_app.py"), wd)
    if mode == "auto": shutil.copy(os.path.join(HERE, "conf_fix.py"), os.path.join(wd, "gunicorn.conf.py"))
    sock = os.path.join(wd, "t.sock")

    r, w = os.pipe()
    fcntl.fcntl(w, 1031, 4096)                 # F_SETPIPE_SZ: nejmensi pipe, rychle se zaplni
    cmd = [GUNI, "--workers", "2", "--bind", "unix:t.sock", "--log-level", "info", "wsgi_app:app"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=w, close_fds=True, cwd=wd)
    os.close(w)
    fcntl.fcntl(r, fcntl.F_SETFL, os.O_NONBLOCK)
    # dokud ctu, bezi normalne
    def drain(t=1.0):
        out = b""; end = time.time() + t
        while time.time() < end:
            try: out += os.read(r, 65536)
            except BlockingIOError: time.sleep(0.05)
        return out
    log = drain(3.0)
    kids = lambda: [int(x) for x in subprocess.run(["pgrep", "-P", str(p.pid)], capture_output=True, text=True).stdout.split()]
    assert p.poll() is None and len(kids()) == 2, ("start", log[-300:])
    if mode == "hup":                                         # soubor pribude az ted; nacte se az pri prvnim HUP
        shutil.copy(os.path.join(HERE, "conf_fix.py"), os.path.join(wd, "gunicorn.conf.py"))
        os.kill(p.pid, signal.SIGHUP); time.sleep(2.5); drain(0.5)
    # zaplnit pipe: HUPy bez cteni; arbiter se zablokuje v write()
    for _ in range(12):
        os.kill(p.pid, signal.SIGHUP); time.sleep(0.4)
        if p.poll() is not None: break
    time.sleep(1.0)
    blocked = open("/proc/%d/wchan" % p.pid).read() if p.poll() is None else "mrtvy"
    # nyni skonci worker (SIGCHLD prijde, zatimco arbiter drzi buffered writer)
    for k in kids():
        try: os.kill(k, signal.SIGKILL)
        except ProcessLookupError: pass
    time.sleep(1.5)
    alive_before_drain = p.poll() is None
    tail = drain(2.0)
    time.sleep(1.0)
    tail += drain(1.0)
    alive = p.poll() is None
    served = None
    if alive:
        time.sleep(2.0)
        try:
            s = socket.socket(socket.AF_UNIX); s.settimeout(3); os.chdir(wd); s.connect("t.sock"); os.chdir(HERE); s.sendall(b"GET / HTTP/1.0\r\n\r\n"); served = s.recv(200).split(b"\r\n")[0]
        except Exception as e: served = repr(e)
    code = p.poll()
    if p.poll() is None:
        p.send_signal(signal.SIGTERM)
        try: p.wait(10)
        except Exception: p.kill()
    return dict(arbiter_wchan=blocked, alive_before_drain=alive_before_drain, alive_after=alive, exit_code=code, served=served,
                reentrant=b"reentrant call" in tail, unhandled=b"Unhandled exception in main loop" in tail)

if __name__ == "__main__":
    import collections
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for name, mode in (("BEZ opatreni (jako ostra sluzba)", "none"), ("api/gunicorn.conf.py od startu (restart sluzby)", "auto"), ("conf pridan za behu, nacte se pri HUP (planovane nasazeni)", "hup")):
        c = collections.Counter()
        for _ in range(n):
            r = run(mode)
            c["arbiter_zemrel"] += (not r["alive_after"]); c["reentrant_v_logu"] += r["reentrant"]; c["unhandled"] += r["unhandled"]; c["obsluhuje_po"] += (r["served"] == b"HTTP/1.0 200 OK")
        print("%-62s %d pokusu: %s" % (name, n, dict(c)), flush=True)
