#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import shutil
import tempfile
import urllib.request
from pathlib import Path

def enable_ansi():
    if os.name == "nt":
        try:
            os.system("")
        except Exception:
            pass

enable_ansi()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
ROOT = HERE.parent
IS_SANDBOX = ROOT.name == ".gemini" and (ROOT / "shell_gpt" / ".sgptrc").exists()

if IS_SANDBOX:
    CFG_PATH = ROOT / "shell_gpt" / ".sgptrc"
    PATCH_DIR = ROOT / "sgpt"
else:
    home = Path.home()
    CFG_PATH = home / ".config" / "shell_gpt" / ".sgptrc"
    PATCH_DIR = None

MODELS = {
    "1": ("@cf/meta/llama-4-scout-17b-16e-instruct", "Llama 4 Scout 17B  (fast, balanced)"),
    "2": ("@cf/meta/llama-3.3-70b-instruct-fp8-fast", "Llama 3.3 70B      (higher quality)"),
    "3": ("@cf/qwen/qwen2.5-coder-32b-instruct",      "Qwen2.5 Coder 32B  (best for code)"),
    "4": ("@cf/meta/llama-3.1-8b-instruct-fp8",       "Llama 3.1 8B       (lightweight)"),
    "5": ("@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", "DeepSeek R1 32B   (reasoning)"),
}
OPENAI_MODELS = {
    "1": ("gpt-4o",                                 "OpenAI GPT-4o      (balanced)"),
    "2": ("gpt-4o-mini",                            "OpenAI GPT-4o mini (fast, cheap)"),
    "3": ("gpt-4.1",                                "OpenAI GPT-4.1     (higher quality)"),
    "4": ("gpt-4.1-mini",                           "OpenAI GPT-4.1 mini"),
    "5": ("o3-mini",                                "OpenAI o3-mini     (reasoning)"),
}
# Free providers via /pollinations skill — curated + fetched live from gen.pollinations.ai
# Pollinations free models are OpenAI-compatible at https://gen.pollinations.ai/v1
# PowerBrain free at https://powerbrainai.com (via tgpt powerbrain provider: https://powerbrainai.com/app/backend/api/api.php)
POLLINATIONS_MODELS = {
    "1": ("openai", "Pollinations OpenAI (free)"),
    "2": ("openai-fast", "Pollinations OpenAI Fast (free)"),
    "3": ("qwen/qwen3.8-flash", "Qwen3.8 Flash (free, 1M ctx)"),
    "4": ("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash (free)"),
}
# Fallback curated list from pollinations-free-models skill (will be refreshed live)
POLLINATIONS_CURATED = [
    "Spit-fires/muse-glimmer",
    "chigwell/llm7-fast",
    "YoannDev90/muse-glimmer-30b:free",
    "YoannDev90/diffusiongemma-26b-a4b-it:free",
    "vendouple/muse-glimmer-30b:free",
    "vendouple/gpt-5.6-sol:free",
    "YoannDev90/poolside-laguna-s-2.1:free",
    "AkshayCoder48/cohere-north-mini-code:free",
    "AkshayCoder48/poolside-laguna-s-2.1:free",
    "YoannDev90/laguna-s-2.1:free",
]
CF_MODES = {
    "1": ("Workers AI (via AI Gateway)", "workers-ai"),
    "2": ("AI Gateway (custom / BYOK)", "aig"),
}
PROVIDERS = {
    "1": ("Cloudflare AI Gateway", None),
    "2": ("OpenAI", "default"),
    "3": ("Ollama (local)", "http://localhost:11434/v1"),
    "4": ("Pollinations (free)", "https://gen.pollinations.ai/v1"),
    "5": ("PowerBrain (free)", "https://powerbrainai.com/app/backend/api/api.php"),
    "6": ("Custom", None),
}

def cloudflare_base(account_id, gateway="acode", mode="workers-ai"):
    if mode == "aig":
        return "https://gateway.ai.cloudflare.com/v1/%s/%s/" % (account_id.strip(), gateway.strip())
    return "https://gateway.ai.cloudflare.com/v1/%s/%s/workers-ai/v1" % (account_id.strip(), gateway.strip())

def parse_cloudflare_base(url):
    u = (url or "").rstrip("/")
    parts = u.split("/")
    if "gateway.ai.cloudflare.com" in u and len(parts) >= 6:
        mode = "aig" if "workers-ai" not in u else "workers-ai"
        return parts[4], parts[5], mode
    return "", "", "workers-ai"

def fetch_pollinations_models(live=False):
    """Fetch pollinations free models: curated + live from /pollinations skill endpoint.
    If live=True, hits https://gen.pollinations.ai/models and filters community/:free.
    Skill source: ~/.config/opencode/skills/pollinations-free-models/SKILL.md
    """
    if live:
        try:
            import urllib.request, json
            with urllib.request.urlopen("https://gen.pollinations.ai/models", timeout=8) as r:
                data = json.load(r)
                if isinstance(data, dict) and "data" in data:
                    data = data["data"]
                free = []
                for m in data:
                    name = m.get("name","")
                    if m.get("community") or ":free" in name:
                        free.append((name, f"{m.get('title','')}  ({name})"))
                    elif "pollinations" in name.lower() and not m.get("paid_only"):
                        free.append((name, f"{m.get('title','')}  ({name})"))
                if free:
                    seen=set()
                    out={}
                    idx=1
                    for nid, disp in free:
                        if nid not in seen and "/" in nid:
                            seen.add(nid)
                            out[str(idx)] = (nid, disp[:50])
                            idx+=1
                            if idx>20: break
                    if out:
                        return out
        except Exception as e:
            pass
    # Curated fallback from skill file + POLLINATIONS_CURATED
    try:
        skill_path = Path.home() / ".config" / "opencode" / "skills" / "pollinations-free-models" / "SKILL.md"
        if skill_path.exists():
            import re
            txt = skill_path.read_text()
            # Parse markdown table lines: | `model-id` | ...
            ids=[]
            for line in txt.splitlines():
                line=line.strip()
                if not line.startswith("| `"): continue
                m=re.match(r"\|\s*`([^`]+)`", line)
                if m:
                    mid=m.group(1).strip()
                    if "/" in mid:
                        ids.append(mid)
            # Filter to curated if still too many
            if ids:
                # Prefer curated order
                curated_set=set(POLLINATIONS_CURATED)
                # Put curated first, then others
                ordered=[]
                for mid in POLLINATIONS_CURATED:
                    if mid in ids:
                        ordered.append(mid)
                for mid in ids:
                    if mid not in ordered:
                        ordered.append(mid)
                out={}
                for idx, mid in enumerate(ordered[:12], start=1):
                    out[str(idx)] = (mid, f"{mid}")
                return out
    except Exception:
        pass
    # Final fallback: POLLINATIONS_CURATED
    out={}
    for idx, mid in enumerate(POLLINATIONS_CURATED, start=1):
        out[str(idx)] = (mid, f"{mid} (curated)")
    return out

def active_models():
    base = read_cfg().get("API_BASE_URL", "")
    if "pollinations" in base or "gen.pollinations" in base:
        # Return live-fetched if possible
        live = fetch_pollinations_models(live=False)
        return live or POLLINATIONS_MODELS
    if "powerbrain" in base:
        return {"1": ("gpt-5", "PowerBrain GPT-5 (free)"), "2": ("gpt-5-mini", "PowerBrain Mini (free)")}
    if "workers-ai" in base:
        return MODELS
    if base.startswith("default") or "openai" in base or "api.openai" in base:
        return OPENAI_MODELS
    return MODELS

def test_connection(base, key, model):
    if not key:
        return c("No API key set.", YELLOW)
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.load(r)
            msg = data["choices"][0]["message"]["content"]
            return c("CONNECTED - model replied: %r" % (msg or "",), GREEN)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        return c("FAILED HTTP %s: %s" % (e.code, detail[:200]), RED)
    except Exception as e:
        return c("FAILED: %s" % e, RED)

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def c(text, color):
    return color + text + RESET

def clear():
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()

def read_cfg():
    cfg = {}
    if CFG_PATH.exists():
        for line in CFG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def write_cfg(cfg):
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in cfg.items():
        lines.append("%s=%s" % (k, v))
    CFG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

def set_cfg_key(key, value):
    cfg = read_cfg()
    if value is None:
        cfg.pop(key, None)
    else:
        cfg[key] = value
    write_cfg(cfg)

def get_editor():
    if os.name == "nt":
        return "notepad"
    for e in ("EDITOR", "VISUAL"):
        if os.environ.get(e):
            return os.environ[e]
    for ed in ("nano", "vi", "vim"):
        if shutil.which(ed):
            return ed
    return "vi"

def sgpt_env():
    env = dict(os.environ)
    for k, v in read_cfg().items():
        env.setdefault(k, v)
    if PATCH_DIR is not None:
        env["PYTHONPATH"] = str(PATCH_DIR)
    env["PYTHONUNBUFFERED"] = "1"
    return env

def run_sgpt(args, stream=True):
    cmd = [sys.executable, "-m", "sgpt"] + args
    try:
        if stream:
            proc = subprocess.run(cmd, env=sgpt_env())
        else:
            proc = subprocess.run(cmd, env=sgpt_env(), capture_output=True, text=True)
        return proc.returncode, proc.stdout if not stream else ""
    except FileNotFoundError:
        print(c("shell-gpt (sgpt) is not installed. Run: python3 -m pip install shell-gpt", RED))
        return 1, ""
    except Exception as exc:
        print(c("error: %s" % exc, RED))
        return 1, ""

def run_usage():
    script = HERE / "sgpt-usage.py"
    if not script.exists():
        print(c("sgpt-usage.py not found next to this script.", RED))
        return
    subprocess.run([sys.executable, str(script)])

def render(title, items, idx, footer=None):
    clear()
    width = max(len(title), *(len(str(i[0])) + 3 + len(str(i[1])) for i in items), len(footer or ""))
    width = min(width + 4, 90)
    border = "\u2500" * (width - 2)
    print(BOLD + "\u250c" + border + "\u2510" + RESET)
    print(BOLD + "\u2502" + (" " + title).ljust(width - 1) + "\u2502" + RESET)
    print(BOLD + "\u251c" + border + "\u2524" + RESET)
    for n, (label, hint) in enumerate(items):
        marker = ">" if n == idx else " "
        style = BOLD if n == idx else ""
        line = "%s %s %s" % (marker, label, DIM + hint + RESET) if hint else "%s %s" % (marker, label)
        pad = width - len(line) - 3
        print(style + "\u2502 " + line + (" " * max(pad, 0)) + " \u2502" + RESET)
    print(BOLD + "\u2514" + border + "\u2518" + RESET)
    if footer:
        print(footer)
    print(DIM + "arrows/numbers: move   enter: select   q/esc: back" + RESET)

def menu(title, items, footer=None):
    idx = 0
    while True:
        render(title, items, idx, footer)
        key = read_key()
        if key == "up":
            idx = (idx - 1) % len(items)
        elif key == "down":
            idx = (idx + 1) % len(items)
        elif key == "enter":
            return idx
        elif key in ("q", "esc"):
            return None
        elif key.isdigit() and int(key) < len(items):
            return int(key)

def read_key():
    if os.name == "nt":
        try:
            import msvcrt
            first = msvcrt.getwch()
            if first in ("\x00", "\xe0"):
                second = msvcrt.getwch()
                if second == "H":
                    return "up"
                if second == "P":
                    return "down"
                return ""
            if first in ("\r", "\n"):
                return "enter"
            if first in ("q", "Q"):
                return "q"
            if first == "\x1b":
                return "esc"
            return first
        except Exception:
            return input()
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "up"
                if seq == "[B":
                    return "down"
                return "esc"
            if ch in ("\r", "\n"):
                return "enter"
            if ch in ("q", "Q"):
                return "q"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        return input()

def text_input(prompt, default=None):
    suffix = (" [%s]" % default) if default else ""
    try:
        if os.name == "nt":
            val = input(prompt + suffix + ": ")
        else:
            val = input(prompt + suffix + ": ")
    except EOFError:
        return default
    return val.strip() if val.strip() else default

def wait_enter():
    try:
        input(DIM + "press enter to continue..." + RESET)
    except EOFError:
        pass

def _run_shell_and_execute(prompt, chat_id=None):
    # Helper: generate shell command via sgpt --shell --no-interaction (capture), show it, and offer execute
    # Returns the generated command string or None
    args=[prompt, "--shell", "--no-cache", "--no-interaction"]
    if chat_id:
        args+=["--chat", chat_id]
    res = run_sgpt(args, stream=False)
    if isinstance(res, tuple):
        rc=res[0]
        out=res[1] if len(res)>1 else ""
    else:
        rc, out = res, ""
    # sgpt shell with --no-interaction prints command to stdout, but may include warning in stderr (already not captured when stream=False)
    # run_sgpt with stream=False captures stdout only; need to ensure we get command
    # If out is empty, try to run again without --no-interaction and handle Execute prompt manually? But --no-interaction is correct for capture.
    cmd=(out or "").strip()
    # Remove possible markdown fences and extra lines (keep last non-empty line that looks like shell command)
    # sgpt shell output is usually single line command, but we clean
    if not cmd:
        # Fallback: try with plain --shell and capture (may include Execute prompt, so strip that)
        res2 = run_sgpt([prompt, "--shell", "--no-cache"], stream=False)
        if isinstance(res2, tuple):
            rc2=res2[0]
            out2=res2[1] if len(res2)>1 else ""
        else:
            rc2, out2 = res2, ""
        # out2 may contain "ls /tmp\n[E]xecute..." - extract first line
        if out2:
            lines=[l.strip() for l in out2.splitlines() if l.strip() and "[E]xecute" not in l and "Warning:" not in l]
            if lines:
                cmd=lines[0]
    if not cmd:
        print(c("No shell command generated (empty).", YELLOW))
        print(c("sgpt output was empty, try a more specific shell task.", YELLOW))
        wait_enter()
        return None
    # Clean markdown fences if present
    if cmd.startswith("```"):
        # strip fences
        parts=cmd.split("```")
        if len(parts)>=2:
            # content between fences
            cmd=parts[1].strip()
            # Remove language hint line if present (e.g., "bash\nls -la")
            if "\n" in cmd:
                first, rest = cmd.split("\n",1)
                if first.strip() in ("bash","sh","shell","zsh"):
                    cmd=rest.strip()
    print(BOLD+"Generated shell command:"+RESET+" "+GREEN+cmd+RESET)
    # Offer Execute / Modify / Describe / Abort
    print(DIM+"[E]xecute  [M]odify  [D]escribe  [A]bort"+RESET)
    choice=text_input("Choice", default="e")
    if not choice:
        choice="e"
    choice=choice.strip().lower()
    if choice in ("e","y","execute","yes",""):
        # Execute via shell
        print(c(f"> Executing: {cmd}", CYAN))
        try:
            # Use user's shell
            shell=os.environ.get("SHELL", "/bin/sh")
            # Run and stream output
            proc=subprocess.run(cmd, shell=True, executable=shell)
            print(c(f"Exit code: {proc.returncode}", GREEN if proc.returncode==0 else RED))
        except Exception as e:
            print(c(f"Execute failed: {e}", RED))
        wait_enter()
        return cmd
    elif choice in ("m","modify"):
        new_cmd=text_input("Modify command", default=cmd)
        if new_cmd and new_cmd!=cmd:
            print(c(f"> Executing modified: {new_cmd}", CYAN))
            try:
                shell=os.environ.get("SHELL", "/bin/sh")
                proc=subprocess.run(new_cmd, shell=True, executable=shell)
                print(c(f"Exit code: {proc.returncode}", GREEN if proc.returncode==0 else RED))
            except Exception as e:
                print(c(f"Execute failed: {e}", RED))
            wait_enter()
            return new_cmd
        else:
            print(c("Aborted modify", YELLOW))
            wait_enter()
            return cmd
    elif choice in ("d","describe"):
        # Describe shell command via sgpt --describe-shell
        clear()
        print(c(f"> Describing: {cmd}", CYAN))
        run_sgpt([cmd, "--describe-shell", "--no-cache"])
        wait_enter()
        return cmd
    else:
        print(c("Aborted.", YELLOW))
        wait_enter()
        return cmd

def do_ask():
    clear()
    print(BOLD + "QUICK ASK" + RESET)
    prompt = text_input("Your question")
    if not prompt:
        return
    clear()
    print(c(">> %s" % prompt, CYAN))
    run_sgpt([prompt, "--no-cache"])

def do_shell():
    clear()
    print(BOLD + "SHELL COMMAND (with execute)" + RESET)
    prompt = text_input("Describe the task")
    if not prompt:
        return
    clear()
    print(c(">> %s" % prompt, CYAN))
    _run_shell_and_execute(prompt)

def do_chat():
    chat_id = text_input("Chat id", default="temp")
    # Ask if shell mode should be enabled for this chat
    shell_mode=text_input("Enable shell execution in chat? (y/N)", default="n").strip().lower() in ("y","yes")
    if shell_mode:
        clear()
        print(BOLD + f"CHAT SESSION (SHELL) ({chat_id}) - type 'exit' to end" + RESET)
        print(DIM+"Shell mode: each message generates a shell command you can Execute/Modify/Describe"+RESET)
        while True:
            try:
                msg = input(CYAN + "you (shell)> " + RESET)
            except EOFError:
                break
            if msg.strip().lower() in ("exit", "quit", "q"):
                break
            if not msg.strip():
                continue
            clear()
            print(c(f">> {msg}", CYAN))
            _run_shell_and_execute(msg, chat_id=chat_id)
            clear()
            print(BOLD + f"CHAT SESSION (SHELL) ({chat_id})" + RESET)
        return
    # Normal chat (advice only)
    clear()
    print(BOLD + "CHAT SESSION (%s) - type 'exit' to end" % chat_id + RESET)
    print(DIM+"Tip: for shell execution, choose Shell command or enable shell mode on next chat"+RESET)
    while True:
        try:
            msg = input(CYAN + "you> " + RESET)
        except EOFError:
            break
        if msg.strip().lower() in ("exit", "quit", "q"):
            break
        if not msg.strip():
            continue
        clear()
        run_sgpt([msg, "--chat", chat_id, "--no-cache"])

def do_repl():
    # True repl using sgpt --repl (handles its own loop)
    chat_id = text_input("REPL chat id", default="temp")
    shell_mode=text_input("Shell REPL? (y/N)  (enables [e] to execute / [d] to describe)", default="n").strip().lower() in ("y","yes")
    clear()
    print(BOLD + f"REPL SESSION ({chat_id})"+RESET)
    if shell_mode:
        print(DIM+"Starting sgpt --repl with --shell (type 'e' to execute last command, 'd' to describe)"+RESET)
        run_sgpt(["--repl", chat_id, "--shell"])
    else:
        run_sgpt(["--repl", chat_id])

def do_shell_repl():
    # Shell REPL with TUI-managed execute (more reliable than sgpt's own REPL)
    chat_id = text_input("Shell REPL chat id", default="temp")
    clear()
    print(BOLD + f"SHELL REPL ({chat_id}) - type 'exit' to end, each prompt -> shell command with Execute" + RESET)
    while True:
        try:
            msg = input(CYAN + "you (shell repl)> " + RESET)
        except EOFError:
            break
        if msg.strip().lower() in ("exit", "quit", "q"):
            break
        if not msg.strip():
            continue
        clear()
        print(c(f">> {msg}", CYAN))
        _run_shell_and_execute(msg, chat_id=chat_id)
        clear()
        print(BOLD + f"SHELL REPL ({chat_id})" + RESET)

def do_model():
    models = active_models()
    base = read_cfg().get("API_BASE_URL", "")
    is_pollinations = "pollinations" in base
    items = [(v[1], "") for v in models.values()] + [("Custom model (type your own)", "")]
    if is_pollinations:
        items.insert(len(items)-1, ("↻ Refresh pollinations free models (live from gen.pollinations.ai)", c("live", CYAN)))
        items.insert(len(items)-1, ("Show /pollinations skill (free model RPMs)", c("skill", YELLOW)))
    pick = menu("MODEL SELECTOR", items, footer=DIM+("Pollinations free — API key public, RPM limits apply" if is_pollinations else "")+RESET)
    if pick is None:
        return
    # Handle pollinations extra items
    if is_pollinations and pick == len(items) - 3:
        # Refresh live
        clear()
        print(c("Fetching live pollinations models from https://gen.pollinations.ai/models ...", CYAN))
        live = fetch_pollinations_models(live=True)
        if live:
            items2 = [(v[1], "") for v in live.values()] + [("Custom", "")]
            p2 = menu("POLLINATIONS LIVE MODELS", items2)
            if p2 is not None and p2 < len(live):
                model = list(live.values())[p2][0]
                set_cfg_key("DEFAULT_MODEL", model)
                print(c("DEFAULT_MODEL=%s" % model, GREEN))
                wait_enter()
                return
        else:
            print(c("Live fetch failed, using curated list", YELLOW))
        # fallback to curated below
        return do_model()
    if is_pollinations and pick == len(items) - 2:
        skill_path = Path.home() / ".config" / "opencode" / "skills" / "pollinations-free-models" / "SKILL.md"
        if skill_path.exists():
            clear()
            print(skill_path.read_text()[:3000])
            # Also show models.log if exists
            log_path = Path.home() / ".pollinations" / "models.log"
            if log_path.exists():
                print(DIM+"\n--- models.log tail ---"+RESET)
                print(log_path.read_text()[-1000:])
        else:
            print(c("skill not found at "+str(skill_path), YELLOW))
        wait_enter()
        return
    if pick == len(items) - 1:
        model = text_input("Enter model id", default=read_cfg().get("DEFAULT_MODEL"))
        if not model:
            return
    else:
        # Adjust for inserted items offset
        if is_pollinations and pick >= len(models):
            # Custom is at len(models) now, but we inserted 2 extra before it
            # So if pick is beyond models, handle custom
            model = text_input("Enter model id", default=read_cfg().get("DEFAULT_MODEL"))
            if not model:
                return
        else:
            model = list(models.values())[pick][0]
    set_cfg_key("DEFAULT_MODEL", model)
    print(c("DEFAULT_MODEL=%s" % model, GREEN))
    wait_enter()

def do_provider():
    items = []
    for name, base in PROVIDERS.values():
        hint = ""
        if base and "pollinations" in base: hint = c("free", GREEN)
        elif base and "powerbrain" in base: hint = c("free", GREEN)
        elif base and "workers-ai" in str(base): hint = c("cloudflare", CYAN)
        items.append((name, hint))
    pick = menu("PROVIDER SELECTOR", items, footer=DIM+"green=free (no key: pollinations/powerbrain)  See /pollinations skill for free models"+RESET)
    if pick is None:
        return
    name, base = list(PROVIDERS.values())[pick]
    current = read_cfg().get("API_BASE_URL", "")
    mode = "workers-ai"
    if name == "Cloudflare AI Gateway":
        cur_acc, cur_gw, cur_mode = parse_cloudflare_base(current)
        mode_items = [(label, "") for label, _ in CF_MODES.values()]
        mpick = menu("CLOUDFLARE ACCESS MODE", mode_items)
        if mpick is None:
            return
        mode = list(CF_MODES.values())[mpick][1]
        acc = text_input("Cloudflare account ID", default=cur_acc)
        if not acc:
            print(c("cancelled", YELLOW))
            wait_enter()
            return
        gw = text_input("cf-aig-gateway-id (gateway slug)", default=cur_gw or "acode")
        base = cloudflare_base(acc, gw, mode)
        if mode == "aig" and not read_cfg().get("DEFAULT_MODEL"):
            set_cfg_key("DEFAULT_MODEL", "gpt-4o-mini")
    elif name in ("Pollinations (free)", "PowerBrain (free)"):
        # Use curated base URL directly, no extra input
        pass
    elif base is None:
        base = text_input("Base URL (end with /v1, or 'default')", default=current)
        if not base:
            return
    set_cfg_key("API_BASE_URL", base)
    if name == "Cloudflare AI Gateway":
        model = list(active_models().values())[0][0] if mode == "workers-ai" else "gpt-4o-mini"
        if not read_cfg().get("DEFAULT_MODEL"):
            set_cfg_key("DEFAULT_MODEL", model)
    elif name == "Pollinations (free)":
        # Set default pollinations model to curated first or live
        mods = fetch_pollinations_models(live=False)
        first = list(mods.values())[0][0] if mods else "openai"
        if not read_cfg().get("DEFAULT_MODEL") or "pollinations" not in read_cfg().get("API_BASE_URL",""):
            set_cfg_key("DEFAULT_MODEL", first)
        # Also set a public pollinations key if none exists (from skill)
        if not read_cfg().get("OPENAI_API_KEY"):
            # public key from pollinations-free-models skill log
            try:
                log = Path.home() / ".config" / "opencode" / "skills" / "pollinations-free-models" / "SKILL.md"
                # use known public key as fallback
                set_cfg_key("OPENAI_API_KEY", text_input("Your Pollinations API key (leave empty to cancel)") or read_cfg().get("OPENAI_API_KEY", ""))
            except: pass
    elif name == "PowerBrain (free)":
        if not read_cfg().get("DEFAULT_MODEL"):
            set_cfg_key("DEFAULT_MODEL", "gpt-5")
        cfg = read_cfg()
        cfg.pop("OPENAI_API_KEY", None)
        write_cfg(cfg)
        print(c("PowerBrain needs no API key", GREEN))
        print(c("API_BASE_URL=%s" % base, GREEN))
        wait_enter()
        return
    key = text_input("API key / token for %s (optional, pollinations uses public key)" % name, default="")
    if key:
        set_cfg_key("OPENAI_API_KEY", key)
    else:
        # For pollinations/powerbrain keep existing key if not cleared; for others allow clearing
        if name not in ("Pollinations (free)", "PowerBrain (free)"):
            cfg = read_cfg()
            # For pollinations keep public key if already set
            if not (name == "Pollinations (free)" and cfg.get("OPENAI_API_KEY")):
                cfg.pop("OPENAI_API_KEY", None)
                write_cfg(cfg)
    print(c("API_BASE_URL=%s" % base, GREEN))
    model = read_cfg().get("DEFAULT_MODEL") or "gpt-4o-mini"
    eff_key = key or read_cfg().get("OPENAI_API_KEY", "")
    if text_input("Test this connection now? (y/N)", default="n").strip().lower() in ("y", "yes"):
        clear()
        print(c("Testing %s with model %s ..." % (base, model), CYAN))
        print(test_connection(base, eff_key, model))
        # For pollinations, show skill hint
        if name == "Pollinations (free)":
            print(DIM+"Tip: run /pollinations skill or check ~/.config/opencode/skills/pollinations-free-models/SKILL.md for free model RPM limits"+RESET)
    wait_enter()

def do_usage():
    clear()
    run_usage()
    wait_enter()

def do_show_config():
    clear()
    print(BOLD + "CONFIG: %s" % CFG_PATH + RESET)
    if CFG_PATH.exists():
        cfg = read_cfg()
        for k, v in cfg.items():
            if "KEY" in k.upper():
                print("%s=%s" % (k, v[:8] + "..." if len(v) > 8 else v))
            else:
                print("%s=%s" % (k, v))
    else:
        print(c("no config file yet", YELLOW))
    wait_enter()

def do_edit_config():
    clear()
    if not CFG_PATH.exists():
        print(c("config file does not exist yet", YELLOW))
        wait_enter()
        return
    editor = get_editor()
    try:
        subprocess.call([editor, str(CFG_PATH)])
    except Exception as exc:
        print(c("failed to open editor %s: %s" % (editor, exc), RED))
        wait_enter()

def do_roles():
    roles_dir = Path(read_cfg().get("ROLE_STORAGE_PATH", str(CFG_PATH.parent / "roles")))
    if not roles_dir.exists():
        print(c("roles folder not found: %s" % roles_dir, YELLOW))
        wait_enter()
        return
    files = sorted(roles_dir.glob("*.json"))
    if not files:
        print(c("no roles installed", YELLOW))
        wait_enter()
        return
    items = [(f.stem, "") for f in files]
    pick = menu("ROLES", items)
    if pick is None:
        return
    try:
        data = json.loads(files[pick].read_text(encoding="utf-8"))
        clear()
        print(BOLD + data.get("name", files[pick].stem) + RESET)
        print(data.get("role", ""))
    except Exception as exc:
        print(c("error reading role: %s" % exc, RED))
    wait_enter()

MAIN_ITEMS = [
    ("Quick ask", ""),
    ("Shell command (with execute)", "generate + [E]xecute"),
    ("Shell REPL (interactive + execute)", "loop shell with [E]xecute"),
    ("Chat session", "advice (ask shell for execute)"),
    ("REPL (sgpt --repl)", "native repl loop"),
    ("Model selector", "pollinations live: refresh in model menu"),
    ("Provider selector", "Cloudflare/OpenAI/Pollinations/PowerBrain"),
    ("Neurons usage (real)", "Cloudflare gateway daily neurons"),
    ("Show config", ""),
    ("Edit config", ""),
    ("Roles", ""),
    ("Pollinations skill (/pollinations)", c("free", GREEN)),
    ("Quit", ""),
]

def main_menu():
    while True:
        pick = menu("SGPT TOOLKIT - CONTROL CENTER", MAIN_ITEMS)
        if pick is None or pick == len(MAIN_ITEMS) - 1:
            break
        if pick == 0:
            do_ask()
        elif pick == 1:
            do_shell()
        elif pick == 2:
            do_shell_repl()
        elif pick == 3:
            do_chat()
        elif pick == 4:
            do_repl()
        elif pick == 5:
            do_model()
        elif pick == 6:
            do_provider()
        elif pick == 7:
            do_usage()
        elif pick == 8:
            do_show_config()
        elif pick == 9:
            do_edit_config()
        elif pick == 10:
            do_roles()
        elif pick == 11:
            # Pollinations skill quick view
            skill_path = Path.home() / ".config" / "opencode" / "skills" / "pollinations-free-models" / "SKILL.md"
            if skill_path.exists():
                clear()
                print(BOLD+"POLLINATIONS FREE MODELS — /pollinations skill"+RESET)
                print(skill_path.read_text()[:4000])
                print(DIM+"\nTip: In Model selector > Pollinations base > Refresh live models"+RESET)
                # Offer to fetch live
                if text_input("Fetch live models now? (y/N)", default="n").lower() in ("y","yes"):
                    clear()
                    print(c("Fetching https://gen.pollinations.ai/models ...", CYAN))
                    live = fetch_pollinations_models(live=True)
                    for k,v in live.items():
                        print(f"{v[0]:35} {v[1]}")
                wait_enter()
            else:
                print(c("skill not found, fetching live", YELLOW))
                live = fetch_pollinations_models(live=True)
                for k,v in live.items():
                    print(f"{v[0]:35} {v[1]}")
                wait_enter()

def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print("sgpt-tui - terminal UI for the sgpt toolkit")
        print("")
        print("  no args            interactive TUI")
        print("  --ask '<q>'        ask a question and print the answer")
        print("  --shell '<task>'   generate a shell command")
        print("  --usage            show real neuron usage")
        print("  --show-config      print the resolved config")
        print("  --set-model <id>   set the default model")
        print("  --set-base <url>   set API base URL")
        print("  --set-key <key>    set API key")
        print("  --config           print resolved config path")
        print("  --preview          render the main menu once (no input)")
        return
    if args and args[0] == "--ask" and len(args) > 1:
        clear()
        run_sgpt([args[1], "--no-cache"])
        return
    if args and args[0] == "--shell" and len(args) > 1:
        clear()
        run_sgpt([args[1], "--shell", "--no-interaction", "--no-cache"])
        return
    if args and args[0] == "--usage":
        clear()
        run_usage()
        return
    if args and args[0] == "--show-config":
        for k, v in read_cfg().items():
            if "KEY" in k.upper():
                print("%s=%s" % (k, v[:8] + "..." if len(v) > 8 else v))
            else:
                print("%s=%s" % (k, v))
        return
    if args and args[0] == "--set-model" and len(args) > 1:
        set_cfg_key("DEFAULT_MODEL", args[1])
        print("DEFAULT_MODEL=%s" % args[1])
        return
    if args and args[0] == "--set-base" and len(args) > 1:
        set_cfg_key("API_BASE_URL", args[1])
        print("API_BASE_URL=%s" % args[1])
        return
    if args and args[0] == "--set-key" and len(args) > 1:
        set_cfg_key("OPENAI_API_KEY", args[1])
        print("OPENAI_API_KEY updated")
        return
    if args and args[0] == "--config":
        print(CFG_PATH)
        return
    if args and args[0] == "--preview":
        render("SGPT TOOLKIT - CONTROL CENTER", MAIN_ITEMS, 0, footer="")
        return
    main_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear()
        print("bye")
        sys.exit(0)
